import discord
from discord.ext import commands
import app.dbInfo as dbInfo
import app.config as config
from collections import defaultdict

class RankCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(guild_ids=[config.lol_server], description="Fetch and display player ranks")
    async def fetch_ranks(self, ctx):
        await ctx.defer()

        players = dbInfo.player_collection.find({})

        # Dictionary to hold players organized by queue type and rank
        rank_dict = defaultdict(lambda: defaultdict(list))

        for player in players:
            name = player.get('name', 'Unknown')
            rank_info = player.get('rank_info', [])

            # Skip players without rank_info
            if not rank_info:
                continue

            for rank in rank_info:
                queue_type = rank.get('queue_type', 'Unknown').replace('_', ' ').title()
                tier = rank.get('tier', 'Unknown').title()
                division = rank.get('division', 'Unknown').title()

                # Add the player to the appropriate queue type and rank list
                rank_dict[queue_type][f"{tier} {division}"].append(name)

        # If no players have rank_info, return a message instead of an empty embed
        if not rank_dict:
            await ctx.respond("No players with rank information found.", ephemeral=True)
            return

        # Build the embed
        embed = discord.Embed(title="Player Ranks", color=discord.Color.blue())

        # Populate the embed with rank information
        for queue_type, ranks in rank_dict.items():
            rank_strings = []
            for rank, names in ranks.items():
                # Join player names with commas for readability
                names_str = ", ".join(names)
                rank_strings.append(f"**{rank}:** {names_str}")
            # Join all ranks for the queue type into a single string
            queue_type_info = "\n".join(rank_strings)
            embed.add_field(name=queue_type, value=queue_type_info, inline=False)

        await ctx.respond(embed=embed, ephemeral=True)

def setup(bot):
    bot.add_cog(RankCog(bot))
