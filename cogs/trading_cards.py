import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont
import app.dbInfo as dbInfo
import app.config as config
import os
import requests
from io import BytesIO

class CardGenerator(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Helper function to load player data from the database
    async def get_player_info(self, player_id):
        return dbInfo.player_collection.find_one({"discord_id": player_id})

    # Helper function to determine peak rank from current and historical rank info
    def get_peak_rank(self, player_info):
        RANK_ORDER = {
            "IRON": 1, "BRONZE": 2, "SILVER": 3, "GOLD": 4, "PLATINUM": 5, 
            "EMERALD": 6, "DIAMOND": 7, "MASTER": 8, "GRANDMASTER": 9, "CHALLENGER": 10
        }
        DIVISION_ORDER = {"IV": 1, "III": 2, "II": 3, "I": 4}

        highest_rank = None
        highest_division = None

        # Function to update the highest rank
        def update_highest_rank(tier, division):
            nonlocal highest_rank, highest_division
            if tier is None or division is None:
                return

            if highest_rank is None or (
                RANK_ORDER.get(tier, 0) > RANK_ORDER.get(highest_rank, 0)
            ) or (
                RANK_ORDER.get(tier) == RANK_ORDER.get(highest_rank) and DIVISION_ORDER.get(division, 0) > DIVISION_ORDER.get(highest_division, 0)
            ):
                highest_rank = tier
                highest_division = division

        # Process current rank_info (if exists)
        rank_info_array = player_info.get('rank_info', [])
        for rank in rank_info_array:
            queue_type = rank.get('queue_type')
            if queue_type == "RANKED_SOLO_5x5":
                tier = rank.get('tier', None)
                division = rank.get('division', None)
                update_highest_rank(tier, division)

        # Process historical_rank_info (if exists)
        historical_rank_info = player_info.get('historical_rank_info', {})
        for date, rank_array in historical_rank_info.items():
            for rank in rank_array:
                queue_type = rank.get('queue_type')
                if queue_type == "RANKED_SOLO_5x5":
                    tier = rank.get('tier', None)
                    division = rank.get('division', None)
                    update_highest_rank(tier, division)

        if highest_rank:
            return f"{highest_rank.capitalize()} {highest_division.upper()}"
        return "N/A"

    # Function to generate the player card
    async def generate_card(self, player_name, avatar_image, peak_rank, team_code):
        # Load the card template
        card_template_path = 'card_template.png'  # Ensure the card template is in the bot's root directory
        template = Image.open(card_template_path)

        # Resize and paste the player's avatar image onto the template
        avatar_image = avatar_image.resize((300, 300))  # Resize to fit in the white space
        template.paste(avatar_image, (100, 150))  # Adjust the coordinates as needed

        # Initialize drawing on the template
        draw = ImageDraw.Draw(template)
        font = ImageFont.truetype('arial.ttf', 40)  # Ensure you have 'arial.ttf' in your directory

        # Add player name
        draw.text((120, 30), player_name, font=font, fill=(255, 255, 255))  # Adjust text coordinates

        # Add peak rank and team code
        draw.text((100, 500), f"Peak Rank: {peak_rank}", font=font, fill=(255, 255, 255))
        draw.text((100, 550), f"Team: {team_code}", font=font, fill=(255, 255, 255))

        # Save the final card image
        output_path = f'cards/{player_name}_card.png'
        if not os.path.exists('cards'):
            os.makedirs('cards')
        template.save(output_path)

        return output_path

    # Slash command to generate the card
    @commands.slash_command(guild_ids=[config.lol_server], description="Generate a player trading card")
    @commands.has_any_role("League Ops", "Bot Guy")
    async def generate_card(self, ctx, user: discord.Member):
        await ctx.defer()

        # Fetch player data from the database
        player_info = await self.get_player_info(user.id)
        if not player_info:
            return await ctx.respond(f"Could not find player data for {user.display_name}")

        # Fetch player details: name, peak rank (calculated), and team code
        player_name = player_info.get('nickname', user.display_name)
        peak_rank = self.get_peak_rank(player_info)
        team_code = player_info.get('team', '')

        # Get the player's Discord avatar
        avatar_url = user.avatar.url
        response = requests.get(avatar_url)
        avatar_image = Image.open(BytesIO(response.content))

        # Generate the player card
        card_path = await self.generate_card(player_name, avatar_image, peak_rank, team_code)

        # Send the generated card image in the Discord channel
        await ctx.send(file=discord.File(card_path))

        # Clean up the generated card file
        os.remove(card_path)

def setup(bot):
    bot.add_cog(CardGenerator(bot))
