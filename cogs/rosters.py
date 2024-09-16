import discord
import logging
from discord.ext import commands
import app.config as config
import app.dbInfo as dbInfo
from tabulate import tabulate
import re

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

    @commands.slash_command(guild_ids=[config.lol_server], description="Prints roster embeds")
    @commands.has_role("Bot Guy")
    async def print_rosters(self, ctx):
        await ctx.defer()

        # Get roster channel
        roster_channel = ctx.guild.get_channel(config.rosters_channel)

        if not roster_channel:
            return await ctx.respond("Roster channel not found", ephemeral=True)

        # Fetch all teams from team collection with logos (active teams)
        teams = dbInfo.team_collection.find({"logo": {"$exists": True}}).sort("team_name", 1)

        # Build embed for each team
        for team in teams:
            team_name = team["team_name"]
            team_code = team["team_code"]
            team_logo_path = team.get("logo", None)

            team_owner = team.get("owner", "N/A")
            team_gm = team.get("gm", "N/A")
            team_color_name = team.get("color", "Blue")
            team_color = DISCORD_COLOR_MAP.get(team_color_name, discord.Color.blue())
            team_cap = team.get("salary_cap", 610)
            team_rmn_cap = team.get("remaining_cap", 610)

            # Convert local path to URL or fall back to none
            team_logo_url = f"{base_logo_url}{team_logo_path}" if team_logo_path else None

            # Fetch active roster players for this team
            roster_list = dbInfo.player_collection.find({"team": team_code, "active_roster": True})

            # Prepare player data for tabulate
            players_table = []
            for index, player in enumerate(roster_list, start=1):
                # Remove team prefixes from player names
                player_name = player['display_name'].replace(f'{team_code} | ', '')
                player_salary = player.get('salary', 'TBD')

                # Check if the player is a reserve player
                if player.get('reserve_player', False):
                    roster_number = "R"  # Mark reserve players with "R"
                else:
                    roster_number = str(index)

                # Append player data to the table
                players_table.append([roster_number, player_name, player_salary])

            # Use tabulate to display roster neatly in the embed with # header
            roster_display = tabulate(players_table, headers=["#", "Player", "Salary"], tablefmt="plain") if players_table else "No players on roster"

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
            embed.set_footer(text="Last updated")

            # Send embed to the roster channel
            await roster_channel.send(embed=embed)

        await ctx.respond("Roster has been posted.", ephemeral=True)

def setup(bot):
    bot.add_cog(Roster(bot))
