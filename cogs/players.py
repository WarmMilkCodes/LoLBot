import aiohttp
import config, dbInfo
from discord.ext import commands
from discord.commands import Option

class PlayerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(description="Update PUUIDs for all players")
    @commands.has_permissions(administrator=True)
    async def update_puuids(self, ctx):
        await ctx.defer()
        await self.update_all_puuids()
        await ctx.respond("Updated PUUID for all players in database.", ephemeral=True)

    async def update_all_puuids(self):
        players = dbInfo.player_collection.find({})
        for player in players:
            if 'game_name' in player and 'tag_line' in player:
                puuid = await self.get_puuid(player['game_name'], player['tag_line'])
                if puuid:
                    dbInfo.player_collection.update_one(
                        {"discord_id": player['discord_id']},
                        {"$set": {"puuid": puuid}}
                    )

    async def get_puuid(self, game_name, tag_line):
        url = f"https://americas.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
        headers = {'X-Riot-Token': config.riot_api}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    account_info = await response.json()
                    return account_info['puuid']
                else:
                    # Handle different HTTP statuses or log them
                    return None

    @commands.slash_command(description="Update all player ranks")
    @commands.has_permissions(administrator=True)
    async def update_ranks(self, ctx):
        await ctx.defer()
        await self.update_all_ranks()
        await ctx.respond("Updated all player ranks.", ephemeral=True)

    async def update_all_ranks(self):
        players = dbInfo.player_collection.find({"puuid": {"$exists": True}})
        for player in players:
            puuid = player['puuid']
            summoner_id = await self.get_summoner_id(puuid)
            if summoner_id:
                rank_info = await self.get_player_rank(summoner_id)
                if rank_info:
                    dbInfo.player_collection.update_one(
                        {"discord_id": player['discord_id']},
                        {"$set": {"rank_info": rank_info}}
                    )

    async def get_summoner_id(self, puuid):
        url = f"https://americas.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"
        headers = {'X-Riot-Token': config.riot_api}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    summoner_info = await response.json()
                    return summoner_info['id']
                else:
                    # Handle errors
                    return None

    async def get_player_rank(self, summoner_id):
        url = f"https://americas.api.riotgames.com/lol/league/v4/entries/by-summoner/{summoner_id}"
        headers = {'X-Riot-Token': config.riot_api}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    rank_info = await response.json()
                    return rank_info
                else:
                    # Handle errors
                    return None

def setup(bot):
    bot.add_cog(PlayerCog(bot))
