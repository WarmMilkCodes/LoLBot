import asyncio
import aiohttp
import discord
import logging
import pytz
from datetime import datetime, timezone
import app.config as config
import app.dbInfo as dbInfo
from discord.ext import commands, tasks

logger = logging.getLogger('__name__')

# Split dates for 2024
SPLITS = [
    {"start": datetime(2024, 1, 10, tzinfo=timezone.utc), "end": datetime(2024, 5, 14, tzinfo=timezone.utc), "name": "Spring Split"},
    {"start": datetime(2024, 5, 15, tzinfo=timezone.utc), "end": datetime(2024, 9, 25, tzinfo=timezone.utc), "name": "Summer Split"},
    {"start": datetime(2024, 9, 25, tzinfo=timezone.utc), "end": None, "name": "Fall Split"},  # End date unknown
]

# Define required game count for eligibility
REQUIRED_GAME_COUNT = 30

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

        # Fetch all players currently playing
        players = dbInfo.intent_collection.find({"Playing": "Yes"})

        for player in players:
            discord_id = player.get('ID')
            player_record = dbInfo.player_collection.find_one({"discord_id": discord_id, "left_at": None})
            
            if not player_record:
                logger.info(f"Skipping player {discord_id} because not found or left server.")
                continue

            # Fetch the split game counts from the database
            summer_split_game_count = player_record.get('summer_split_game_count', 0)
            fall_split_game_count = player_record.get('fall_split_game_count', 0)
            total_game_count = summer_split_game_count + fall_split_game_count
            

            logger.info(f"Processing player: {player_record['name']}")
            puuid = player_record.get('puuid')

            # If no PUUID is stored, fetch and store it
            if not puuid:
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
                else:
                    dbInfo.player_collection.update_one(
                        {"discord_id": player_record['discord_id']},
                        {"$set": {"puuid": puuid}}
                    )

            # Get match history (match IDs) if player has not met the game count requirement
            if total_game_count < REQUIRED_GAME_COUNT:
                match_history = await self.get_match_history(puuid)
                if match_history is None:
                    logger.error(f"Failed to retrieve match history for {player_record['name']}")
                    continue

                # Get the start and end dates for the Summer and Fall splits
                summer_split_start = SPLITS[1]["start"]
                summer_split_end = SPLITS[1]["end"]
                fall_split_start = SPLITS[2]["start"]

                logger.info(f"Summer Split Start: {summer_split_start}, Fall Split Start: {fall_split_start}")

                # Initialize counts for new games
                new_summer_split_games = 0
                new_fall_split_games = 0

                # Fetch match details for each match ID and categorize them into splits
                for match_id in match_history:
                    if total_game_count >= REQUIRED_GAME_COUNT:
                        logger.info(f"Player {player_record['name']} has reached the required {REQUIRED_GAME_COUNT} games. Stopping further checks.")
                        break  # Stop fetching more games if the required number has been reached

                    match_details = await self.get_match_details(match_id)
                    if not match_details:
                        continue  # Skip if there was an error retrieving match details

                    # Get the game creation timestamp
                    game_timestamp = match_details['info']['gameCreation'] / 1000  # Convert from milliseconds to seconds
                    game_date = datetime.fromtimestamp(game_timestamp, timezone.utc)

                    logger.info(f"Match {match_id} timestamp: {game_date}")

                    # Count games for the Summer Split
                    if summer_split_start <= game_date <= summer_split_end:
                        new_summer_split_games += 1

                    # Count games for the Fall Split
                    if game_date >= fall_split_start:
                        new_fall_split_games += 1

                    # Update total game count
                    total_game_count = summer_split_game_count + new_summer_split_games + fall_split_game_count + new_fall_split_games

                logger.info(f"Player: {player_record['name']}, Summer Split Games: {new_summer_split_games}, Fall Split Games: {new_fall_split_games}")

                # Update the split game counts in the database
                dbInfo.player_collection.update_one(
                    {"discord_id": player_record['discord_id']},
                    {"$set": {
                        "summer_split_game_count": summer_split_game_count + new_summer_split_games,
                        "fall_split_game_count": fall_split_game_count + new_fall_split_games
                    }}
                )

                # Calculate eligibility based on total games
                is_eligible = total_game_count >= REQUIRED_GAME_COUNT

                # Update eligibility status
                dbInfo.player_collection.update_one(
                    {"discord_id": player_record['discord_id']},
                    {"$set": {
                        "eligible_for_split": is_eligible,
                        "last_eligibility_check": datetime.now(pytz.utc),
                        "current_split_game_count": fall_split_game_count + new_fall_split_games
                    }}
                )

            # Rank check and update will ALWAYS run, even if eligibility is already met
            summoner_id = player_record.get('summoner_id')
            if not summoner_id:
                # Fetch summoner ID if not available
                summoner_id = await self.get_summoner_id(puuid)
                if summoner_id:
                    dbInfo.player_collection.update_one(
                        {"discord_id": player_record['discord_id']},
                        {"$set": {"summoner_id": summoner_id}}
                    )
                    logger.info(f"Stored Summoner ID for player {player_record['name']}")
                else:
                    logger.warning(f"Failed to retrieve Summoner ID for {player_record['name']}. Skipping rank update.")
                    continue

            # Fetch and store rank info
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

        logger.info("Completed rank and eligibility check for all players.")



    async def get_match_history(self, puuid):
        """Get match history for the current and last split."""
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

    async def get_match_details(self, match_id):
        """Get the details of a specific match by match ID."""
        url = f"https://americas.api.riotgames.com/lol/match/v5/matches/{match_id}"
        headers = {'X-Riot-Token': config.RIOT_API}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    match_details = await response.json()
                    return match_details
                else:
                    logger.error(f"Error fetching match details for match ID {match_id}: {await response.text()}")
                    return None

    async def get_puuid(self, game_name, tag_line):
        """Get PUUID for the given game_name and tag_line."""
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

    def get_summer_split_start(self):
        """Retrieve the start date of the Summer Split."""
        summer_split = SPLITS[1]  # Summer Split is the second in the list
        return summer_split['start']

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

    async def get_player_rank(self, summoner_id):
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