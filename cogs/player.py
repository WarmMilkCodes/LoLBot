import asyncio
import aiohttp
import discord
import logging
import pytz
from datetime import datetime, timezone
import app.config as config
import app.dbInfo as dbInfo
from discord.ext import commands, tasks
import urllib.parse

logger = logging.getLogger('__name__')

# Split dates for 2024
SPLITS = [
    {"start": datetime(2024, 1, 10, tzinfo=timezone.utc), "end": datetime(2024, 5, 14, tzinfo=timezone.utc), "name": "Spring Split"},
    {"start": datetime(2024, 5, 15, tzinfo=timezone.utc), "end": datetime(2024, 9, 25, tzinfo=timezone.utc), "name": "Summer Split"},
    {"start": datetime(2024, 9, 25, tzinfo=timezone.utc), "end": None, "name": "Fall Split"},  # End date unknown
]

# Define required game count for eligibility
REQUIRED_GAME_COUNT = 30

def is_game_in_split(game_timestamp, split):
    """Check if a game timestamp falls within the given split."""
    start = split["start"]
    end = split["end"] or datetime.now(timezone.utc)
    game_date = datetime.fromtimestamp(game_timestamp / 1000, timezone.utc)  # Riot timestamps are in milliseconds
    return start <= game_date <= end

class PlayerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.task_started = False
        self.task_running = False
        logger.info("PlayerCog loaded. Waiting for rank and eligibility check task to be started.")

    def cog_unload(self):
        if self.task_started:
            self.rank_and_eligibility_task.cancel()
            logger.info("PlayerCog unloaded and task cancelled.")

    @commands.slash_command(guild_ids=[config.lol_server], description="Start the rank and eligibility check task")
    @commands.has_role("Bot Guy")
    async def start_check_task(self, ctx):
        if not self.task_started:
            self.rank_and_eligibility_task.start()
            self.task_started = True
            await ctx.respond("Rank and eligibility check task started and will run every 24 hours.", ephemeral=True)
            logger.info("Rank and eligibility check task started by admin command.")
        else:
            await ctx.respond("Rank and eligibility check task is already running.", ephemeral=True)

    @tasks.loop(hours=24)
    async def rank_and_eligibility_task(self):
        if self.task_running:
            logger.warning("Rank and eligibility check task is already running. Skipping this execution.")
            return
        
        self.task_running = True
        logger.info("Rank and Eligibility update task triggered.")
        
        try:
            await self.update_ranks_and_check()
        finally:
            self.task_running = False
            logger.info("Rank and eligibility check task completed.")

    @commands.slash_command(guild_ids=[config.lol_server], description="Update player ranks and check eligibility manually")
    @commands.has_role("Bot Guy")
    async def check_ranks_and_eligibility(self, ctx):
        await ctx.defer(ephemeral=True)
        await self.update_ranks_and_check()
        await ctx.respond("Updated ranks and checked eligibility for all players.", ephemeral=True)

    async def update_ranks_and_check(self):
        logger.info("Updating ranks and checking eligibility for all players.")
        riot_id_log_channel = self.bot.get_channel(config.failure_log_channel)

        players = dbInfo.intent_collection.find({"Playing": "Yes"})

        for player in players:
            discord_id = player.get('ID')
            player_record = dbInfo.player_collection.find_one({"discord_id": discord_id, "left_at": None})
            
            if not player_record:
                logger.info(f"Skipping player {discord_id} because not found or left server.")
                continue

            logger.info(f"Processing player: {player_record['name']}")
            puuid = None

            # Check if game_name and tag_line are set
            if not player_record.get('game_name') or not player_record.get('tag_line'):
                logger.warning(f"Missing game_name or tag_line for {player_record['name']}. Skipping rank and eligibility update.")
                if riot_id_log_channel:
                    await riot_id_log_channel.send(
                        f"Missing Riot ID info for {player_record['name']} ({player_record['discord_id']}). Please ensure their game_name and tag_line are set."
                    )
                continue

            # Get and store PUUID
            puuid = await self.get_puuid(player_record['game_name'], player_record['tag_line'])
            if not puuid:
                logger.warning(f"Failed to retrieve PUUID for {player_record['name']}. Skipping rank and eligibility update.")
                if riot_id_log_channel:
                    await riot_id_log_channel.send(
                        f"Failed to retrieve PUUID for {player_record['name']} ({player_record['discord_id']}) - {player_record['game_name']}#{player_record['tag_line']}"
                    )
                continue

            # Get match history and filter by split dates
            match_history = await self.get_match_history(puuid)
            if match_history is None:
                logger.error(f"Failed to retrieve match history for {player_record['name']}")
                continue

            # Get the start and end dates for the Summer and Fall splits
            summer_split_start = SPLITS[1]["start"]
            summer_split_end = SPLITS[1]["end"]
            fall_split_start = SPLITS[2]["start"]

            logger.info(f"Summer Split Start: {summer_split_start}, Fall Split Start: {fall_split_start}")

            # Debugging: Log each match's timestamp to verify splits
            for match in match_history:
                game_timestamp = datetime.fromtimestamp(match["timestamp"] / 1000, timezone.utc)
                logger.info(f"Match timestamp: {game_timestamp}")

            # Count games for the Summer Split
            summer_split_games = [match for match in match_history if summer_split_start <= datetime.fromtimestamp(match["timestamp"] / 1000, timezone.utc) <= summer_split_end]
            summer_split_game_count = len(summer_split_games)

            # Count games for the Fall Split
            fall_split_games = [match for match in match_history if datetime.fromtimestamp(match["timestamp"] / 1000, timezone.utc) >= fall_split_start]
            fall_split_game_count = len(fall_split_games)

            logger.info(f"Player: {player_record['name']}, Summer Split Games: {summer_split_game_count}, Fall Split Games: {fall_split_game_count}")

            # Calculate total game count across Summer and Fall splits
            total_game_count = summer_split_game_count + fall_split_game_count
            is_eligible = total_game_count >= REQUIRED_GAME_COUNT

            logger.info(f"Player: {player_record['name']}, Total Game Count: {total_game_count}, Eligible: {is_eligible}")

            # Store Summoner ID
            summoner_id = await self.get_summoner_id(puuid)
            if summoner_id:
                if not player_record.get('summoner_id') or player_record.get('summoner_id') != summoner_id:
                    dbInfo.player_collection.update_one(
                        {"discord_id": player_record['discord_id']},
                        {"$set": {"summoner_id": summoner_id}}
                    )
                    logger.info(f"Stored Summoner ID for player {player_record['name']}")
            else:
                logger.warning(f"Failed to retrieve Summoner ID for {player_record['name']}. Skipping rank and eligibility update.")
                if riot_id_log_channel:
                    await riot_id_log_channel.send(
                        f"Failed to retrieve Summoner ID for {player_record['name']} ({player_record['discord_id']}) - PUUID: {puuid}"
                    )
                continue

            # Update rank information and eligibility
            rank_info = await self.get_player_rank(summoner_id)
            if rank_info:
                date_str = datetime.now(pytz.utc).strftime('%m-%d-%Y')
                historical_rank_info = player_record.get('historical_rank_info', {})

                if not player_record.get('rank_info') or player_record['rank_info'] != rank_info:
                    historical_rank_info[date_str] = rank_info
                    dbInfo.player_collection.update_one(
                        {"discord_id": player_record['discord_id']},
                        {"$set": {
                            "rank_info": rank_info,
                            "last_updated": datetime.now(pytz.utc).strftime('%m-%d-%Y'),
                            "historical_rank_info": historical_rank_info
                        }}
                    )
                    logger.info(f"Updated rank information for player {player_record['name']} and set last updated.")

            # Update eligibility after updating rank
            if player_record.get("eligible_for_split") != is_eligible or player_record.get("current_split_game_count") != total_game_count:
                logger.info(f"Updating eligibility for {player_record['name']}: Eligible: {is_eligible}, Games: {total_game_count}")
                dbInfo.player_collection.update_one(
                    {"discord_id": player_record['discord_id']},
                    {"$set": {
                        "eligible_for_split": is_eligible,
                        "last_eligibility_check": datetime.now(pytz.utc),
                        "current_split_game_count": total_game_count
                    }}
                )
            else:
                logger.info(f"No change in eligibility for {player_record['name']}")

        logger.info("Completed rank and eligibility check for all players.")

    async def get_match_history(self, puuid):
        """Get match history for the Summer and Fall split."""
        url = f"https://americas.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
        headers = {'X-Riot-Token': config.RIOT_API}
        summer_split_start = int(self.get_summer_split_start().timestamp())
        params = {
            "startTime": summer_split_start,  # Get matches starting from the Summer Split
            "type": "ranked",
            "count": 100  # Retrieve more matches if necessary
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    match_ids = await response.json()
                    logger.info(f"Retrieved match IDs for PUUID {puuid}: {match_ids}")
                    return match_ids
                else:
                    logger.error(f"Error fetching match history for PUUID {puuid}: {await response.text()}")
                    return []


    def get_summer_split_start(self):
        """Retrieve the start date of the Summer Split."""
        summer_split = SPLITS[1]  # Summer Split is the second in the list
        return summer_split['start']

    async def get_puuid(self, game_name, tag_line):
        """Fetch the PUUID for a given Riot game name and tag line."""
        encoded_game_name = urllib.parse.quote(game_name)
        encoded_tag_line = urllib.parse.quote(tag_line)
        url = f"https://americas.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{encoded_game_name}/{encoded_tag_line}"
        headers = {'X-Riot-Token': config.RIOT_API}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    account_info = await response.json()
                    return account_info.get('puuid')
                else:
                    logger.error(f"Error fetching PUUID for {game_name}#{tag_line}: {await response.text()}")
                    return None

    async def get_summoner_id(self, puuid):
        """Get summoner ID from PUUID."""
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

    async def get_player_rank(self, summoner_id):
        """Fetch player's rank information."""
        url = f"https://na1.api.riotgames.com/lol/league/v4/entries/by-summoner/{summoner_id}"
        headers = {'X-Riot-Token': config.RIOT_API}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    rank_info = await response.json()
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

def setup(bot):
    bot.add_cog(PlayerCog(bot))