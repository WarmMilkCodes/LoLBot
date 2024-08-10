import discord
from discord.ext import commands
from datetime import datetime
import pytz
import dbInfo
import config
import logging

logger = logging.getLogger('lol_log')

lol_server_id = config.lol_server
submission_log_channel_id = config.submission_log_channel  # Ensure this is in your config

class ApplicationButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Click here to fill out the intent form", style=discord.ButtonStyle.red, custom_id="Intent Form")
    async def report_button_press(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_message("The form has been sent to your inbox", ephemeral=True)
        guild = interaction.guild
        questions = ["Do you intend on playing this season?", "Are you interested in joining the Development team?", "Are you interested in joining the Production team?"]
        notes = ["If you click No, you will be a spectator.", "This includes helping in website development, discord bots, and the use of APIs.", "This includes being a caster, commentator, broadcasting games on stream nights, and/or creating graphics."]
        responses = []
        
        lol_description = "**Thank you for submitting the intent form for UR League of Legends**\n\nIf you need to change any of your responses, please click on the intent form button again to resubmit"

        # Collecting responses for general questions
        for x in range(len(questions)):
            view = ButtonOptions()
            embed = discord.Embed(title=f"Question {x + 1}/{len(questions)}", description=f"{questions[x]}\n\n{notes[x]}", color=discord.Color.blue())
            message = await interaction.user.send(embed=embed, view=view)
            await view.wait()
            responses.append(view.value)
            embed = discord.Embed(title=f"Question {x + 1}/{len(questions)}", description=f"{questions[x]}\n\n{notes[x]}", timestamp=datetime.now(pytz.timezone('America/New_York')), color=discord.Color.blue())
            embed.set_footer(text=f"Answered: {view.value}")
            await message.edit(embed=embed, view=None)

        # Riot ID Submission
        embed = discord.Embed(title="Riot ID Submission", description="Please provide your Riot ID details below:", color=discord.Color.blue())
        riot_id_form = RiotIDForm()
        await interaction.user.send(embed=embed, view=riot_id_form)

        await riot_id_form.wait()  # Wait until the form is submitted
        riot_game_name = riot_id_form.game_name.value
        riot_tag_line = riot_id_form.tag_line.value

        # Final message after form submission
        if guild.id == lol_server_id:
            embed = discord.Embed(title="Intent Form Complete", description=lol_description, color=discord.Color.blue())
        
        await interaction.user.send(embed=embed)
        logger.info(f"These are the responses: {responses}")

        # Set time for database entry                        
        dateTimeObj = datetime.now()
        dateObj = dateTimeObj.date()
        dateStr = dateObj.strftime("%b %d %Y")

        # Debug: Print database connection and collection info
        logger.info(f"Database Info: {dbInfo}")

        # Debug: Print the collection name
        logger.info(f"Using collection: {dbInfo.lol_intent_collection.name}")

        # Checks if user is in the database, if they are updates, if not adds them
        if guild.id == lol_server_id:
            result = dbInfo.lol_intent_collection.find_one_and_update(
                {"ID": interaction.user.id},
                {"$set":
                    {
                        "User": str(interaction.user),
                        "Playing": responses[0],
                        "Development Team": responses[1],
                        "Production Team": responses[2],
                        "Riot Game Name": riot_game_name,
                        "Riot Tag Line": riot_tag_line,
                        "Completed On": dateStr
                    }
                },
                upsert=True,
                return_document=True
            )

            logger.info(f"Database update result: {result}")

            lol_missing_intent = discord.utils.get(guild.roles, name="Missing Intent Form")
            lol_free_agent = discord.utils.get(guild.roles, name="Free Agents")
            lol_spectator = discord.utils.get(guild.roles, name="Spectator")
            lol_member = discord.utils.get(guild.roles, name="Member")

            if responses[0] == "Yes":
                await interaction.user.add_roles(lol_free_agent, lol_member)
                await interaction.user.remove_roles(lol_missing_intent)
            if responses[0] == "No":
                await interaction.user.remove_roles(lol_missing_intent, lol_free_agent)
                await interaction.user.add_roles(lol_spectator, lol_member)

            logger.info(f"{interaction.user.name}'s LoL intent form has been entered into the database.")
        else:
            logger.error("Unable to submit intent form to database")

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


class RiotIDForm(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

        self.game_name = discord.ui.InputText(label="Game Name", placeholder="Enter your game name", min_length=3, max_length=16)
        self.tag_line = discord.ui.InputText(label="Tag Line", placeholder="Enter your tag line", min_length=3, max_length=6)

        self.add_item(self.game_name)
        self.add_item(self.tag_line)

    @discord.ui.button(label="Submit", style=discord.ButtonStyle.blurple, custom_id="SubmitRiotID")
    async def submit_button_press(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_message("Riot ID successfully submitted.", ephemeral=True)
        self.stop()


class Application(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.persistent_views_added = False

    @commands.slash_command(guild_ids=[config.lol_server], description="Intent Form Button")
    @commands.has_any_role("Commissioner", "Bot Guy")
    async def intent_button(self, ctx):
        view = ApplicationButton()  # Create the ApplicationButton view
        await ctx.send(view=view)
        await view.wait()

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.persistent_views_added:
            self.bot.add_view(ApplicationButton())  # Make sure the button is persistent
            self.persistent_views_added = True
            logger.info("Persistent view added")


def setup(bot):
    bot.add_cog(Application(bot))
