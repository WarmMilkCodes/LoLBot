import aiohttp, logging, pytz
from datetime import datetime
import app.config as config
import app.dbInfo as dbInfo
from discord.ext import commands, tasks
import discord

logger = logging.getLogger('lol_log')

class PlayerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.rank_update_task_started = False
        logger.info("PlayerCog loaded. Waiting for bot to be ready to run task.")

    def cog_unload(self):
        if self.rank_update_task_started:
            self.rank_update_task.cancel()
            logger.info("PlayerCog unloaded and rank task cancelled.")

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.rank_update_task_started:
            logger.info("Bot is ready. Starting rank update task.")
            self.rank_update_task.start()
            self.rank_update_task_started = True

    @tasks.loop(hours=24)
    async def rank_update_task(self):
        logging.info("Rank update task triggered.")
        await self.update_all_ranks()

    ## Command to update player ranks
    @commands.slash_command(description="Update player ranks")
    @commands.has_permissions(administrator=True)
    async def update_ranks(self, ctx):
        await ctx.defer()
        await self.update_all_ranks()
        await ctx.respond("Updated ranks for all players", ephemeral=True)

    ## Function to update ranks for all players
    async def update_all_ranks(self):
        logger.info("Updating ranks for all players.")
        failure_channel = self.bot.get_channel(config.failure_log_channel)
        players = dbInfo.player_collection.find({})

        for player in players:
            logger.info(f"Processing player: {player['name']}")
            if 'game_name' in player and 'tag_line' in player:
                puuid = await self.get_puuid(player['game_name'], player['tag_line'])

                if puuid and (not player.get('puuid') or player.get('puuid') != puuid):
                    dbInfo.player_collection.update_one(
                        {"discord_id": player['discord_id']},
                        {"$set": {"puuid": puuid}}
                    )
                    logger.info(f"Stored PUUID for {player['name']}")

                    summoner_id = await self.get_summoner_id(puuid)
                    if summoner_id and (not player.get('summoner_id') or player.get('summoner_id') != summoner_id):
                        dbInfo.player_collection.update_one(
                            {"discord_id": player['discord_id']},
                            {"$set": {"summoner_id": summoner_id}}
                        )
                        logger.info(f"Stored Summoner ID for player {player['name']}")
                if summoner_id:
                    rank_info = await self.get_player_rank(summoner_id)
                        
                if rank_info:
                    # Store rank information with date
                    date_str = datetime.now(pytz.utc).strftime('%m-%d-%Y')
                    historical_rank_info = player.get('historical_rank_info', {})

                    # Check if rank info for today already exists and is the same
                    if date_str in historical_rank_info and historical_rank_info[date_str] == rank_info:
                        logger.info(f"Rank information for player {player['name']} is unchanged for today.")
                        continue

                    # If current rank_info is different, update the database
                    if not player.get('rank_info') or player['rank_info'] != rank_info:
                        historical_rank_info[date_str] = rank_info

                        dbInfo.player_collection.update_one(
                            {"discord_id": player['discord_id']},
                            {"$set": {
                                "rank_info": rank_info, 
                                "last_updated": datetime.now(pytz.utc).strftime('%m-%d-%Y'),
                                "historical_rank_info": historical_rank_info
                                }}
                        )
                        logger.info(f"Updated rank information for player {player['name']} and set last updated.")
                else:
                    if not player.get('last_updated') or player['last_updated'] != datetime.now(pytz.utc).strftime('%m-%d-%Y'):
                        dbInfo.player_collection.update_one(
                            {"discord_id": player['discord_id']},
                            {"$set": {"last_updated":datetime.now(pytz.utc).strftime('%m-%d-%Y')}}
                        )
                    logger.warning(f"No rank information found for {player['name']}, but updated last_updated")
                    
            else:
                logger.error(f"Player {player['name']} does not have game_name and tag_line set.")
                await self.report_failure(failure_channel, player['name'], 'Riot ID is not set or is invalid.')
        logger.info("Completed updating ranks for all players.")


    ## Function to get PUUID
    async def get_puuid(self, game_name, tag_line):
        url = f"https://americas.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
        headers = {'X-Riot-Token': config.RIOT_API}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    account_info = await response.json()
                    return account_info.get('puuid')
                else:
                    logger.error(f"Error fetching PUUID for {game_name}#{tag_line}: {await response.text()}")
                    return None                    

    ## Function to get Summoner ID
    async def get_summoner_id(self, puuid):
        url = f"https://na1.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"
        headers = {'X-Riot-Token': config.RIOT_API}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    summoner_info = await response.json()
                    return summoner_info.get('id')
                else:
                    logger.error(f"Error fetching Summoner ID for PUUID {puuid}: {await response.text()}")
                    return None

    ## Function to get player rank
    async def get_player_rank(self, summoner_id):
        url = f"https://na1.api.riotgames.com/lol/league/v4/entries/by-summoner/{summoner_id}"
        headers = {'X-Riot-Token': config.RIOT_API}
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
                    logger.error(f"Error fetching rank info for Summoner ID {summoner_id}: {await response.text()}")
                    return None

    ## Function to report failures to a specific channel
    async def report_failure(self, channel, player_name, reason):
        if channel:
            message = f"Player: {player_name} | Reason: {reason}"
            await channel.send(message)

def setup(bot):
    bot.add_cog(PlayerCog(bot))
