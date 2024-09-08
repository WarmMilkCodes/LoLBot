import discord
from discord.ext import commands
from app import dbInfo, config
import logging

logger = logging.getLogger('role_log')

class RoleSelectionView(discord.ui.View):
    def __init__(self, bot, log_channel_id):
        super().__init__(timeout=None)
        self.bot = bot
        self.log_channel_id = log_channel_id

    async def get_existing_roles(self, member, guild):
        """Retrieve the user's current roles from the allowed in-game roles list."""
        allowed_roles = ["Top", "JG", "Mid", "ADC", "Sup"]
        existing_roles = [role for role in member.roles if role.name in allowed_roles]
        return existing_roles

    async def assign_role(self, interaction, role_name):
        member = interaction.user
        guild = interaction.guild

        # Get the selected role
        new_role = discord.utils.get(guild.roles, name=role_name)

        # Check if the role exists
        if not new_role:
            await interaction.response.send_message(f"Role '{role_name}' not found.", ephemeral=True)
            return

        # Retrieve the current in-game roles the user has
        existing_roles = await self.get_existing_roles(member, guild)

        if len(existing_roles) >= 2:
            # User already has two roles, prevent assigning more
            await interaction.response.send_message(
                "You already have two roles assigned. Please remove one to assign a new role.", ephemeral=True)
            return

        # Add the new role if they have fewer than 2
        await member.add_roles(new_role)
        logger.info(f"Assigned {role_name} role to {member.name}")

        # Update the database with the new roles
        updated_roles = [role.name for role in (existing_roles + [new_role])]
        dbInfo.player_collection.update_one(
            {"discord_id": member.id},
            {"$set": {"in_game_roles": updated_roles}},  # Store both roles
            upsert=True
        )
        logger.info(f"Updated database for {member.name} with roles {updated_roles}")

        # Log role change in the log channel
        log_channel = interaction.guild.get_channel(self.log_channel_id)
        if log_channel:
            await log_channel.send(f"{member.mention} updated their in-game roles to: **{', '.join(updated_roles)}**")

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
        view = RoleSelectionView(self.bot, config.riot_id_log_channel)
        await ctx.send("Select your in-game role:", view=view)

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.persistent_views_added:
            self.bot.add_view(RoleSelectionView(self.bot, config.riot_id_log_channel))  # Make the view persistent
            self.persistent_views_added = True
            logger.info("Persistent view added for role selection")


def setup(bot):
    bot.add_cog(RoleSelectionCog(bot))
