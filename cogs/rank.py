import discord
import logging
from discord.ext import commands
import app.dbInfo as dbInfo

# Set up logging
logger = logging.getLogger('rank_log')
logging.basicConfig(level=logging.INFO)

class RankCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(description="Fetch and display ranks of all players.")
    async def fetch_ranks(self, ctx):
        await ctx.defer()

        # Dictionary to organize players by queue type and rank
        rank_dict = {}

        players = dbInfo.player_collection.find({})

        for player in players:
            player_name = player.get('name', 'Unknown')
            logger.info(f"Checking player: {player_name}")

            rank_info = player.get('rank_info')
            if not rank_info:
                logger.info(f"No rank_info found for player: {player_name}")
                continue  # Skip players with no rank_info

            logger.info(f"Found rank_info for player: {player_name}")

            for rank in rank_info:
                queue_type = rank.get('queue_type', 'Unknown').replace('_', ' ').title()
                tier = rank.get('tier')
                division = rank.get('division')

                logger.info(f"Player {player_name} - Queue: {queue_type}, Tier: {tier}, Division: {division}")

                if tier and division:  # Only proceed if both tier and division are available
                    rank_label = f"{tier.capitalize()} {division}"

                    if queue_type not in rank_dict:
                        rank_dict[queue_type] = {}

                    if rank_label not in rank_dict[queue_type]:
                        rank_dict[queue_type][rank_label] = [player_name]
                    else:
                        rank_dict[queue_type][rank_label].append(player_name)

        # Create the embed message
        embed = discord.Embed(title="Player Ranks", color=discord.Color.blue())

        for queue_type, ranks in rank_dict.items():
            description = ""
            for rank_label, players_list in ranks.items():
                players_str = ', '.join(players_list)
                description += f"**{rank_label}**: {players_str}\n"

            if description:
                embed.add_field(name=queue_type, value=description, inline=False)

        if not embed.fields:
            embed.description = "No players with rank information found."

        await ctx.respond(embed=embed)

def setup(bot):
    bot.add_cog(RankCog(bot))
