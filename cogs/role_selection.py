import discord
from discord.ext import commands
from app import dbInfo, config
import logging

logger = logging.getLogger('role_log')

class RoleSelectionView(discord.ui.View):
    def __init__(self, bot, log_channel_id):
        super().__init__(timeout=None)
        self.bot = bot
        self.log_channel_id = log_channel_id  # Channel where role changes will be logged

    async def assign_role(self, interaction, role_name):
        member = interaction.user
        guild = interaction.guild
        
        # Get the role
        role = discord.utils.get(guild.roles, name=role_name)

        # Check if the role exists
        if not role:
            await interaction.response.send_message(f"Role '{role_name}' not found.", ephemeral=True)
            return

        # Remove existing roles
        role_names = ["Top", "JG", "Mid", "ADC", "Sup"]
        roles_to_remove = [discord.utils.get(guild.roles, name=role_name) for role_name in role_names]
        for role_to_remove in roles_to_remove:
            if role_to_remove and role_to_remove in member.roles:
                await member.remove_roles(role_to_remove)

        # Assign the new role
        await member.add_roles(role)
        logger.info(f"Assigned {role_name} role to {member.name}")

        # Update the database
        dbInfo.player_collection.update_one(
            {"discord_id": member.id},
            {"$set": {"in_game_role": role_name}},
            upsert=True
        )
        logger.info(f"Updated database for {member.name} with role {role_name}")

        # Log role change in the log channel
        log_channel = interaction.guild.get_channel(self.log_channel_id)
        if log_channel:
            await log_channel.send(f"{member.mention} updated their in-game role to **{role_name}**")

        # Confirm to the user
        await interaction.response.send_message(f"You have been assigned the {role_name} role!", ephemeral=True)

    @discord.ui.button(label="Top", style=discord.ButtonStyle.primary)
    async def top_role(self, button: discord.ui.Button, interaction: discord.Interaction):
        await self.assign_role(interaction, "Top")

    @discord.ui.button(label="JG", style=discord.ButtonStyle.primary)
    async def jg_role(self, button: discord.ui.Button, interaction: discord.Interaction):
        await self.assign_role(interaction, "JG")

    @discord.ui.button(label="Mid", style=discord.ButtonStyle.primary)
    async def mid_role(self, button: discord.ui.Button, interaction: discord.Interaction):
        await self.assign_role(interaction, "Mid")

    @discord.ui.button(label="ADC", style=discord.ButtonStyle.primary)
    async def adc_role(self, button: discord.ui.Button, interaction: discord.Interaction):
        await self.assign_role(interaction, "ADC")

    @discord.ui.button(label="Sup", style=discord.ButtonStyle.primary)
    async def sup_role(self, button: discord.ui.Button, interaction: discord.Interaction):
        await self.assign_role(interaction, "Sup")


class RoleSelectionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.persistent_views_added = False

    @commands.slash_command(guild_ids=[config.lol_server], description="Post the role selection buttons")
    @commands.has_role("Bot Guy")
    async def post_role_selection(self, ctx):
        view = RoleSelectionView(self.bot, config.role_log_channel)  # Assuming role_log_channel is in your config
        await ctx.send("Select your in-game role:", view=view)

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.persistent_views_added:
            self.bot.add_view(RoleSelectionView(self.bot, config.role_log_channel))  # Make the view persistent
            self.persistent_views_added = True
            logger.info("Persistent view added for role selection")


def setup(bot):
    bot.add_cog(RoleSelectionCog(bot))
