from discord.ext import commands
from tabulate import tabulate
import discord
import app.dbInfo as dbInfo
import pytz
from datetime import datetime

class RankCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(description="Retrieve and sort all players' ranks")
    @commands.has_permissions(administrator=True)
    async def get_sorted_ranks(self, ctx):
        await ctx.defer(ephemeral=True)

        # Fetch all players from the database
        players = list(dbInfo.player_collection.find({}))

        if not players:
            await ctx.respond("No players found in the database.", ephemeral=True)
            return

        # Prepare the data for sorting
        player_data = []
        for player in players:
            rank_info = player.get('rank_info')
            if rank_info:
                # Extract useful rank information
                tier = rank_info[0].get('tier', 'Unranked')
                division = rank_info[0].get('division', '')
                player_data.append([player['name'], tier, division])

        # Sort players by tier and division
        sorted_players = sorted(player_data, key=lambda x: (x[1], x[2]))

        if not sorted_players:
            await ctx.respond("No rank data available.", ephemeral=True)
            return

        # Create a table using tabulate
        table_headers = ["Player", "Tier", "Division"]
        table_value = "```" + tabulate(sorted_players, headers=table_headers, tablefmt="grid") + "```"

        # Create an embed to display the ranks
        embed = discord.Embed(title="Sorted Player Ranks", color=discord.Color.blue())
        embed.description = table_value
        embed.set_footer(text=f"Retrieved on {datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

        await ctx.respond(embed=embed, ephemeral=True)

def setup(bot):
    bot.add_cog(RankCog(bot))
