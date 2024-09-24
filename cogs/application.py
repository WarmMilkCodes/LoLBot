import discord
from discord.ext import commands
from datetime import datetime
import pytz
from app import config, dbInfo
import logging
import asyncio, re
from utils import update_nickname

logger = logging.getLogger('lol_log')

lol_server_id = config.lol_server
submission_log_channel_id = config.submission_log_channel  # Ensure this is in your config
game_name_image = "https://media.discordapp.net/attachments/1171263861240889405/1271892784315498556/gamename.png?ex=66b8fdf6&is=66b7ac76&hm=74fdbff2be50b7e43ad8e6aad38a29a0dad698badb361572e8ce54758c83abf4&=&format=webp&quality=lossless&width=960&height=540"
tagline_image = "https://media.discordapp.net/attachments/1171263861240889405/1271892783892008971/tagline.png?ex=66b8fdf6&is=66b7ac76&hm=d019a8ae1a58ab3344c9776465e5c74f4e5d37324cd147cff4ca26e180fb9f68&=&format=webp&quality=lossless&width=960&height=540"

class ApplicationButton(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Click here to fill out the intent form", style=discord.ButtonStyle.red, custom_id="Intent Form")
    async def report_button_press(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_message("The form has been sent to your inbox", ephemeral=True)
        questions = [
            "Do you intend on playing this season?",
            "Are you interested in joining the Development team?",
            "Are you interested in joining the Production team?"
        ]
        notes = [
            "If you click No, you will be a spectator.",
            "This includes helping in website development, discord bots, and the use of APIs.",
            "This includes being a caster, commentator, broadcasting games on stream nights, and/or creating graphics."
        ]
        responses = []
        
        lol_description = "**Thank you for submitting the intent form for UR League of Legends**\n\nIf you need to change any of your responses, please click on the intent form button again to resubmit"

        # Collect 

        # Collecting responses for general questions
        for x in range(len(questions)):
            view = ButtonOptions()
            embed_description = f"{questions[x]}"
            if notes[x]:
                embed_description += f"\n\n{notes[x]}"
            embed = discord.Embed(title=f"Question {x + 1}/{len(questions)}", description=embed_description, color=discord.Color.blue())
            message = await interaction.user.send(embed=embed, view=view)
            await view.wait()
            responses.append(view.value)
            embed = discord.Embed(title=f"Question {x + 1}/{len(questions)}", description=embed_description, timestamp=datetime.now(pytz.timezone('America/New_York')), color=discord.Color.blue())
            embed.set_footer(text=f"Answered: {view.value}")
            await message.edit(embed=embed, view=None)

        # Default values for Riot game name and tag line
        riot_game_name = None
        riot_tag_line = None
        
        # Check if user has existing Riot ID in database
        existing_player_data = dbInfo.intent_collection.find_one({"ID": interaction.user.id})
        if existing_player_data:
            riot_game_name = existing_player_data.get('game_name')
            riot_tag_line = existing_player_data.get('tag_line')

        # If they intend to player ask for Riot ID info
        if responses[0] == 'Yes':
            # Asking for Riot Game Name
            await interaction.user.send(embed=discord.Embed(
                title="Please provide your Riot Game Name (do not include tag line)",
                description="Enter your Riot Game Name below:",
                color=discord.Color.blue()
            ).set_image(url=game_name_image))

            # Waiting for user's response
            try:
                riot_game_name_msg = await self.bot.wait_for(
                    "message",
                    check=lambda m: m.author == interaction.user and isinstance(m.channel, discord.DMChannel),
                    timeout=60  # Wait for up to 60 seconds
                )
                riot_game_name = riot_game_name_msg.content
                logger.info(f"Received Riot Game Name: {riot_game_name}")
            except asyncio.TimeoutError:
                await interaction.user.send("You took too long to respond. Please try again.")
                logger.warning("Timeout occurred while waiting for the Riot Game Name.")
                return

            # Asking for Riot Tag Line
            await interaction.user.send(embed=discord.Embed(
                title="Please provide your Riot Tag Line (do not include game name or #)",
                description="Enter your Riot Tag Line below.",
                color=discord.Color.blue()
            ).set_image(url=tagline_image))

            # Waiting for user's response
            try:
                riot_tag_line_msg = await self.bot.wait_for(
                    "message",
                    check=lambda m: m.author == interaction.user and isinstance(m.channel, discord.DMChannel),
                    timeout=60  # Wait for up to 60 seconds
                )
                riot_tag_line = riot_tag_line_msg.content
                logger.info(f"Received Riot Tag Line: {riot_tag_line}")
            except asyncio.TimeoutError:
                await interaction.user.send("You took too long to respond. Please try again.")
                logger.warning("Timeout occurred while waiting for the Riot Tag Line.")
                return
            
            # Update prefix to FA
            await update_nickname(interaction.user, "FA")

        # Final message after form submission
        embed = discord.Embed(title="Intent Form Complete", description=lol_description, color=discord.Color.blue())
        await interaction.user.send(embed=embed)
        logger.info(f"These are the responses: {responses}")

        # Assign roles based on responses
        # Get roles
        member_role = discord.utils.get(interaction.guild.roles, name="Member")
        free_agent_role = discord.utils.get(interaction.guild.roles, name="Free Agents")
        spectator_role = discord.utils.get(interaction.guild.roles, name="Spectator")
        missing_intent_role = discord.utils.get(interaction.guild.roles, name="Missing Intent Form")

        # Ensure roles exist
        if not all([member_role, free_agent_role, spectator_role, missing_intent_role]):
            await interaction.user.send("Error: One or more roles are missing in the server.")
            return

        # Remove "Missing Intent Form" role
        if missing_intent_role in interaction.user.roles:
            await interaction.user.remove_roles(missing_intent_role)

        # Assign roles based on the intent to play
        if responses[0] == "Yes":
            # User intends to play this season
            await interaction.user.add_roles(free_agent_role, member_role)
            if spectator_role in interaction.user.roles:
                await interaction.user.remove_roles(spectator_role)
        else:
            # User does not intend to play this season
            await interaction.user.add_roles(spectator_role, member_role)
            if free_agent_role in interaction.user.roles:
                await interaction.user.remove_roles(free_agent_role)
            
            await update_nickname(interaction.user, "S")

        logger.info(f"Roles updated for {interaction.user.name}: Playing - {responses[0]}")
        
        # Set time for database entry                        
        dateTimeObj = datetime.now()
        dateObj = dateTimeObj.date()
        dateStr = dateObj.strftime("%b %d %Y")

        #Prepare fields to update in database
        update_fields = {
            "User": str(interaction.user),
            "Playing": responses[0],
            "Development Team": responses[1],
            "Production Team": responses[2],
            "Completed On": dateStr
        }
        

         # Only update Riot Game Name and Tag Line if the user is playing
        if responses[0] == 'Yes':
            update_fields["Riot Game Name"] = riot_game_name
            update_fields["Riot Tag Line"] = riot_tag_line

        # Update the intent collection
        result = dbInfo.intent_collection.find_one_and_update(
            {"ID": interaction.user.id},
            {"$set": update_fields},
            upsert=True,
            return_document=True
        )

        # If they are playing, also update the player collection with Riot Game Name and Tag Line
        if responses[0] == 'Yes':
            dbInfo.player_collection.find_one_and_update(
                {"discord_id": interaction.user.id},
                {"$set": {
                    "game_name": riot_game_name,
                    "tag_line": riot_tag_line
                }},
                upsert=True
            )

        logger.info(f"Database update result: {result}")

        # Send submission to log channel
        submission_log_channel = self.bot.get_channel(submission_log_channel_id)
        if submission_log_channel:
            submission_embed = discord.Embed(
                title="New Intent Form Submission",
                description=f"**User:** {interaction.user.mention}\n"
                            f"**Playing this season:** {responses[0]}\n"
                            f"**Development Team Interest:** {responses[1]}\n"
                            f"**Production Team Interest:** {responses[2]}\n"
                            f"**Riot ID:** {riot_game_name}#{riot_tag_line}\n"
                            f"**Submitted On:** {dateStr}",
                color=discord.Color.green(),
                timestamp=datetime.now(pytz.timezone('America/New_York'))
            )
            submission_embed.set_footer(text=f"User ID: {interaction.user.id}")
            if interaction.user.avatar:
                submission_embed.set_thumbnail(url=interaction.user.avatar.url)

            await submission_log_channel.send(embed=submission_embed)

        # Logging Riot ID Submission
        riot_id_log_channel = self.bot.get_channel(config.riot_id_log_channel)
        if riot_id_log_channel:
            await riot_id_log_channel.send(f"{interaction.user.mention} updated their Riot ID: {riot_game_name}#{riot_tag_line}")

class ButtonOptions(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.value = None

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.green, custom_id="Yes Button")
    async def yes_button_press(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.stop()
        self.value = "Yes"

    @discord.ui.button(label="No", style=discord.ButtonStyle.red, custom_id="No Button")
    async def no_button_press(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.stop()
        self.value = "No"

class Application(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.persistent_views_added = False

    @commands.slash_command(guild_ids=[config.lol_server], description="Intent Form Button")
    @commands.has_any_role("Commissioner", "Bot Guy")
    async def intent_button(self, ctx):
        view = ApplicationButton(self.bot)  # Pass the bot instance to ApplicationButton
        await ctx.send(view=view)
        await view.wait()

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.persistent_views_added:
            self.bot.add_view(ApplicationButton(self.bot))  # Make sure the button is persistent
            self.persistent_views_added = True
            logger.info("Persistent view added")

def setup(bot):
    bot.add_cog(Application(bot))
