import asyncio
import discord
import logging
from discord.ext import commands
from discord.commands import Option
import app.config as config
import app.dbInfo as dbInfo

logger = logging.getLogger('alt_report')

class AltReport(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def validate_command_channel(self, ctx):
        """Check if the command is invoked in the correct channel."""
        if ctx.channel.id != config.alt_channel:
            alt_report_channel = ctx.guild.get_channel(config.alt_channel)
            await ctx.respond(f"This command can only be used in {alt_report_channel.mention}", ephemeral=True)
            return False
        return True

    @commands.slash_command(guild_ids=[config.lol_server], description="Report alt account")
    async def report_alt(self, ctx, game_name: Option(str, "Enter game name - do not include discriminator"), tag_line: Option(str, "Enter tag line (numbers only)")):
        try:
            if not await self.validate_command_channel(ctx):
                return
            
            embed = discord.Embed(
                title="Confirm Alt Account",
                description=f"You are reporting the following account: '{game_name}#{tag_line}'.\nIf it looks correct, confirm the report.",
                color=discord.Color.orange()
            )

            view = ReportConfirmationView(ctx, game_name, tag_line)
            await ctx.respond(embed=embed, view=view, ephemeral=True)
        
        except Exception as e:
            await ctx.respond(f"There was an error submitting your alt account: {e}", ephemeral=True)

class ReportConfirmationView(discord.ui.View):
    def __init__(self, ctx, game_name, tag_line):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.game_name = game_name
        self.tag_line = tag_line

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, button: discord.ui.Button, interaction: discord.Interaction):
        try:
            # Store the alt account as an object with game_name and tag_line
            alt_account = {
                "game_name": self.game_name,
                "tag_line": self.tag_line
            }

            dbInfo.player_collection.update_one(
                {"discord_id": self.ctx.author.id},
                {"$push": {
                    "alt_accounts": alt_account  # Append the alt account object
                }},
                upsert=True  # Create the document if it doesn't exist
            )

            await interaction.response.send_message(f"Report for `{self.game_name}#{self.tag_line}` has been confirmed.", ephemeral=True)
            logger.info(f"User {self.ctx.author} reported alt account: {self.game_name}#{self.tag_line}")
        
        except Exception as e:
            await interaction.response.send_message(f"Failed to confirm report due to: {e}", ephemeral=True)
            logger.error(f"Error updating database for alt report: {e}")

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_message(f"Report for `{self.game_name}#{self.tag_line}` has been cancelled.", ephemeral=True)
        logger.info(f"User {self.ctx.author} cancelled alt report for: {self.game_name}#{self.tag_line}")

# Adding the Cog to the bot
def setup(bot):
    bot.add_cog(AltReport(bot))