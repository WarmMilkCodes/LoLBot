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
        await ctx.defer(ephemeral=True)

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
                queue_type = rank.get('queue_type', 'Unknown').replace('_', ' ').capitalize()
                tier = rank.get('tier', 'Unknown').capitalize()
                division = rank.get('division', 'Unknown').upper()

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
            for rank, names in ranks.items():
                names_str = ", ".join(names)
                
                # Split the names into multiple fields if the string is too long
                while len(names_str) > 1024:
                    # Find a place to split before the limit
                    split_point = names_str[:1024].rfind(", ")
                    if split_point == -1:  # If no comma is found, force split
                        split_point = 1024
                    
                    # Add the part that fits into the embed
                    embed.add_field(name=f"{queue_type} - {rank}", value=names_str[:split_point], inline=False)
                    
                    # Remove the part that was added to the embed
                    names_str = names_str[split_point + 2:]  # +2 to remove the comma and space
                
                # Add any remaining names to the embed
                embed.add_field(name=f"{queue_type} - {rank}", value=names_str, inline=False)

        await ctx.respond(embed=embed, ephemeral=True)

def setup(bot):
    bot.add_cog(RankCog(bot))
