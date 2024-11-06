import asyncio
import aiohttp
import discord
import logging
import pytz
from datetime import datetime, timezone
import config
import dbInfo
from discord.ext import commands, tasks
from discord.commands import Option

# Split dates for 2024
SPLITS = [
    {"start": datetime(2024, 1, 10, tzinfo=timezone.utc), "end": datetime(2024, 5, 14, tzinfo=timezone.utc), "name": "Spring Split"},
    {"start": datetime(2024, 5, 15, tzinfo=timezone.utc), "end": datetime(2024, 9, 25, tzinfo=timezone.utc), "name": "Summer Split"},
    {"start": datetime(2024, 9, 25, tzinfo=timezone.utc), "end": datetime(2024, 12, 31, tzinfo=timezone.utc), "name": "Fall Split"},  # Set an end date
]

# Define required game count for eligibility
REQUIRED_GAME_COUNT = 30

class PlayerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.task_started = False
        self.task_running = False
        self.bot.logger.info("PlayerCog loaded. Waiting for rank and eligibility check task to be started.")

    def cog_unload(self):
        if self.task_started:
            self.rank_and_eligibility_task.cancel()
            self.bot.logger.info("PlayerCog unloaded and task cancelled.")

    @commands.slash_command(guild_ids=[config.lol_server], description="Start the rank and eligibility check task")
    @commands.has_role("Bot Guy")
    async def dev_start_checks(self, ctx):
        if not self.task_started:
            self.rank_and_eligibility_task.start()
            self.task_started = True
            await ctx.respond("Rank and eligibility check task started and will run every 24 hours.", ephemeral=True)
            self.bot.logger.info("Rank and eligibility check task started by admin command.")
        else:
            await ctx.respond("Rank and eligibility check task is already running.", ephemeral=True)

    @tasks.loop(hours=24)
    async def rank_and_eligibility_task(self):
        if self.task_running:
            self.bot.logger.warning("Rank and eligibility check task is already running. Skipping this execution.")
            return
        
        self.task_running = True
        self.bot.logger.info("Rank and Eligibility update task triggered.")
        
        try:
            await self.update_ranks_and_check()
        finally:
            self.task_running = False
            self.bot.logger.info("Rank and eligibility check task completed.")

    @commands.slash_command(guild_ids=[config.lol_server], description="Update player ranks and check eligibility manually")
    @commands.has_role("Bot Guy")
    async def dev_check_players(self, ctx):
        await ctx.defer(ephemeral=True)
        await self.update_ranks_and_check()
        await ctx.respond("Updated ranks and checked eligibility for all players.", ephemeral=True)

    async def update_ranks_and_check(self):
        self.bot.logger.info("Updating ranks and checking eligibility for all players.")

        # Fetch all active players who have not left the server
        try:
            active_players_cursor = dbInfo.player_collection.find({"left_at": None})
            active_players = list(active_players_cursor)
        except Exception as e:
            self.bot.logger.error(f"Error fetching active players: {e}")
            return

        # Fetch intents where 'Playing': 'Yes'
        try:
            intents_cursor = dbInfo.intent_collection.find({"Playing": "Yes"})
            intents = list(intents_cursor)
            playing_discord_ids = set(intent['ID'] for intent in intents)  # Adjust 'ID' if necessary
        except Exception as e:
            self.bot.logger.error(f"Error fetching intents: {e}")
            return

        # Filter active players to include only those who are playing
        players_to_process = [player for player in active_players if player['discord_id'] in playing_discord_ids]

        total_players = len(players_to_process)
        processed_players = 0
        errors = 0

        for player_record in players_to_process:
            discord_id = player_record['discord_id']
            try:
                self.bot.logger.info(f"Processing player: {player_record.get('name')}")
                eligible_for_split = player_record.get('eligible_for_split', False)
                if eligible_for_split:
                    self.bot.logger.info(f"Player {player_record['name']} is already eligible for the current split. Skipping.")
                    continue

                # Process player and alt accounts to get highest rank
                highest_rank_info = await self.process_player_and_alts(player_record)
                if highest_rank_info is None:
                    continue  # Skip to next player if failed to get rank info

                # Update rank info
                dbInfo.player_collection.update_one(
                    {"discord_id": discord_id},
                    {"$set": {
                        "rank_info": highest_rank_info['rank_info'],
                        "last_updated": datetime.now(pytz.utc).strftime('%m-%d-%Y'),
                        "highest_account_type": highest_rank_info['account_type'],
                    }}
                )
                self.bot.logger.info(f"Updated rank information for player {player_record['name']} from their {highest_rank_info['account_type']} account.")

                # Collect PUUIDs from main and alt accounts
                puuids = await self.collect_puuids(player_record)
                if not puuids:
                    self.bot.logger.warning(f"No valid PUUIDs found for player {player_record['name']}. Skipping eligibility check.")
                    continue

                # Get eligible matches from all PUUIDs
                total_eligible_matches = 0
                for puuid in puuids:
                    eligible_matches = await self.get_match_history(puuid)
                    total_eligible_matches += eligible_matches

                # Update eligible match count
                if total_eligible_matches >= REQUIRED_GAME_COUNT:
                    self.bot.logger.info(f"Player {player_record['name']} has reached eligibility with {total_eligible_matches} matches.")
                    dbInfo.player_collection.update_one(
                        {"discord_id": discord_id},
                        {"$set": {"eligible_for_split": True, "eligible_match_count": total_eligible_matches}}
                    )
                else:
                    self.bot.logger.info(f"Player {player_record['name']} has {total_eligible_matches} eligible matches.")
                    dbInfo.player_collection.update_one(
                        {"discord_id": discord_id},
                        {"$set": {"eligible_match_count": total_eligible_matches}}
                    )

                processed_players += 1

                # Optional delay to prevent rate limiting
                await asyncio.sleep(1)

            except Exception as e:
                self.bot.logger.error(f"Error processing player {player_record['name']}: {e}")
                errors += 1
                continue

        self.bot.logger.info(f"Rank and eligibility update completed. Total players: {total_players}, Processed: {processed_players}, Errors: {errors}")

    @commands.slash_command(guild_ids=[config.lol_server], description="Update player rank and check eligibility for a single user")
    @commands.has_role("Bot Guy")
    async def dev_check_single_player(self, ctx, player_name: Option(discord.Member)):
        try:
            await ctx.defer(ephemeral=True)

            # Find the player by name in the database
            player_record = dbInfo.player_collection.find_one({"discord_id": player_name.id, "left_at": None})

            if not player_record:
                await ctx.respond(f"Player '{player_name.display_name}' not found or has left the server.", ephemeral=True)
                return

            self.bot.logger.info(f"Processing player: {player_record['name']}")

            eligible_for_split = player_record.get('eligible_for_split', False)
            if eligible_for_split:
                self.bot.logger.info(f"Player {player_record['name']} is already eligible for the current split.")
                await ctx.respond(f"Player '{player_name.display_name}' is already eligible for the current split.", ephemeral=True)
                return

            # Process player and alt accounts to get highest rank
            highest_rank_info = await self.process_player_and_alts(player_record)
            if highest_rank_info is None:
                await ctx.respond(f"Failed to retrieve rank information for '{player_name.display_name}'.", ephemeral=True)
                return

            # Update rank info
            dbInfo.player_collection.update_one(
                {"discord_id": player_record['discord_id']},
                {"$set": {
                    "rank_info": highest_rank_info['rank_info'],
                    "last_updated": datetime.now(pytz.utc).strftime('%m-%d-%Y'),
                    "highest_account_type": highest_rank_info['account_type'],
                }}
            )

            self.bot.logger.info(f"Updated rank information for player {player_record['name']} from their {highest_rank_info['account_type']} account.")

            # Collect PUUIDs from main and alt accounts
            puuids = await self.collect_puuids(player_record)
            if not puuids:
                await ctx.respond(f"No valid PUUIDs found for '{player_name.display_name}'.", ephemeral=True)
                return

            # Get eligible matches from all PUUIDs
            total_eligible_matches = 0
            for puuid in puuids:
                eligible_matches = await self.get_match_history(puuid)
                total_eligible_matches += eligible_matches

            # Update eligible match count
            if total_eligible_matches >= REQUIRED_GAME_COUNT:
                self.bot.logger.info(f"Player {player_record['name']} has reached eligibility with {total_eligible_matches} matches.")
                dbInfo.player_collection.update_one(
                    {"discord_id": player_record['discord_id']},
                    {"$set": {"eligible_for_split": True, "eligible_match_count": total_eligible_matches}}
                )
            else:
                self.bot.logger.info(f"Player {player_record['name']} has {total_eligible_matches} eligible matches.")
                dbInfo.player_collection.update_one(
                    {"discord_id": player_record['discord_id']},
                    {"$set": {"eligible_match_count": total_eligible_matches}}
                )

            await ctx.respond(f"Rank and eligibility check completed for '{player_name.display_name}'.", ephemeral=True)

        except Exception as e:
            await ctx.respond(f"There was an error processing {player_name}")
            self.bot.logger.error(f"Error processing ranks for {player_name}: {e}")

    async def collect_puuids(self, player_record):
        """Collect PUUIDs from main and alt accounts."""
        puuids = []

        # Main account
        main_puuid = player_record.get('puuid')
        if not main_puuid:
            main_puuid = await self.get_puuid(player_record['game_name'], player_record['tag_line'])
            if main_puuid:
                dbInfo.player_collection.update_one(
                    {"discord_id": player_record['discord_id']},
                    {"$set": {"puuid": main_puuid}}
                )
        if main_puuid:
            puuids.append(main_puuid)
        else:
            self.bot.logger.warning(f"Could not get PUUID for main account of {player_record['name']}.")

        # Alt accounts
        alt_accounts = player_record.get('alt_accounts', [])
        for alt in alt_accounts:
            alt_puuid = await self.get_puuid(alt['game_name'], alt['tag_line'])
            if alt_puuid:
                puuids.append(alt_puuid)
            else:
                self.bot.logger.warning(f"Failed to retrieve PUUID for alt {alt['game_name']}#{alt['tag_line']}.")

        # Remove duplicates
        puuids = list(set(puuids))
        return puuids

    async def process_player_and_alts(self, player_record):
        """Process a player and their alt accounts to find the highest rank."""
        highest_rank_info = None
        highest_rank_tier = None
        highest_rank_division = None

        # Define rank order for comparison
        rank_order = {
            "IRON": 1, "BRONZE": 2, "SILVER": 3, "GOLD": 4,
            "PLATINUM": 5, "EMERALD": 6, "DIAMOND": 7, "MASTER": 8, "GRANDMASTER": 9, "CHALLENGER": 10
        }
        division_order = {
            'IV': 1, 'III': 2, 'II': 3, 'I': 4
        }

        # Process main account
        main_puuid = player_record.get('puuid')
        if not main_puuid:
            main_puuid = await self.get_puuid(player_record['game_name'], player_record['tag_line'])
            if main_puuid:
                dbInfo.player_collection.update_one(
                    {"discord_id": player_record['discord_id']},
                    {"$set": {"puuid": main_puuid}}
                )
        if main_puuid:
            summoner_id = await self.get_summoner_id(main_puuid)
            if summoner_id:
                main_rank_info = await self.get_player_rank(summoner_id)
                if main_rank_info:
                    for rank in main_rank_info:
                        tier = rank.get('tier')
                        division = rank.get('division')
                        if highest_rank_tier is None or rank_order.get(tier, 0) > rank_order.get(highest_rank_tier, 0) or (
                            rank_order.get(tier, 0) == rank_order.get(highest_rank_tier, 0) and 
                            division_order.get(division, 0) > division_order.get(highest_rank_division, 0)
                        ):
                            highest_rank_tier = tier
                            highest_rank_division = division
                            highest_rank_info = {"rank_info": main_rank_info, "account_type": "main"}
            else:
                self.bot.logger.error(f"Failed to retrieve Summoner ID for main account of {player_record['name']}.")
        else:
            self.bot.logger.error(f"Failed to retrieve PUUID for main account of {player_record['name']}.")

        # Process alt accounts
        alt_accounts = player_record.get('alt_accounts', [])
        for alt in alt_accounts:
            alt_puuid = await self.get_puuid(alt['game_name'], alt['tag_line'])
            if not alt_puuid:
                self.bot.logger.warning(f"Failed to retrieve PUUID for alt {alt['game_name']}#{alt['tag_line']}. Skipping.")
                continue

            alt_summoner_id = await self.get_summoner_id(alt_puuid)
            if not alt_summoner_id:
                self.bot.logger.warning(f"Failed to retrieve Summoner ID for alt {alt['game_name']}#{alt['tag_line']}. Skipping.")
                continue

            alt_rank_info = await self.get_player_rank(alt_summoner_id)
            if alt_rank_info:
                for rank in alt_rank_info:
                    tier = rank.get('tier')
                    division = rank.get('division')
                    if rank_order.get(tier, 0) > rank_order.get(highest_rank_tier, 0) or (
                        rank_order.get(tier, 0) == rank_order.get(highest_rank_tier, 0) and 
                        division_order.get(division, 0) > division_order.get(highest_rank_division, 0)
                    ):
                        highest_rank_tier = tier
                        highest_rank_division = division
                        highest_rank_info = {"rank_info": alt_rank_info, "account_type": "alt"}

        if highest_rank_info is None:
            self.bot.logger.error(f"Failed to retrieve rank information for {player_record['name']} from any account.")
        return highest_rank_info

    async def get_match_history(self, puuid):
        """Get number of eligible matches for a given PUUID."""
        url = f"https://americas.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
        headers = {'X-Riot-Token': config.RIOT_API}
        summer_split_start = int(SPLITS[1]["start"].timestamp())
        fall_split_end = SPLITS[2]["end"] or datetime.now(timezone.utc)
        fall_split_end_timestamp = int(fall_split_end.timestamp())

        params = {
            "startTime": summer_split_start,
            "endTime": fall_split_end_timestamp,
            "type": "ranked",
            "count": 100
        }

        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers, params=params) as response:
                        if response.status == 200:
                            match_ids = await response.json()
                            if not match_ids:
                                self.bot.logger.info(f"No matches found for PUUID {puuid} in the specified period.")
                                return 0

                            self.bot.logger.info(f"Retrieved {len(match_ids)} match IDs for PUUID {puuid}")

                            eligible_count = 0
                            for match_id in match_ids:
                                match_details = await self.get_match_details(match_id)
                                if match_details:
                                    queue_id = match_details['info'].get('queueId')
                                    if queue_id == 420:
                                        game_creation = match_details['info'].get('gameCreation')
                                        game_date = datetime.fromtimestamp(game_creation / 1000, tz=timezone.utc)
                                        # Check if the match falls within the splits
                                        if self.is_match_in_splits(game_date):
                                            eligible_count += 1

                            self.bot.logger.info(f"Total eligible matches for PUUID {puuid}: {eligible_count}")
                            return eligible_count

                        else:
                            error_message = await response.text()
                            if response.status == 429:
                                self.bot.logger.error(f"Rate limited while fetching match history for {puuid}, attempt {attempt + 1}: {error_message}")
                            else:
                                self.bot.logger.error(f"Error fetching match history for PUUID {puuid}, attempt {attempt + 1}: {error_message}")

                            await asyncio.sleep(2 ** attempt)
            except Exception as e:
                self.bot.logger.error(f"Exception occurred while fetching match history for PUUID {puuid}, attempt {attempt + 1}: {e}")

        self.bot.logger.error(f"Failed to retrieve match history for PUUID {puuid} after {max_retries} attempts.")
        return 0

    def is_match_in_splits(self, game_date):
        """Check if the game date falls within the defined splits."""
        for split in SPLITS:
            split_start = split['start']
            split_end = split['end'] or datetime.now(timezone.utc)
            if split_start <= game_date <= split_end:
                return True
        return False

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
                    self.bot.logger.error(f"Error fetching match details for match ID {match_id}: {await response.text()}")
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
                    self.bot.logger.error(f"Error fetching PUUID for {game_name}#{tag_line}: {await response.text()}")
                    return None

    async def get_summoner_id(self, puuid):
        """Get Summoner ID from PUUID."""
        url = f"https://na1.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"
        headers = {'X-Riot-Token': config.RIOT_API}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    summoner_info = await response.json()
                    return summoner_info.get('id')
                else:
                    self.bot.logger.error(f"Error fetching Summoner ID for PUUID {puuid}: {await response.text()}")
                    return None

    async def get_player_rank(self, summoner_id):
        """Get player's rank information."""
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
                    self.bot.logger.error(f"Error fetching rank info for Summoner ID {summoner_id}: {await response.text()}")
                    return None

def setup(bot):
    bot.add_cog(PlayerCog(bot))