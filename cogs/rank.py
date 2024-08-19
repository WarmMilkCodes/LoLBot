import discord
import logging
from discord.ext import commands
import app.dbInfo as dbInfo

# Set up logging
logger = logging.getLogger('rank_log')
logging.basicConfig(level=logging.INFO)

# Update the rank order to match the capitalization in the database
RANK_ORDER = ["IRON", "BRONZE", "SILVER", "GOLD", "PLATINUM", "EMERALD", "DIAMOND", "MASTER", "GRANDMASTER", "CHALLENGER"]
DIVISION_ORDER = ["I", "II", "III", "IV", "V"]

class RankCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(description="Fetch and display ranks of all players.")
    async def fetch_ranks(self, ctx):
        await ctx.defer()

        # Dictionary to organize players by queue type and rank
        rank_dict = {}
        total_ranked_players = 0

        # Only select players who have not left the server
        players = dbInfo.player_collection.find({"left_at": None})

        for player in players:
            player_name = player.get('name', 'Unknown')
            logger.info(f"Checking player: {player_name}")

            rank_info = player.get('rank_info')
            if not rank_info:
                logger.info(f"No rank_info found for player: {player_name}")
                continue  # Skip players with no rank_info

            logger.info(f"Found rank_info for player: {player_name}")

            for rank in rank_info:
                queue_type = rank.get('queue_type')

                # Only process 'RANKED_SOLO_5x5'
                if queue_type != "RANKED_SOLO_5x5":
                    logger.info(f"Skipping {queue_type} for player: {player_name}")
                    continue

                # Increment the total ranked players count
                total_ranked_players += 1

                tier = rank.get('tier')
                division = rank.get('division')

                logger.info(f"Player {player_name} - Queue: {queue_type}, Tier: {tier}, Division: {division}")

                if tier and division:  # Only proceed if both tier and division are available
                    rank_label = f"{tier} {division}"

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

            # Sort the ranks according to RANK_ORDER and DIVISION_ORDER
            sorted_ranks = sorted(
                ranks.keys(),
                key=lambda x: (RANK_ORDER.index(x.split()[0]), DIVISION_ORDER.index(x.split()[1]))
            )

            for rank_label in sorted_ranks:
                players_list = ranks[rank_label]
                players_str = ', '.join(players_list)
                description += f"**{rank_label}**: {players_str}\n"

            if description:
                embed.add_field(name=queue_type.replace('_', ' ').title(), value=description, inline=False)

        if not embed.fields:
            embed.description = "No players with rank information found."

        # Set the footer with the total count of ranked players
        embed.set_footer(text=f"Total Ranked Players (Ranked Solo 5x5): {total_ranked_players}")

        await ctx.respond(embed=embed)

def setup(bot):
    bot.add_cog(RankCog(bot))
