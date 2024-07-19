import discord
import logging
from discord.ext import commands
from discord.commands import Option
import config
import dbInfo
import pandas as pd
import io

logger = logging.getLogger('lol_log')

GUILD_IDS = config.GUILD_IDS

class StaffCog(commands.Cog):
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
            division = rank.get('division', 'Unknown Division').upper()
            embed.add_field(name=queue_type, value=f"{tier} {division}", inline=False)

        await ctx.respond(embed=embed)
        logger.info(f"Rank information for {user.display_name} sent, requested by {ctx.author.display_name}")

    @commands.slash_command(GUILD_IDS, description="Adds 'Missing Intent Form' role to all users")
    @commands.has_any_role("Bot Guy", "United Rogue Owner", "Commissioner")
    async def add_missing_intent_role(self, ctx: discord.ApplicationContext):
        role_name = "Missing Intent Form"
        role = discord.utils.get(ctx.guild.roles, name=role_name)

        if not role:
            await ctx.respond(f"Role '{role_name}' not found.", ephemeral=True)
            logger.error(f"Role '{role_name}' not found.")
            return
            
        count = 0
        for member in ctx.guild.members:
            if not member.bot and role not in member.roles:
                await member.add_roles(role)
                count += 1

        await ctx.respond(f"Role '{role_name}' has been assigned to {count} members.", ephemeral=True)
        logger.info(f"Role '{role_name}' added to {count} members by {ctx.author.display_name}")

    @commands.slash_command(GUILD_IDS, description="Export all player names and their ranks")
    @commands.has_permissions(administrator=True)
    async def export_player_ranks(self, ctx):
        data = []
        for player in dbInfo.player_collection.find():
            discord_id = player.get("discord_id")
            player_name = player.get("discord_name", "Unknown")
            rank_info = player.get("rank_info", [])
            ranks = ", ".join(
                [f"{rank.get('queue_type', 'Unknown Queue').replace('_', ' ').title()} - "
                 f"{rank.get('tier', 'Unknown Tier').capitalize()} "
                 f"{rank.get('division', 'Unknown Division').upper()}" 
                 for rank in rank_info]
            )
            data.append({"Player Name": player_name, "Ranks":ranks})

        df = pd.DataFrame(data)
        with io.BytesIO() as output:
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Player Ranks')
                writer.save()
            output.seek(0)
            file = discord.File(output, filename="player_ranks.xlsx")
            await ctx.respond("Here is the spreadsheet with player ranks:", file=file)

        logger.info(f"Exported player ranks spreadsheet requested by {ctx.author.display_name}")


def setup(bot):
    bot.add_cog(StaffCog(bot))
    logger.info("StaffCog setup completed.")
