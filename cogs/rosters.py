import discord
import logging
from discord.ext import commands
import app.config as config
import app.dbInfo as dbInfo
from tabulate import tabulate
import re
from datetime import datetime

logger = logging.getLogger('__name__')

# Discord color mapping
DISCORD_COLOR_MAP = {
    "Blue": discord.Color.blue(),
    "Red": discord.Color.red(),
    "Teal": discord.Color.teal(),
    "Yellow": discord.Color.gold(),
    "Orange": discord.Color.orange()
}

# Update base URL where team logos are served from
base_logo_url = "https://lol-web-app.onrender.com"

class Roster(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _print_rosters(self):

        # Get roster channel
        roster_channel = self.bot.get_channel(config.rosters_channel)

        if not roster_channel:
            logger.error("Roster channel not found.")
            return
        
        # Clear all messages in roster channel before reposting
        async for message in roster_channel.history(limit=10):
            await message.delete()

        # Fetch all teams from team collection with logos (active teams)
        teams = dbInfo.team_collection.find({"logo": {"$exists": True}}).sort("team_name", 1)

        # Build embed for each team
        for team in teams:
            team_name = team["team_name"]
            team_code = team["team_code"]
            team_logo_path = team.get("logo", None)

            team_owner = team.get("owner", "")
            team_gm = team.get("gm", "")
            team_color_name = team.get("team_color", "Blue")
            team_color = DISCORD_COLOR_MAP.get(team_color_name, discord.Color.blue())
            team_cap = team.get("salary_cap", 610)
            team_rmn_cap = team.get("remaining_cap", 610)

            # Convert local path to URL or fall back to none
            team_logo_url = f"{base_logo_url}{team_logo_path}" if team_logo_path else ''

            # Fetch active roster players for this team (exclude reserves)
            roster_list = dbInfo.player_collection.find({"team": team_code, "active_roster": True, "reserve_player": {"$ne": True}})

            player_slots = ['A', 'B', 'C', 'D', 'E']

            # Tabulate the roster with 'Slots' header
            roster_table = []

            # Only add non-reserve players
            for index, player in enumerate(roster_list):
                # Truncate long player names
                player_name = player['nickname'].replace(f"{team_code} | ", "")[:20]  # Truncate after 20 characters
                player_salary = player.get("manual_salary", player.get("salary", "TBD"))  # Use manual_salary if available, else salary

                slot = player_slots[index] if index < len(player_slots) else "N/A"  # Assign A-E, else N/A if more players
                roster_table.append([slot, player_name, player_salary])

            # Create tabulated roster display
            roster_display = tabulate(roster_table, headers=["Slot", "Player", "Salary"], tablefmt="plain") if roster_table else "No players on roster"

            # Create the embed for this team's roster
            embed = discord.Embed(
                title=f"{team_name} ({team_code}) Roster:",
                description=f"```\n{roster_display}\n```",
                color=team_color
            )

            if team_logo_url:
                embed.set_thumbnail(url=team_logo_url)
            
            embed.add_field(name="Owner", value=team_owner, inline=True)
            embed.add_field(name="GM", value=team_gm, inline=True)
            embed.add_field(name="Salary Cap", value=f"${team_cap}", inline=True)
            embed.add_field(name="Remaining Cap", value=f"${team_rmn_cap}", inline=True)
            embed.set_footer(text=f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            # Send embed to the roster channel
            await roster_channel.send(embed=embed)

    @commands.slash_command(guild_ids=[config.lol_server], description="Manually print rosters")
    @commands.has_role("Bot Guy", "League Ops")
    async def print_rosters(self, ctx):
        await ctx.defer()
        await self._print_rosters()
        await ctx.respond("Rosters have been posted", ephemeral=True)

def setup(bot):
    bot.add_cog(Roster(bot))
