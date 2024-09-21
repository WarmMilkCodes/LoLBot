import discord
import logging, re
from discord.ext import commands
from discord.commands import Option
import app.dbInfo as dbInfo
import app.config as config
from tabulate import tabulate

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

    async def update_nickname(self, member, prefix):
        """Update member's nickname with given prefix, or restore original if no prefix."""
        try:
            # Remove any existing prefix
            new_nickname = re.sub(r"^(FA \| |S \| |TBD \| |[A-Z]{2,3} \| )", "", member.display_name)
            # Add new prefix if applicable
            if prefix:
                new_nickname = f"{prefix} | {new_nickname}"
            await member.edit(nick=new_nickname)
            logger.info(f"Updated nickname for {member.name} to {new_nickname}")
        except Exception as e:
            logger.error(f"Error updating nickname for {member.name}: {e}")

    @commands.slash_command(guild_ids=[config.lol_server], description="Change a player to spectator")
    @commands.has_any_role("League Ops", "Bot Guy")
    async def force_spectator(self, ctx, user: Option(discord.Member)):
        await ctx.defer(ephemeral=True)

        user_info = dbInfo.intent_collection.find_one({"ID": user.id})
        try:
            if user_info:
                if user_info.get("Playing") == "Yes":
                    dbInfo.intent_collection.update_one(
                        {"ID": user.id},
                        {"$set": {"Playing": "No"}}
                    )
                    await self.update_nickname(user, "S")
                    logger.info(f"{ctx.author.name} forced {user} to spectator.")
                    await ctx.respond(f"Succesfully forced {user.mention} to spectator.")
        except Exception as e:
            logger.error(f"Unable to force change {user}'s intent form to spectator: {e}")
            await ctx.respond(f"Error forcing {user} to spectator: {e}")
        

    @commands.slash_command(guild_ids=[config.lol_server], description="Update avatar URLs for all existing members in the database.")
    @commands.has_role("Bot Guy")
    async def update_avatars(self, ctx):
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


    @commands.slash_command(guild_ids=[config.lol_server], description="Return player info embed")
    @commands.has_any_role("Bot Guy", "League Ops")
    async def player_info(self, ctx, user: Option(discord.Member)):
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

        player_status = player_intent.get('Playing')
        if player_intent:
            if player_status == 'Yes':
                player_status_embed = 'Playing'
            elif player_status == 'No':
                player_status_embed = 'Spectator'
            else:
                player_status_embed = 'N/A'

        # Fetch number of games in split
        split_games = player_info.get('current_split_game_count', 'N/A')

        # Calculate peak rank (pass the entire player_info to get_peak_rank function)
        peak_rank = get_peak_rank(player_info)

        # Determine salary, prioritize manual salary if available
        manual_salary = player_info.get('manual_salary')
        salary = manual_salary if manual_salary else player_info.get('salary', 'N/A')

        # Construct player info list
        player_info_list = [
            f"**Username**: {user.name}",
            f"**Riot ID**: {player_info.get('game_name', 'N/A')}#{player_info.get('tag_line', 'N/A')}",
            f"**Salary**: {salary}",
            f"**Status**: {player_status_embed}",
            f"**Eligibility**:  {'Eligible' if player_info.get('eligible_for_split') == True else 'Not Eligible'}",
            f"**Current Games**: {split_games}\n"
            f"**Peak Rank**:\n{peak_rank}"  # Display peak rank here
        ]

        # Embed creation
        embed = discord.Embed(title=f"Player Info for {user.display_name}", color=discord.Color.blue())
        embed.set_thumbnail(url=user.avatar.url)
        embed.add_field(name="Player Profile", value=f"[Click here to view profile]({player_profile_url})", inline=False)
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
    async def update_riot_id(self, ctx, user: Option(discord.Member), game_name: Option(str, "Enter user's game name"), tag_line: Option(str, "Enter user's tag line - do not include '#'")):
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
