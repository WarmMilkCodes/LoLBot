import discord
import logging, re
from discord.ext import commands
from discord.commands import Option
import app.dbInfo as dbInfo
import app.config as config
from tabulate import tabulate

logger = logging.getLogger(__name__)

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

    @commands.slash_command(guild_ids=[config.lol_server], description="Assign prefixes based on roles and undo previous changes")
    @commands.has_any_role("Bot Guy")
    async def assign_prefixes(self, ctx):
        guild = ctx.guild
        free_agent_role = discord.utils.get(guild.roles, name="Free Agents")
        spectator_role = discord.utils.get(guild.roles, name="Spectator")
        not_eligible_role = discord.utils.get(guild.roles, name="Not Eligible")
        franchise_governor_role = discord.utils.get(guild.roles, name="Franchise Governors")

        if not free_agent_role or not spectator_role or not not_eligible_role:
            await ctx.respond("Roles not found. Ensure 'Free Agents', 'Spectator', 'Not Eligible', and 'Franchise Governors' roles exist.", ephemeral=True)
            return

        updated_users = []

        for member in guild.members:
            if franchise_governor_role in member.roles:
                # Check for team role associated with Franchise Governor and assign team code as prefix
                team_role = next((role for role in member.roles if dbInfo.team_collection.find_one({"team_id": role.id})), None)
                if team_role:
                    team_code = dbInfo.team_collection.find_one({"team_id": team_role.id}).get("team_code")
                    if team_code:
                        await self.update_nickname(member, team_code)
                        updated_users.append(f"Updated {member.display_name} to {team_code} | {member.display_name}")
                continue  # Skip other roles if Franchise Governor

            if free_agent_role in member.roles:
                await self.update_nickname(member, "FA")
                updated_users.append(f"Updated {member.display_name} to FA | {member.display_name}")
            elif spectator_role in member.roles:
                await self.update_nickname(member, "S")
                updated_users.append(f"Updated {member.display_name} to S | {member.display_name}")
            elif not_eligible_role in member.roles:
                await self.update_nickname(member, "TBD")
                updated_users.append(f"Updated {member.display_name} to TBD | {member.display_name}")
            else:
                # Remove prefix if none of the roles apply
                await self.update_nickname(member, None)
                updated_users.append(f"Restored {member.display_name} to original nickname")

        response_message = "Updated prefixes:\n" + "\n".join(updated_users) if updated_users else "No users were updated."
        await ctx.respond(response_message, ephemeral=True)

    @commands.slash_command(guild_ids=[config.lol_server], description="Return player info embed")
    @commands.has_any_role("Bot Guy", "League Ops")
    async def player_info(self, ctx, user: Option(discord.Member)):
        guild = ctx.guild

        allowed_channels = [self.bot.get_channel(ch_id) for ch_id in config.admin_channels]
        if ctx.channel.id not in config.admin_channels:
            channels_str = ', '.join([ch.mention for ch in allowed_channels if ch])
            return await ctx.respond(f"This command can only be used in the following channels: {channels_str}", ephemeral=True)

        team_id = dbInfo.team_collection.find_one({"team_id": {"$in": [r.id for r in user.roles]}}, {"_id": 0, "team_id": 1})
        team_info = "Unassigned"
        if team_id:
            team_role = ctx.guild.get_role(team_id["team_id"])
            if team_role:
                team_info = team_role.mention

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

        # Handling the rank_info array with proper formatting
        rank_info_array = player_info.get('rank_info', [])
        rank_info_display = ""
        if rank_info_array:
            rank_info_list = []
            for rank in rank_info_array:
                queue_type = rank.get('queue_type', 'N/A').replace('_', ' ').title()
                tier = rank.get('tier', 'N/A').capitalize()
                division = rank.get('division', 'N/A').upper()
                rank_info_list.append(f"\n**Queue Type**: {queue_type}\n**Tier**: {tier}\n**Division**: {division}")
            rank_info_display = '\n'.join(rank_info_list)
        else:
            rank_info_display = "N/A"

        player_info_list = [
            f"**Username**: {user.name}",
            f"**Riot ID**: {player_info.get('game_name', 'N/A')}#{player_info.get('tag_line', 'N/A')}",
            f"**Status**: {player_status_embed}",
            f"**Eligibility**:  {'Eligible' if player_info.get('eligible_for_split') == True else 'Not Eligible'}",
            f"**Rank Info**:\n{rank_info_display}"
        ]

        embed = discord.Embed(title=f"Player Info for {user.display_name}", color=discord.Color.blue())
        embed.set_thumbnail(url=user.avatar.url)
        embed.add_field(name="Player Info", value='\n'.join(player_info_list))

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

        await ctx.respond(embed=embed)
        
    @commands.slash_command(guild_ids=[config.lol_server], description="Return player eligibility tabulate")
    @commands.has_any_role("Bot Guy", "League Ops")
    async def player_eligibility(self, ctx):
        await ctx.defer()
        # Fetch all players who are playing
        players = list(dbInfo.player_collection.find({"eligible_for_split": {"$exists": True}}))

        if not players:
            await ctx.respond("No players found with eligibility information.", ephemeral=True)
            return

        table_data = []
        for player in players:
            discord_id = player.get('discord_id')
            username = self.bot.get_user(discord_id).name if self.bot.get_user(discord_id) else "Unknown"
            eligible = "Yes" if player.get("eligible_for_split") else "No"
            game_count = player.get("current_split_game_count", "N/A")
            last_check = player.get("last_eligibility_check", "N/A")

            table_data.append([username, eligible, game_count, last_check])

        table_headers = ["Username", "Eligible", "Game Count", "Last Check"]
        table_string = tabulate(table_data, headers=table_headers, tablefmt="grid")

        if len(table_string) < 2000:
            await ctx.respond(f"```{table_string}```")
        else:
            messages = [table_string[i:i+1990] for i in range(0, len(table_string), 1990)]
            await ctx.respond(f"```{messages[0]}```")
        
        for message in messages:
            await ctx.followup.send(f"```{message}```")
        

def setup(bot):
    bot.add_cog(StaffCog(bot))
