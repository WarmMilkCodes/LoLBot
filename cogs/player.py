import aiohttp, json
import config, dbInfo
from discord.ext import commands, tasks
from discord.commands import Option

class PlayerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.rank_update_task.start() # Start background task

    def cog_unload(self):
        self.rank_update_task.cancel() # Cancel task when is unloaded

    @tasks.loop(hours=12)
    async def rank_update_task(self):
        await self.update_all_ranks()

    @rank_update_task.before_loop
    async def before_rank_update_task(self):
        await self.bot.wait_until_ready() # Wait until the bot is ready

    ## Command to update player ranks
    @commands.slash_command(description="Update player ranks")
    @commands.has_permissions(administrator=True)
    async def update_ranks(self, ctx):
        await ctx.defer()
        await self.update_all_ranks()
        await ctx.respond("Update ranked for all players", ephemeral=True)

    ## Function to update ranks for all players
    async def update_all_ranks(self):
        players = dbInfo.player_collection.find({})
        for player in players:
            if 'game_name' in player and 'tag_line' in player:
                puuid = await self.get_puuid(player['game_name'], player['tag_line'])
                if puuid:
                    dbInfo.player_collection.update_one(
                        {"discord_id": player['discord_id']},
                        {"$set": {"puuid": puuid}}
                    )
                    print(f"Stored PUUID for {player['name']}")

                    summoner_id = await self.get_summoner_id(puuid)
                    if summoner_id:
                        dbInfo.player_collection.update_one(
                            {"discord_id": player['discord_id']},
                            {"$set": {"summoner_id": summoner_id}}
                        )
                        print(f"Stored Summoner ID for player {player['name']}")

                        rank_info = await self.get_player_rank(summoner_id)
                        if rank_info:
                            dbInfo.player_collection.update_one(
                                {"discord_id": player['discord_id']},
                                {"$set": {"rank_info": rank_info}}
                            )
                            print(f"Updated rank information for player {player['name']}")

                        else:
                            print(f"No rank information found for {player['name']}")
                            
                    else:
                        print(f"Failed to retrieve summoner information for {player['name']}")

    ## Function to get PUUID
    async def get_puuid(self, game_name, tag_line):
        url = f"https://americas.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
        headers = {'X-Riot-Token': config.riot_api}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    account_info = await response.json()
                    return account_info.get('puuid')
                else:
                    print(f"Error fetching PUUID for {game_name}#{tag_line}: {await response.text()}")
                    return None                    

    ## Function to get Summoner ID
    async def get_summoner_id(self, puuid):
        url = f"https://na1.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"
        headers = {'X-Riot-Token': config.riot_api}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    summoner_info = await response.json()
                    return summoner_info.get('id')
                else:
                    print(f"Error fetching Summoner ID for PUUID {puuid}: {await response.text()}")
                    return None

    ## Function to get player rank
    async def get_player_rank(self, summoner_id):
        url = f"https://na1.api.riotgames.com/lol/league/v4/entries/by-summoner/{summoner_id}"
        headers = {'X-Riot-Token': config.riot_api}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    rank_info = await response.json()
                    # Extract tier and division for each queue type (e.g., Solo Queue, Flex Queue)
                    tier_division_info = []
                    for entry in rank_info:
                        tier = entry.get('tier')
                        division = entry.get('rank')
                        queue_type = entry.get('queueType')
                        tier_division_info.append({
                            "queue_type": queue_type,
                            "tier": tier,
                            "division": division
                        })
                    return tier_division_info
                else:
                    print(f"Error fetching rank info for Summoner ID {summoner_id}: {await response.text()}")
                    return None


def setup(bot):
    bot.add_cog(PlayerCog(bot))
