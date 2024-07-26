import requests
import discord
from discord.ext import commands
import app.config as config
import app.dbInfo as dbInfo

API_KEY = config.RIOT_API
REGION = 'na1'  
PROVIDER_URL = 'https://www.unitedrogue.com'

class TournamentCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(description="Register a provider")
    @commands.has_any_role("Staff", "Admin")
    async def register_provider(self, ctx):
        provider_payload = {
            "region": REGION,
            "url": PROVIDER_URL
        }
        response = requests.post(
            f"https://{REGION}.api.riotgames.com/lol/tournament-stub/v4/providers",
            json=provider_payload,
            headers={"X-Riot-Token": API_KEY}
        )
        provider_id = response.json()
        dbInfo.save_provider_id(provider_id)  # Save provider ID in your database
        await ctx.respond(f"Provider registered with ID: {provider_id}")

    @commands.slash_command(description="Create a new tournament")
    @commands.has_any_role("Staff", "Admin")
    async def create_tournament(self, ctx, tournament_name: str):
        provider_id = dbInfo.get_provider_id()  # Retrieve this from your database
        tournament_payload = {
            "name": tournament_name,
            "providerId": provider_id
        }
        response = requests.post(
            f"https://{REGION}.api.riotgames.com/lol/tournament-stub/v4/tournaments",
            json=tournament_payload,
            headers={"X-Riot-Token": API_KEY}
        )
        tournament_id = response.json()
        dbInfo.save_tournament_id(tournament_id)  # Save this in your database
        await ctx.respond(f"Tournament created with ID: {tournament_id}")

    @commands.slash_command(description="Generate tournament codes")
    @commands.has_any_role("Staff", "Admin")
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
        response = requests.post(
            f"https://{REGION}.api.riotgames.com/lol/tournament-stub/v4/codes?count={count}",
            json=code_payload,
            headers={"X-Riot-Token": API_KEY}
        )
        tournament_codes = response.json()
        dbInfo.save_tournament_codes(tournament_codes)  # Save these codes in your database
        await ctx.respond(f"Tournament codes generated: {tournament_codes}")

    @commands.slash_command(description="Fetch match results")
    @commands.has_any_role("Staff", "Admin")
    async def fetch_match_results(self, ctx, tournament_code: str):
        match_ids = self.get_match_ids_by_tournament_code(tournament_code)
        match_results = []
        for match_id in match_ids:
            match_details = self.get_match_details(match_id, tournament_code)
            match_results.append(match_details)
            dbInfo.save_match_details(match_details)  # Save match details in your database
        await ctx.respond(f"Match results fetched: {match_results}")

    @staticmethod
    def get_match_ids_by_tournament_code(tournament_code):
        response = requests.get(
            f"https://{REGION}.api.riotgames.com/lol/match/v4/matches/by-tournament-code/{tournament_code}/ids",
            headers={"X-Riot-Token": API_KEY}
        )
        return response.json()

    @staticmethod
    def get_match_details(match_id, tournament_code):
        response = requests.get(
            f"https://{REGION}.api.riotgames.com/lol/match/v4/matches/{match_id}/by-tournament-code/{tournament_code}",
            headers={"X-Riot-Token": API_KEY}
        )
        return response.json()

def setup(bot):
    bot.add_cog(TournamentCog(bot))
