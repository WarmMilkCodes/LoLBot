import config, dbInfo, discord, logging
from discord.ext import commands
from discord.commands import Option

logger = logging.getLogger('lol_log')

class StaffCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(description="Get player rank info")
    @commands.has_permissions(administrator=True)
    async def get_rank(self, ctx, user: Option(discord.Member)):
        user_data = dbInfo.player_collection.find_one({"discord_id":user.id})

        if not user_data:
            await ctx.respond(f"No data found for {user.display_name}.")
            logger.warning(f"No data found for {user.display_name}.")
            return
        
        rank_info = user_data('rank_info', [])
        if not rank_info:
            await ctx.respond(f"No rank information available for {user.display_name}")
            logger.info(f"No rank information available for {user.display_name}")
            return
        
        embed = discord.Embed(title=f"Rank Information for {user.display_name}", color=discord.Color.blue())

        for rank in rank_info:
            queue_type = rank.get('queue_type', 'Unknown Queue')
            tier = rank.get('tier', 'Unknown Tier')
            division = rank.get('division', 'Unknown Division')
            embed.add_field(name=queue_type, value=f"{tier} {division}", inline=False)

        await ctx.respond(embed=embed, ephemeral=True)
        logger.info(f"Rank information for {user.display_name} sent to {ctx.author.display_name}")

def setup(bot):
    bot.add_cog(StaffCommands(bot))
    logger.info("StaffCog setup completed.")