import requests
import discord
import logging
from discord.ext import commands
import app.config as config
import app.dbInfo as dbInfo

API_KEY = config.RIOT_API
REGION = 'NA'  
PROVIDER_URL = 'https://www.unitedrogue.com'

GUILD_ID=1171263858971770901

logger = logging.getLogger(__name__)

class TournamentCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(guild_ids=[GUILD_ID], description="Register a provider")
    @commands.has_any_role("Bot Guy")
    async def register_provider(self, ctx):
        provider_payload = {
            "region": REGION,
            "url": PROVIDER_URL
        }
        try:
            logger.debug(f"Provider payload: {provider_payload}")
            response = requests.post(
                f"https://americas.api.riotgames.com/lol/tournament/v5/providers",
                json=provider_payload,
                headers={"X-Riot-Token": API_KEY}
            )
            response.raise_for_status()

            provider_id = int(response.text)

            dbInfo.save_provider_id(provider_id)  # Save provider ID to database
            await ctx.respond(f"Provider registered with ID: {provider_id}")
            logger.info(f"Provider registered with ID: {provider_id}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to register provider: {e}")
            await ctx.respond("Failed to register provider. Please check the logs for details.")

    @commands.slash_command(guild_ids=[GUILD_ID], description="Create a new tournament")
    @commands.has_any_role("Bot Guy")
    async def create_tournament(self, ctx, tournament_name: str):
        provider_id = dbInfo.get_provider_id()  # Retrieve this from your database
        tournament_payload = {
            "name": tournament_name,
            "providerId": provider_id
        }
        try:
            response = requests.post(
                f"https://americas.api.riotgames.com/lol/tournament/v5/tournaments",
                json=tournament_payload,
                headers={"X-Riot-Token": API_KEY}
            )
            response.raise_for_status()

            tournament_id = int(response.text)

            dbInfo.save_tournament_id(tournament_id, tournament_name) # Save tournament ID to database
            await ctx.respond(f"Tournament created with ID: {tournament_id}")
            logger.info(f"Tournament created with ID: {tournament_id}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to create tournament: {e}")
            await ctx.respond("Failed to create tournament. Please check the logs for details.")

    @commands.slash_command(guild_ids=[GUILD_ID], description="Generate tournament codes")
    @commands.has_any_role("Bot Guy", "Commissioner", "Owner")
    async def generate_tournament_codes(self, ctx, count: int):
        tournament_id = dbInfo.get_tournament_id()
        logger.debug(f"Passing tournament ID: {tournament_id}")

        code_payload = {
            "mapType": "SUMMONERS_RIFT",
            "pickType": "TOURNAMENT_DRAFT",
            "spectatorType": "ALL",
            "teamSize": 5,
            "metadata": "UR LoL Match"
        }
        
        try:
            response = requests.post(
                f"https://americas.api.riotgames.com/lol/tournament/v5/codes?tournamentId={tournament_id}&count={count}",
                json=code_payload,
                headers={"X-Riot-Token": API_KEY}
            )
            response.raise_for_status()

            tournament_codes = response.json()

            dbInfo.save_tournament_codes(tournament_id, tournament_codes)  # Save these codes in your database
            
            await ctx.respond(f"Tournament codes generated: {', '.join(tournament_codes)}")
            logger.info(f"Tournament codes generated: {tournament_codes}")
        except requests.exceptions.HTTPError as err:
            error_message = err.response.json().get('message', 'Unknown error')
            logger.error(f"Failed to generate tournament codes: {err} - {error_message}")
            logger.debug(f"Payload: {code_payload}")
            logger.debug(f"Response: {err.response.text}")
            await ctx.respond(f"Failed to generate tournament codes: {err} - {error_message}", ephemeral=True)
    
    
    @commands.slash_command(guild_ids=[GUILD_ID], description="Fetch match details and lobby events")
    @commands.has_any_role("Bot Guy", "League Ops", "Commissioner", "Owner")
    async def fetch_tournament_info(self, ctx, tournament_code: str):
        try:
            # Fetch match details
            logger.info(f"Fetching match details for tournament code: {tournament_code}")
            match_details = self.get_match_details(tournament_code)
            logger.info(f"Match details: {match_details}")

            # Fetch lobby events
            logger.info(f"Fetching lobby events for tournament code: {tournament_code}")
            lobby_events = self.get_lobby_events_by_tournament_code(tournament_code)
            logger.info(f"Lobby events: {lobby_events}")

            # Respond with both match details and lobby events
            response_message = (
                f"Match details: {match_details}\n"
                f"Lobby events: {lobby_events}"
            )
            await ctx.respond(response_message)
            logger.info(f"Match details and lobby events fetched for tournament code {tournament_code}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch tournament info: {e}")
            await ctx.respond("Failed to fetch tournament info. Please check the logs for details.")

    @staticmethod
    def get_match_details(tournament_code):
        response = requests.get(
            f"https://americas.api.riotgames.com/lol/tournament/v5/games/by-code/{tournament_code}",
            headers={"X-Riot-Token": API_KEY}
        )
        logger.debug(f"Match details response status code: {response.status_code}")
        response.raise_for_status()
        match_details = response.json()
        logger.debug(f"Match details response: {match_details}")
        return match_details

    @staticmethod
    def get_lobby_events_by_tournament_code(tournament_code):
        response = requests.get(
            f"https://americas.api.riotgames.com/lol/tournament/v5/lobby-events/by-code/{tournament_code}",
            headers={"X-Riot-Token": API_KEY}
        )
        logger.debug(f"Lobby events response status code: {response.status_code}")
        response.raise_for_status()
        lobby_events = response.json()
        logger.debug(f"Lobby events response: {lobby_events}")
        return lobby_events

def setup(bot):
    bot.add_cog(TournamentCog(bot))
