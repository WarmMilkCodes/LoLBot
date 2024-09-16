import discord, logging
from discord.ext import commands
import app.config as config
import app.dbInfo as dbInfo
from tabulate import tabulate
import re

logger = logging.getLogger('__name__')

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
        
        # Fetch all teams from team collection
        teams = dbInfo.team_collection.find({"logo": {"$exists": True}})

        # Build embed for each team
        for team in teams:
            team_name = team.get("team_name")
            team_code = team.get("team_code")
            team_owner = team.get("owner")
            team_gm = team.get("gm")
            team_cap = team.get("salary_cap", 610)
            team_rmn_cap = team.get("remaining_cap", 610)
            #logo_url = team.get("logo")

            owner_name = team_owner if team_owner else ''
            gm_name = team_gm if team_gm else ''

            # Fetch active roster players from player collection
            roster_members = dbInfo.player_collection.find({"team": team_code, "active_roster":True})

                        # Prepare the roster list
            roster_list = []

            for member in roster_members:
                discord_member = ctx.guild.get_member(member.get('discord_id'))
                salary = member.get('salary', 0)
                
                if discord_member:
                    clean_name = re.sub(r"^[A-Z]{2,3} \| ", "", discord_member.display_name)
                    roster_list.append([clean_name, f"${salary}"])

            if roster_list:
                roster_display = tabulate(roster_list, headers=["Player", "Salary"], tablefmt="plain")
            else:
                roster_display = "No active players on roster"

            # Create an embed for the team roster
            embed = discord.Embed(
                title=f"{team_name} ({team_code}) Roster:",
                color=discord.Color.teal()
            )

            #embed.set_thumbnail(url=logo_url)
            embed.add_field(name="Roster", value=f"```\n{roster_display}\n```", inline=False)
            embed.add_field(name="Owner", value=owner_name, inline=True)
            embed.add_field(name="GM", value=gm_name, inline=True)
            embed.add_field(name="Salary Cap", value=f"${team_cap}", inline=True)
            embed.add_field(name="Cap Left", value=f"${team_rmn_cap}", inline=True)

            # Send embed to roster channel
            await roster_channel.send(embed=embed)

        await ctx.respond("Roster has been posted.", ephemeral=True)

def setup(bot):
    bot.add_cog(Roster(bot))