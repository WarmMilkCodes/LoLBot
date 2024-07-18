import discord
import logging
from discord.ext import commands
from discord.commands import Option
import config
import dbInfo

logger = logging.getLogger('lol_log')

class RankInfoCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(description="Get user's rank information")
    @commands.has_permissions(administrator=True)
    async def get_rank(self, ctx: discord.ApplicationContext, user: Option(discord.Member, "Select a user")):
        user_data = dbInfo.player_collection.find_one({"discord_id": user.id})

        if not user_data:
            await ctx.respond(f"No data found for user {user.display_name}", ephemeral=True)
            logger.warning(f"No data found for user {user.display_name}")
            return

        rank_info = user_data.get('rank_info', []) 
        if not rank_info:
            await ctx.respond(f"No rank information available for user {user.display_name}", ephemeral=True)
            logger.info(f"No rank information available for user {user.display_name}")
            return

        embed = discord.Embed(title=f"Rank Information for {user.display_name}", color=discord.Color.blue())

        for rank in rank_info:
            queue_type = rank.get('queue_type', 'Unknown Queue').replace('_', ' ').title()
            tier = rank.get('tier', 'Unknown Tier').capitalize()
            division = rank.get('division', 'Unknown Division').capitalize()
            embed.add_field(name=queue_type, value=f"{tier} {division}", inline=False)

        await ctx.respond(embed=embed)
        logger.info(f"Rank information for {user.display_name} sent to {ctx.author.display_name}")

def setup(bot):
    bot.add_cog(RankInfoCog(bot))
    logger.info("RankInfoCog setup completed.")
