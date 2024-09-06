import discord
from discord.ext import commands
from discord.ui import Button, View
import app.dbInfo as dbInfo  # Assuming you're using a module named dbInfo for your database
from app.config import lol_server

class RoleSelectionView(View):
    def __init__(self, ctx, log_channel_id):
        super().__init__(timeout=None)  # No timeout for persistent buttons
        self.ctx = ctx  # Pass the context to the view
        self.log_channel_id = log_channel_id  # Log channel ID to post role updates

    async def remove_existing_roles(self, user, guild):
        role_names = ["Top", "JG", "Mid", "ADC", "Sup"]
        roles_to_remove = [discord.utils.get(guild.roles, name=role_name) for role_name in role_names]

        # Remove any existing roles in the defined list
        for role in roles_to_remove:
            if role in user.roles:
                await user.remove_roles(role)

    async def update_role_in_db(self, user, role_name):
        # Assuming you store the player's info in the 'player_collection' using 'discord_id'
        dbInfo.player_collection.update_one(
            {"discord_id": user.id},  # Find the player by their Discord ID
            {"$set": {"in_game_role": role_name}}  # Update their in-game role
        )

    async def post_role_update(self, user, role_name):
        # Post the role update in the specified log channel
        log_channel = self.ctx.guild.get_channel(self.log_channel_id)
        if log_channel:
            await log_channel.send(f"{user.mention} updated their in-game role to **{role_name}**")

    async def assign_role(self, interaction, role_name):
        guild = self.ctx.guild

        role = discord.utils.get(guild.roles, name=role_name)

        if role:
            # Remove existing roles first
            await self.remove_existing_roles(interaction.user, guild)

            # Assign the new role
            await interaction.user.add_roles(role)
            # Update the role in the database
            await self.update_role_in_db(interaction.user, role_name)
            # Post the role update in the log channel
            await self.post_role_update(interaction.user, role_name)
            await interaction.response.send_message(f"You have been assigned the {role_name} role!", ephemeral=True)
        else:
            await interaction.response.send_message(f"Role '{role_name}' not found.", ephemeral=True)

    @discord.ui.button(label="Top", style=discord.ButtonStyle.primary)
    async def top_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.assign_role(interaction, "Top")

    @discord.ui.button(label="JG", style=discord.ButtonStyle.primary)
    async def jg_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.assign_role(interaction, "JG")

    @discord.ui.button(label="Mid", style=discord.ButtonStyle.primary)
    async def mid_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.assign_role(interaction, "Mid")

    @discord.ui.button(label="ADC", style=discord.ButtonStyle.primary)
    async def adc_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.assign_role(interaction, "ADC")

    @discord.ui.button(label="Sup", style=discord.ButtonStyle.primary)
    async def sup_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.assign_role(interaction, "Sup")

class RoleSelectionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(guild_ids=[lol_server], description="Post the in-game role selection message")
    @commands.has_role("Bot Guy")
    async def post_role_selection(self, ctx):
        log_channel_id = 1194430443362205767  # Replace with the log channel ID where updates should be posted
        view = RoleSelectionView(ctx, log_channel_id)  # Pass ctx to the view
        await ctx.send("Please select your in-game role:", view=view)

def setup(bot):
    bot.add_cog(RoleSelectionCog(bot))