import discord, logging, gspread, os
from oauth2client.service_account import ServiceAccountCredentials
from discord.ext import commands, tasks
import app.dbInfo as dbInfo
import app.config as config

logger = logging.getLogger('sheet_log')

class SheetCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.task_started = False
        self.sheet_url = None

    def cog_unload(self):
        if self.task_started:
            self.update_sheet_task.cancel()
            logger.info("Google Sheet update task cancelled due to unloaded cog.")

    def authenticate_google_sheets(self):
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        json_path = os.path.join(os.path.dirname(__file__), '..', 'google_creds.json')

        creds = ServiceAccountCredentials.from_json_keyfile_name(json_path, scope)
        client = gspread.authorize(creds)
        return client

    @commands.slash_command(guild_ids=[config.lol_server], description="Initialize the Google Sheet and start updating.")
    @commands.has_role("Bot Guy")
    async def initialize_sheet(self, ctx):
        client = self.authenticate_google_sheets()

        # Create a new spreadsheet
        spreadsheet = client.create("Player Data")
        self.sheet_url = spreadsheet.url
        worksheet = spreadsheet.sheet1

        # Set up the initial structure (headers) of the sheet
        worksheet.update('A1', 'Discord ID')
        worksheet.update('B1', 'Player Name')
        worksheet.update('C1', 'Rank')
        worksheet.update('D1', 'Eligible')
        worksheet.update('E1', 'Games Played')

        await ctx.respond(f"Google Sheet created: {self.sheet_url}", ephemeral=True)

        # Start the task to update the sheet regularly
        if not self.task_started:
            self.update_sheet_task.start()
            self.task_started = True
            logger.info("Google Sheet update task started.")

    @tasks.loop(hours=24)
    async def update_sheet_task(self):
        if not self.sheet_url:
            logger.warning("No Google Sheet URL found. Task will not run.")
            return

        client = self.authenticate_google_sheets()
        spreadsheet = client.open_by_url(self.sheet_url)
        worksheet = spreadsheet.sheet1

        players = dbInfo.player_collection.find({"left_at": None})
        for i, player in enumerate(players, start=2):
            worksheet.update(f'A{i}', player.get('discord_id', 'N/A'))
            worksheet.update(f'B{i}', player.get('name', 'N/A'))
            worksheet.update(f'C{i}', self.get_solo_rank(player.get('rank_info', [])))
            worksheet.update(f'D{i}', "Yes" if player.get('eligible_for_split') else "No")
            worksheet.update(f'E{i}', player.get('current_split_game_count', 0))
            
        logger.info("Google Sheet updated.")

    def get_solo_rank(self, rank_info):
        for rank in rank_info:
            if rank.get('queue_type') == 'RANKED_SOLO_5X5':
                return f"{rank.get('tier', 'N/A')} {rank.get('division', 'N/A')}"
        return 'N/A'

    @commands.slash_command(guild_ids=[config.lol_server], description="Initial setup for Google Sheets")
    @commands.has_role("Bot Guy")
    async def setup_sheet(self, ctx):
        await ctx.defer()
        client = self.authenticate_google_sheets()
        sheet = client.create("UR LoL Player Data")
        worksheet = sheet.get_worksheet(0)

        # Set up the initial structure (headers) of the sheet
        worksheet.append_row(["Discord ID", "Name", "Ranked Solo 5x5 Rank", "Eligibility", "Games Played"])

        # Populate with data
        players = dbInfo.player_collection.find({"left_at": None})
        for player in players:
            discord_id = player.get('discord_id')
            name = player.get('name', 'N/A')
            eligibility = 'Eligible' if player.get('eligible_for_split') else 'Not Eligible'
            game_count = player.get('current_split_game_count', 0)

            # Get the player's rank info for Ranked Solo 5x5
            rank = self.get_solo_rank(player.get('rank_info', []))
            
            # Append player data to the sheet
            worksheet.append_row([discord_id, name, rank, eligibility, game_count])
        
        self.sheet_url = sheet.url
        await ctx.respond("Google Sheet setup completed and populated with player data.", ephemeral=True)

def setup(bot):
    bot.add_cog(SheetCog(bot))