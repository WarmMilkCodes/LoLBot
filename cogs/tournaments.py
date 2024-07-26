import requests
import discord
import logging
from discord.ext import commands
import app.config as config
import app.dbInfo as dbInfo

API_KEY = config.RIOT_API
REGION = 'americas'  
PROVIDER_URL = 'https://www.unitedrogue.com'

GUILD_ID=1171263858971770901

logger = logging.getLogger(__name__)

class TournamentCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(guild_ids=[GUILD_ID],description="Register a provider")
    @commands.has_any_role("Bot Guy")
    async def register_provider(self, ctx):
        provider_payload = {
            "region": REGION,
            "url": PROVIDER_URL
        }
        try:
            response = requests.post(
                f"https://americas.api.riotgames.com/lol/tournament-stub/v5/providers",
                json=provider_payload,
                headers={"X-Riot-Token": API_KEY}
            )
            response.raise_for_status()
            provider_id = response.json()
            dbInfo.save_provider_id(provider_id)  # Save provider ID in your database
            await ctx.respond(f"Provider registered with ID: {provider_id}")
            logger.info(f"Provider registered with ID: {provider_id}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to register provider: {e}")
            await ctx.respond("Failed to register provider. Please check the logs for details.")

    @commands.slash_command(guild_ids=[GUILD_ID],description="Create a new tournament")
    @commands.has_any_role("Bot Guy")
    async def create_tournament(self, ctx, tournament_name: str):
        provider_id = dbInfo.get_provider_id()  # Retrieve this from your database
        tournament_payload = {
            "name": tournament_name,
            "providerId": provider_id
        }
        try:
            response = requests.post(
                f"https://{REGION}.api.riotgames.com/lol/tournament-stub/v5/tournaments",
                json=tournament_payload,
                headers={"X-Riot-Token": API_KEY}
            )
            response.raise_for_status()
            tournament_id = response.json()
            dbInfo.save_tournament_id(tournament_id, tournament_name)
            await ctx.respond(f"Tournament created with ID: {tournament_id, tournament_name}")
            logger.info(f"Tournament created with ID: {tournament_id}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to create tournament: {e}")
            await ctx.respond("Failed to create tournament. Please check the logs for details.")

    @commands.slash_command(guild_ids=[GUILD_ID],description="Generate tournament codes")
    @commands.has_any_role("Bot Guy", "League Ops", "Commissioner", "Owner")
    async def generate_tournament_codes(self, ctx, count: int):
        tournament_id = dbInfo.get_tournament_id()  # Retrieve this from your database
        code_payload = {
            "mapType": "SUMMONERS_RIFT",
            "pickType": "TOURNAMENT_DRAFT",
            "spectatorType": "ALL",
            "teamSize": 5,
            "tournamentId": tournament_id,
            "metadata": "UR LoL Match"
        }
        try:
            response = requests.post(
                f"https://{REGION}.api.riotgames.com/lol/tournament-stub/v5/codes?count={count}",
                json=code_payload,
                headers={"X-Riot-Token": API_KEY}
            )
            response.raise_for_status()
            tournament_codes = response.json()
            dbInfo.save_tournament_codes(tournament_codes)  # Save these codes in your database
            await ctx.respond(f"Tournament codes generated: {tournament_codes}")
            logger.info(f"Tournament codes generated: {tournament_codes}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to generate tournament codes: {e}")
            await ctx.respond("Failed to generate tournament codes. Please check the logs for details.")

    @commands.slash_command(guild_ids=[GUILD_ID],description="Fetch match results")
    @commands.has_any_role("Bot Guy", "League Ops", "Commissioner", "Owner")
    async def fetch_match_results(self, ctx, tournament_code: str):
        try:
            match_ids = self.get_match_ids_by_tournament_code(tournament_code)
            match_results = []
            for match_id in match_ids:
                match_details = self.get_match_details(match_id, tournament_code)
                match_results.append(match_details)
                dbInfo.save_match_details(match_details)  # Save match details in your database
            await ctx.respond(f"Match results fetched: {match_results}")
            logger.info(f"Match results fetched for tournament code {tournament_code}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch match results: {e}")
            await ctx.respond("Failed to fetch match results. Please check the logs for details.")

    @staticmethod
    def get_match_ids_by_tournament_code(tournament_code):
        response = requests.get(
            f"https://{REGION}.api.riotgames.com/lol/match/v5/matches/by-tournament-code/{tournament_code}/ids",
            headers={"X-Riot-Token": API_KEY}
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def get_match_details(match_id, tournament_code):
        response = requests.get(
            f"https://{REGION}.api.riotgames.com/lol/match/v5/matches/{match_id}/by-tournament-code/{tournament_code}",
            headers={"X-Riot-Token": API_KEY}
        )
        response.raise_for_status()
        return response.json()

def setup(bot):
    bot.add_cog(TournamentCog(bot))