import discord
from discord.ext import commands
from tabulate import tabulate
import app.dbInfo as dbInfo
import app.config as config

class RankCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(guild_ids=[config.lol_server], description="Fetch and display player ranks")
    async def fetch_ranks(self, ctx):
        await ctx.defer()

        players = dbInfo.player_collection.find({})

        # Prepare a table with headers for tabulate
        table_data = [["Player", "Queue Type", "Rank"]]

        for player in players:
            name = player.get('name', 'Unknown')
            rank_info = player.get('rank_info', [])

            for rank in rank_info:
                queue_type = rank.get('queue_type', 'Unknown').replace('_', ' ').title()
                tier = rank.get('tier', 'Unknown').title()
                division = rank.get('division', 'Unknown').title()
                table_data.append([name, queue_type, f"{tier} {division}"])

        # Format the table using tabulate
        table = tabulate(table_data, headers="firstrow", tablefmt="pretty")

        # Split the table into chunks to fit Discord's character limit
        chunks = [table[i:i + 1024] for i in range(0, len(table), 1024)]

        embed = discord.Embed(title="Player Ranks", color=discord.Color.blue())

        for i, chunk in enumerate(chunks):
            embed.add_field(name=f"Ranks {i + 1}", value=f"```{chunk}```", inline=False)

        await ctx.respond(embed=embed, ephemeral=True)

def setup(bot):
    bot.add_cog(RankCog(bot))
