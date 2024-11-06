import discord
from discord.ext import commands
import app.config as config
import app.dbInfo as dbInfo
from datetime import datetime, timedelta
from discord.commands import Option
import asyncio

class SubstitutionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.substitution_timers = {}  # A dictionary to track substitution end times

    @commands.slash_command(guild_ids=[config.lol_server], description="Substitute a player onto a team")
    async def substitute_player(self, ctx, player: discord.Member, team_code: Option(str, "Enter 3-digit team abbreviation"), duration: Option(int, "Enter number for amount of minutes")):
        # Check if the player is a free agent
        player_data = dbInfo.players_collection.find_one({"discord_id": player.id})
        if not player_data or player_data.get("team") not in ["FA", None]:
            return await ctx.respond(f"{player.mention} is not a free agent or does not exist in the database.", ephemeral=True)

        # Check if the player is eligible
        if not player_data.get("eligible", False):
            return await ctx.respond(f"{player.mention} is not eligible for substitution.", ephemeral=True)

        # Find the team role based on team code
        team_data = dbInfo.teams_collection.find_one({"team_code": team_code.upper()})
        if not team_data:
            return await ctx.respond(f"Team with code '{team_code}' does not exist.", ephemeral=True)

        team_role = ctx.guild.get_role(team_data['team_id'])
        if not team_role:
            return await ctx.respond(f"Could not find the role for team '{team_code}'.", ephemeral=True)

        # Assign the team role to the player
        await player.add_roles(team_role)
        await ctx.respond(f"{player.mention} has been substituted onto '{team_code}' for {duration} minutes.")

        # Set a timer to remove the role after the specified duration
        end_time = datetime.now() + timedelta(minutes=duration)
        self.substitution_timers[player.id] = (team_role.id, end_time)
        
        # Start a task to remove the role after the duration
        self.bot.loop.create_task(self.remove_role_after_duration(player, team_role, duration))

    async def remove_role_after_duration(self, player: discord.Member, team_role: discord.Role, duration: int):
        # Wait for the specified duration
        await asyncio.sleep(duration * 60)

        # Check if the player still has the team role
        if team_role in player.roles:
            await player.remove_roles(team_role)
            await player.send(f"Your substitution time on team '{team_role.name}' has ended, and your role has been removed.")

        # Remove the substitution timer entry
        if player.id in self.substitution_timers:
            del self.substitution_timers[player.id]

def setup(bot):
    bot.add_cog(SubstitutionCog(bot))
