import discord, logging
from discord.ext import commands
import app.config as config
import app.dbInfo as dbInfo

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

            owner_name = team_owner if team_owner else ''
            gm_name = team_gm if team_gm else ''

            # Fetch active roster players from player collection
            roster_members = dbInfo.player_collection.find({"team": team, "active_roster":True})

            # Prepare the roster list
            roster_list = []

            for member in roster_members:
                discord_member = ctx.guild.get_member(member.get('discord_id'))
                salary = member.get('salary', 0)
                if discord_member:
                    roster_list.append(f"{discord_member.display_name} - ${salary}")

            # If no players show message
            roster_display = "\n".join(roster_list) if roster_list else "No players on roster."

            # Create an embed for the team roster
            embed = discord.Embed(
                title=f"{team_name} ({team_code}) Roster:",
                color=discord.Color.teal()
            )

            embed.add_field(name="Players", value=roster_display, inline=False)
            embed.add_field(name="Owner", value=owner_name, inline=True)
            embed.add_field(name="GM", value=gm_name, inline=True)
            embed.add_field(name="Salary Cap", value=f"${team_cap}", inline=True)
            embed.add_field(name="Cap Left", value=f"${team_rmn_cap}", inline=True)

            # Send embed to roster channel
            await roster_channel.send(embed=embed)

        await ctx.respond("Roster has been posted.", ephemeral=True)

def setup(bot):
    bot.add_cog(Roster(bot))