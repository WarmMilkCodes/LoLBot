import asyncio
import aiohttp
import discord
import logging
import pytz
from datetime import datetime, timezone
import app.config as config
import app.dbInfo as dbInfo
from discord.ext import commands, tasks
from discord.commands import Option

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
    async def dev_start_checks(self, ctx):
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
    async def dev_check_players(self, ctx):
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

            logger.info(f"Processing player: {player_record.get('name')}")

            if not player_record:
                logger.info(f"Skipping player {player_record.get('name')} because not found or left server.")
                continue

            # Check if the player is eligible for the current split
            eligible_for_split = player_record.get('eligible_for_split', False)
            
            if eligible_for_split:
                logger.info(f"Player {player_record['name']} is already eligible for the current split. Skipping.")
                continue

            # Process player and alt accounts
            highest_rank_info = await self.process_player_and_alts(player_record, riot_id_log_channel)
            if highest_rank_info is None:
                continue  # Skip to the next player if there was an issue with rank retrieval

            # Update rank info with the highest rank found
            dbInfo.player_collection.update_one(
                {"discord_id": player_record['discord_id']},
                {"$set": {
                    "rank_info": highest_rank_info['rank_info'],
                    "last_updated": datetime.now(pytz.utc).strftime('%m-%d-%Y'),
                    "highest_account_type": highest_rank_info['account_type'],  # Indicates whether it's from main or alt
                }}
            )
            logger.info(f"Updated rank information for player {player_record['name']} from their {highest_rank_info['account_type']} account.")

            # Check and store eligible match count
            eligible_matches = await self.get_match_history(player_record['puuid'])  # Get matches for this player

            # Check if the player has reached the required number of eligible matches
            if eligible_matches >= 30:
                logger.info(f"Player {player_record['name']} has reached eligibility with {eligible_matches} matches.")
                # Update player record to reflect eligibility
                await dbInfo.player_collection.update_one(
                    {"discord_id": player_record['discord_id']},
                    {"$set": {"eligible_for_split": True, "eligible_match_count": eligible_matches}}
                )
            else:
                logger.info(f"Player {player_record['name']} still has {eligible_matches} eligible matches.")



    @commands.slash_command(guild_ids=[config.lol_server], description="Update player rank and check eligibility for a single user")
    @commands.has_role("Bot Guy")
    async def dev_check_single_player(self, ctx, player_name: Option(discord.Member)):
        """
        Command to update rank and check eligibility for a single user.
        """
        try:
            await ctx.defer(ephemeral=True)

            # Find the player by name in the database
            player_record = dbInfo.player_collection.find_one({"discord_id": player_name.id, "left_at": None})

            if not player_record:
                await ctx.respond(f"Player '{player_name.display_name}' not found or has left the server.", ephemeral=True)
                return

            logger.info(f"Processing player: {player_record['name']}")
            riot_id_log_channel = self.bot.get_channel(config.failure_log_channel)

            # Process player and their alt accounts
            logger.debug(f"Preparing to run process player and alts function for {player_record['name']}...")
            highest_rank_info = await self.process_player_and_alts(player_record, riot_id_log_channel)
            logger.debug(f"highest_rank_info function completed for {player_record['name']}")
            if highest_rank_info is None:
                await ctx.respond(f"Failed to retrieve rank information for '{player_name.display_name}'.", ephemeral=True)
                return
            
            # Update rank info with the highest rank found
            dbInfo.player_collection.update_one(
                {"discord_id": player_record['discord_id']},
                {"$set": {
                    "rank_info": highest_rank_info['rank_info'],
                    "last_updated": datetime.now(pytz.utc).strftime('%m-%d-%Y'),
                    "highest_account_type": highest_rank_info['account_type'],  # Indicates whether it's from main or alt
                }}
            )

            logger.info(f"Updated rank information for player {player_record['name']} from their {highest_rank_info['account_type']} account.")
            await ctx.respond(f"Rank and eligibility check completed for '{player_name.display_name}'.", ephemeral=True)

        except Exception as e:
            await ctx.respond(f"There was an error processing {player_name}")
            logger.error(f"Error processing ranks for {player_name}: {e}")


    async def process_player_and_alts(self, player_record, riot_id_log_channel):
        logger.debug(f"Running process player and alts on {player_record['name']}")
        """Process a player and their alt accounts to find the highest rank."""
        highest_rank_info = None
        highest_rank_tier = None
        highest_rank_division = None

        # Define rank order for comparison (used to determine highest rank)
        rank_order = {
            "IRON": 1, "BRONZE": 2, "SILVER": 3, "GOLD": 4, 
            "PLATINUM": 5, "EMERALD": 8, "DIAMOND": 7, "MASTER": 8, "GRANDMASTER": 9, "CHALLENGER": 10
        }
        division_order = {
            'IV': 1, 'III': 2, 'II': 3, 'I': 4
        }

        logger.debug(f"Attempting to get PUUID from DB or API for {player_record['name']}")
        # Step 1: Check rank for main account via API
        puuid = player_record.get('puuid') or await self.get_puuid(player_record['game_name'], player_record['tag_line'])
        if puuid:
            logger.debug(f"Retrieved PUUID for {player_record['name']}: {puuid}\nAttempting to get summoner ID now.")
            summoner_id = await self.get_summoner_id(puuid)
            logger.debug(f"Passed 'Get Summoner ID' for {player_record['name']}")
            if summoner_id:
                logger.debug("Summoner ID found. Getting player rank")
                main_rank_info = await self.get_player_rank(summoner_id)
                if main_rank_info:
                    for rank in main_rank_info:
                        tier = rank.get('tier')
                        division = rank.get('division')
                        if highest_rank_tier is None or rank_order[tier] > rank_order.get(highest_rank_tier, 0) or (
                            rank_order[tier] == rank_order.get(highest_rank_tier, 0) and 
                            division_order[division] > division_order.get(highest_rank_division, 0)
                        ):
                            highest_rank_tier = tier
                            highest_rank_division = division
                            highest_rank_info = {"rank_info": main_rank_info, "account_type": "main"}
            else:
                logger.error(f"Failed to retrieve Summoner ID for main account of {player_record['name']}.")
                return None
        else:
            logger.error(f"Failed to retrieve PUUID for main account of {player_record['name']}.")
            return None

        # Step 2: Check ranks for alt accounts via API
        alt_accounts = player_record.get('alt_accounts', [])
        for alt in alt_accounts:
            alt_puuid = await self.get_puuid(alt['game_name'], alt['tag_line'])
            if not alt_puuid:
                logger.warning(f"Failed to retrieve PUUID for alt {alt['game_name']}#{alt['tag_line']}. Skipping.")
                continue

            alt_summoner_id = await self.get_summoner_id(alt_puuid)
            if not alt_summoner_id:
                logger.warning(f"Failed to retrieve Summoner ID for alt {alt['game_name']}#{alt['tag_line']}. Skipping.")
                continue

            alt_rank_info = await self.get_player_rank(alt_summoner_id)
            if alt_rank_info:
                for rank in alt_rank_info:
                    tier = rank.get('tier')
                    division = rank.get('division')
                    if rank_order[tier] > rank_order.get(highest_rank_tier, 0) or (
                        rank_order[tier] == rank_order.get(highest_rank_tier, 0) and 
                        division_order[division] > division_order.get(highest_rank_division, 0)
                    ):
                        highest_rank_tier = tier
                        highest_rank_division = division
                        highest_rank_info = {"rank_info": alt_rank_info, "account_type": "alt"}

        return highest_rank_info



    async def get_match_history(self, puuid):
        """Get match history for the current and last split with retry."""
        url = f"https://americas.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
        headers = {'X-Riot-Token': config.RIOT_API}
        summer_split_start = int(self.get_summer_split_start().timestamp())
        
        params = {
            "startTime": summer_split_start,  # Get matches starting from the Summer Split
            "type": "ranked",
            "count": 100  # Retrieve more matches if necessary
        }

        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers, params=params) as response:
                        if response.status == 200:
                            match_ids = await response.json()
                            if not match_ids:
                                logger.info(f"No matches found for PUUID {puuid} in the specified period.")
                            logger.info(f"Retrieved match IDs for PUUID {puuid}: {match_ids}")
                            return match_ids
                        else:
                            error_message = await response.text()
                            if response.status == 429:
                                logger.error(f"Rate limited while fetching match history for {puuid}, attempt {attempt + 1}: {error_message}")
                            else:
                                logger.error(f"Error fetching match history for PUUID {puuid}, attempt {attempt + 1}: {error_message}")
                            
                            # Add delay if rate-limited or error encountered
                            await asyncio.sleep(2 ** attempt)
            except Exception as e:
                logger.error(f"Exception occurred while fetching match history for PUUID {puuid}, attempt {attempt + 1}: {e}")

        logger.error(f"Failed to retrieve match history for PUUID {puuid} after {max_retries} attempts.")
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
