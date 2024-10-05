import discord
import logging
import app.config as config
import app.dbInfo as dbInfo
from discord.ext import commands
from discord.commands import Option

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
            
            reported_account = f"{game_name}#{tag_line}"
            embed = discord.Embed(
                title="Confirm Alt Account",
                description=f"You are reporting the following account: '{reported_account}'.\nIf it looks correct, confirm the report.",
                color=discord.Color.orange()
            )

            view = ReportConfirmationView(ctx, reported_account)
            await ctx.respond(embed=embed, view=view)
        
        except Exception as e:
            await ctx.respond(f"There was an error submitting your alt account: {e}", ephemeral=True)

class ReportConfirmationView(discord.ui.View):
    def __init__(self, ctx, reported_account):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.reported_account = reported_account

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, button: discord.Button, interaction: discord.Interaction):
        dbInfo.player_collection.update_one(
            {"discord_id": self.ctx.author.id},
            {"$push": {
                "alt_accounts": self.reported_account
            }},
            upsert=True
        )

        await interaction.response.edit_message(content=f"Report for `{self.reported_account}` has been confirmed.", embed=None, view=None)
        logger.info(f"User {self.ctx.author} reported alt account: {self.reported_account}")

    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
        # If the cancellation is clicked
        await interaction.response.edit_message(content=f"Report for `{self.reported_account}` has been cancelled.", embed=None, view=None)

# Adding the Cog to the bot
def setup(bot):
    bot.add_cog(AltReport(bot))