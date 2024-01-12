import requests, config, dbInfo
import discord
from discord.ext import commands
from discord.commands import Option

class RiotCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(description="Submit Riot ID")
    @commands.has_permissions(administrator=True)
    async def riot_id_submission(self, ctx):
        await ctx.respond("On it!", ephemeral=True)
        # Create button for users to click
        button = discord.ui.Button(label="Submit Riot ID", style=discord.ButtonStyle.blurple, custom_id="submit_riot_id")
        view = discord.ui.View()
        view.add_item(button)
        await ctx.send("Click the button to submit your Riot ID.", view=view)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.data.get('custom_id') == "submit_riot_id":
            try:
                modal = RiotIDModal(self.bot)
                await interaction.response.send_modal(modal)
            except discord.errors.InteractionResponded:
                pass

class RiotIDModal(discord.ui.Modal):
    def __init__(self, bot):
        super().__init__(title="Riot ID Submission")
        self.bot = bot

        self.game_name = discord.ui.InputText(label="Game Name", placeholder="Enter your game name", min_length=3, max_length=16)
        self.tag_line = discord.ui.InputText(label="Tag Line", placeholder="Enter your tag line. Do not include '#'.", min_length=2, max_length=8)

        self.add_item(self.game_name)
        self.add_item(self.tag_line)

    async def callback(self, interaction: discord.Interaction):
        # Update the user's document in player collection
        update_result = dbInfo.player_collection.update_one(
            {"discord_id": interaction.user.id}, 
            {"$set": {"game_name": self.game_name.value, "tag_line": self.tag_line.value}}
        )

        if update_result.modified_count:
            await interaction.response.send_message("Riot ID successfully updated.", ephemeral=True)
            riot_id_log_channel = self.bot.get_channel(config.riot_id_log_channel)
            await riot_id_log_channel.send(f"{interaction.user.mention} updated their Riot ID: {self.game_name.value}#{self.tag_line.value}")
        else:
            await interaction.response.send_message("Riot ID not updated.", ephemeral=True)

def setup(bot):
    bot.add_cog(RiotCog(bot))
