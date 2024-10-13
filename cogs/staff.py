import discord
import logging, re
from discord.ext import commands
from discord.commands import Option
import app.dbInfo as dbInfo
import app.config as config
from tabulate import tabulate
from urllib.parse import quote_plus
from app.helper import update_nickname

logger = logging.getLogger(__name__)

def get_peak_rank(player_info):
    RANK_ORDER = {
        "IRON": 1, "BRONZE": 2, "SILVER": 3, "GOLD": 4, "PLATINUM": 5, 
        "EMERALD": 6, "DIAMOND": 7, "MASTER": 8, "GRANDMASTER": 9, "CHALLENGER": 10
    }
    DIVISION_ORDER = {"IV": 1, "III": 2, "II": 3, "I": 4}

    highest_rank = None
    highest_division = None

    # Function to update the highest rank
    def update_highest_rank(tier, division):
        nonlocal highest_rank, highest_division
        if tier is None or division is None:
            return

        if highest_rank is None or (
            RANK_ORDER.get(tier, 0) > RANK_ORDER.get(highest_rank, 0)
        ) or (
            RANK_ORDER.get(tier) == RANK_ORDER.get(highest_rank) and DIVISION_ORDER.get(division, 0) > DIVISION_ORDER.get(highest_division, 0)
        ):
            highest_rank = tier
            highest_division = division

    # Process current rank_info (if exists)
    rank_info_array = player_info.get('rank_info', [])
    for rank in rank_info_array:
        queue_type = rank.get('queue_type')
        if queue_type == "RANKED_SOLO_5x5":
            tier = rank.get('tier', None)
            division = rank.get('division', None)
            update_highest_rank(tier, division)

    # Process historical_rank_info (if exists)
    historical_rank_info = player_info.get('historical_rank_info', {})
    for date, rank_array in historical_rank_info.items():
        for rank in rank_array:
            queue_type = rank.get('queue_type')
            if queue_type == "RANKED_SOLO_5x5":
                tier = rank.get('tier', None)
                division = rank.get('division', None)
                update_highest_rank(tier, division)

    if highest_rank:
        return f"{highest_rank.capitalize()} {highest_division.upper()}"
    return "N/A"




class StaffCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot         

    @commands.slash_command(guild_ids=[config.lol_server], description="Process series as FF")
    @commands.has_any_role("League Ops", "Bot Guy")
    async def admn_ff_series(self, ctx, ff_team: Option(str, "Enter 3-digit code of forfeiting team (ex. SDA)"), win_team: Option(str, "Enter 3-digit code of winning team (ex. SDA)")):
        try:
            await ctx.defer()

            # Ensure team codes entered correctly
            winning_team = dbInfo.team_collection.find_one({"team_code": win_team.upper()})
            ffing_team = dbInfo.team_collection.find_one({"team_code": ff_team.upper()})

            if winning_team and ffing_team:
                # Update winner record
                dbInfo.team_collection.update_one({"team_code": win_team.upper()}, {"$inc": {"wins": 1}})
                # Update loser record
                dbInfo.team_collection.update_one({"team_code": ff_team.upper()}, {"$inc": {"losses": 1}})

                await ctx.respond(f"Forfeit processed succesfully. {ff_team.upper()} forfeited to {win_team.upper()}.")
                logger.info(f"{ctx.author.display_name} processed FF of {ff_team.upper()} to {win_team.upper()}")

            else:
                await ctx.respond(f"One or both team codes were not found. Please ensure the correct abbreviations are used.")
        
        except Exception as e:
            await ctx.respond(f"There was an error processing the FF: {e}")
            logger.error(f"There was an error processing FF submission: {e}")


    @commands.slash_command(guild_ids=[config.lol_server], description="Change a player to spectator")
    @commands.has_any_role("League Ops", "Bot Guy")
    async def admn_force_spectator(self, ctx, user: Option(discord.Member)):
        await ctx.defer(ephemeral=True)
        
        fa_role = discord.utils.get(ctx.guild.roles, name="Free Agents")
        spect_role = discord.utils.get(ctx.guild.roles, name="Spectator")

        user_info = dbInfo.intent_collection.find_one({"ID": user.id})
        try:
            if user_info:
                if user_info.get("Playing") == "Yes":
                    dbInfo.intent_collection.update_one(
                        {"ID": user.id},
                        {"$set": {"Playing": "No"}}
                    )

                    if fa_role in user.roles:
                        await user.remove_roles(fa_role)
                    await user.add_roles(spect_role)
                    
                    await update_nickname(user, "S")

                    logger.info(f"{ctx.author.name} forced {user} to spectator.")
                    await ctx.respond(f"Succesfully forced {user.mention} to spectator.")
        except Exception as e:
            logger.error(f"Unable to force change {user}'s intent form to spectator: {e}")
            await ctx.respond(f"Error forcing {user} to spectator: {e}")
        

    @commands.slash_command(guild_ids=[config.lol_server], description="Update avatar URLs for all existing members in the database.")
    @commands.has_role("Bot Guy")
    async def admn_update_avatars(self, ctx):
        await ctx.defer(ephemeral=True)

        # Get the list of all members in the guild
        members = ctx.guild.members

        updated_count = 0

        for member in members:
            if not member.bot:
                # Get the user's avatar URL (using default avatar if they don't have one)
                avatar_url = str(member.avatar.url if member.avatar else member.default_avatar.url)

                # Update the player's document in the database with the avatar URL
                dbInfo.player_collection.update_one(
                    {"discord_id": member.id},
                    {"$set": {"avatar_url": avatar_url}},
                    upsert=True
                )
                updated_count += 1
                logger.info(f"Updated avatar for {member.name} ({member.id})")

        await ctx.respond(f"Avatar URLs updated for {updated_count} members.", ephemeral=True)


    @commands.slash_command(guild_ids=[config.lol_server], description="Return player K/D/A stats")
    @commands.has_any_role("Bot Guy", "League Ops")
    async def admn_player_stats(self, ctx, user: discord.Option(discord.Member)):
        await ctx.defer()

        # Fetch the player document based on the Discord user ID
        player = dbInfo.player_collection.find_one({"discord_id": user.id})

        if not player:
            await ctx.respond(f"Player with Discord ID {user.id} not found in the players collection.")
            return

        # Get the player's PUUID
        player_puuid = player.get("raw_puuid")
        if not player_puuid:
            await ctx.respond(f"Player does not have a PUUID associated.")
            return

        # Fetch replays where the player participated
        replays = dbInfo.replays_collection.find({"players.puuid": player_puuid})

        # Initialize total stats
        total_kills = 0
        total_deaths = 0
        total_assists = 0

        # Sum up K/D/A stats from each replay
        for replay in replays:
            # Find the player's stats from the replay by matching the PUUID
            player_stats = next((p for p in replay["players"] if p["puuid"] == player_puuid), None)

            if player_stats:
                total_kills += int(player_stats.get("champions_killed", 0))
                total_deaths += int(player_stats.get("num_deaths", 0))
                total_assists += int(player_stats.get("assists", 0))

        # Respond with the total K/D/A
        await ctx.respond(f"Player K/D/A for {user.display_name}: {total_kills}/{total_deaths}/{total_assists}")

    @commands.slash_command(guild_ids=[config.lol_server], description="Return player info embed")
    @commands.has_any_role("Bot Guy", "League Ops")
    async def admn_player_info(self, ctx, user: discord.Option(discord.Member)):
        await ctx.defer()
        guild = ctx.guild
        player_profile_url = f"https://lol-web-app.onrender.com/player/{user.id}"

        allowed_channels = [self.bot.get_channel(ch_id) for ch_id in config.admin_channels]
        if ctx.channel.id not in config.admin_channels:
            channels_str = ', '.join([ch.mention for ch in allowed_channels if ch])
            return await ctx.respond(f"This command can only be used in the following channels: {channels_str}", ephemeral=True)

        # Fetch team info
        team_id = dbInfo.team_collection.find_one({"team_id": {"$in": [r.id for r in user.roles]}}, {"_id": 0, "team_id": 1})
        team_info = "Unassigned"
        if team_id:
            team_role = ctx.guild.get_role(team_id["team_id"])
            if team_role:
                team_info = team_role.mention

        # Fetch player intent and info from DB
        player_intent = dbInfo.intent_collection.find_one({"ID": user.id})
        player_info = dbInfo.player_collection.find_one({"discord_id": user.id}, {"_id": 0})

        # Fetch player status from intent
        player_status = player_intent.get('Playing', 'N/A') if player_intent else 'N/A'
        player_status_embed = 'Playing' if player_status == 'Yes' else 'Spectator' if player_status == 'No' else 'N/A'

        # Fetch Fall and Summer 2024 split counts
        summer_split_games = player_info.get('summer_split_game_count', 0)
        fall_split_games = player_info.get('fall_split_game_count', 0)

        # Calculate total split games
        total_games = summer_split_games + fall_split_games if isinstance(summer_split_games, int) and isinstance(fall_split_games, int) else 'N/A'

        # Determine eligibility based on combined games from current and last split
        is_eligible = total_games >= 30 if isinstance(total_games, int) else False
        eligibility_status = 'Eligible' if is_eligible else 'Not Eligible'

        # Calculate peak rank (pass the entire player_info to get_peak_rank function)
        peak_rank = player_info.get('peak_rank', 'N/A')
        if peak_rank != "N/A":
            tier = peak_rank.get('tier', 'Unk Tier')
            division = peak_rank.get('division', "Unk Div")
            display_peak_rank = f"{tier} {division}"
        else:
            display_peak_rank = 'N/A'

        # Determine salary, prioritize manual salary if available
        manual_salary = player_info.get('manual_salary')
        salary = manual_salary if manual_salary else player_info.get('salary', 'N/A')

        # Fetch alt accounts (if any)
        alt_accounts = player_info.get("alt_accounts", [])
        alt_accounts_list = "\n".join([f"{alt['game_name']}#{alt['tag_line']}" for alt in alt_accounts]) if alt_accounts else "None"

        # Build OP.GG link
        if player_info.get('game_name') and player_info.get('tag_line'):
            # URL encode the game_name to handle spaces and special characters
            encoded_game_name = quote_plus(player_info.get('game_name'))
            opgg_base_url = f"https://www.op.gg/summoners/na/{encoded_game_name}-{player_info.get('tag_line')}"
            opgg_embed_value = f"[Click here to view OP.GG profile]({opgg_base_url})"
        else:
            opgg_embed_value = "No OP.GG link for this player."


        # Build Riot ID
        game_name = player_info.get('game_name', '')
        tag_line = player_info.get('tag_line', '')
        hash_tag = '#'

        if game_name == "None" and tag_line == "None":
            game_name = 'N/A'
            tag_line = ''
            hash_tag = ''

        if not game_name and not tag_line:
            game_name = 'N/A'
            tag_line = ''
            hash_tag = ''

        # Construct player info list
        player_info_list = [
            f"**Username**: {user.name}",
            f"**Riot ID**: {game_name}{hash_tag}{tag_line}",
            f"**Salary**: {salary}",
            f"**Status**: {player_status_embed}",
            f"**Eligibility**: {eligibility_status}",
            f"**Total Games (Last + Current Split)**: {total_games}",
            f"**Summer Split**: {summer_split_games}",
            f"**Fall Split**: {fall_split_games}",
            f"**Peak Rank**:\n{display_peak_rank}",
            f"**Alt Account(s)**:\n{alt_accounts_list}"
        ]

        # Embed creation
        embed = discord.Embed(title=f"Player Info for {user.display_name}", color=discord.Color.blue())
        embed.set_thumbnail(url=user.avatar.url)
        embed.add_field(name="Player Profile", value=f"[Click here to view profile]({player_profile_url})", inline=False)
        embed.add_field(name="OP.GG Profile", value=f"{opgg_embed_value}", inline=False)
        embed.add_field(name="Player Info", value='\n'.join(player_info_list))

        # Display user roles excluding default role
        user_roles = '\n'.join([x.mention for x in user.roles if x != ctx.guild.default_role])
        if user_roles:
            embed.add_field(name="User Roles", value=user_roles)

        # Mapping the intent fields to display in the embed
        if player_intent:
            intent_info = '\n'.join([
                f"**Playing**: {player_intent.get('Playing', 'N/A')}",
                f"**Date Submitted**: {player_intent.get('Completed On', 'N/A')}"
            ])
            embed.add_field(name="Intent Info", value=intent_info)
        else:
            embed.add_field(name="Intent Info", value="N/A")

        embed.add_field(name="Team Info", value=team_info)

        # Respond with the embed
        await ctx.respond(embed=embed)

        

    @commands.slash_command(guild_ids=[config.lol_server], description="Update a user's Riot ID")
    @commands.has_any_role("Bot Guy", "League Ops")
    async def admn_update_riotid(self, ctx, user: Option(discord.Member), game_name: Option(str, "Enter user's game name"), tag_line: Option(str, "Enter user's tag line - do not include '#'")):
        await ctx.defer()
        
        player_data = dbInfo.player_collection.find_one({"discord_id": user.id})

        if not player_data:
            return await ctx.respond(f"{user.mention} was not found in the database.")
        
        dbInfo.player_collection.update_one({"discord_id": user.id}, {"$set" : {"game_name":game_name, "tag_line":tag_line}})

        riot_log_channel = self.bot.get_channel(config.riot_id_log_channel)

        if riot_log_channel:
            message = f"{user.mention}'s Riot ID has been updated: {game_name}#{tag_line}"
            await riot_log_channel.send(message)

        await ctx.respond(f"Succesfully updated {user.mention}'s Riot ID: {game_name}#{tag_line}", ephemeral=True)

def setup(bot):
    bot.add_cog(StaffCog(bot))
