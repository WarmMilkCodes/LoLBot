import aiohttp
import discord
import logging
import pytz
from datetime import datetime, timezone
import app.config as config
import app.dbInfo as dbInfo
from discord.ext import commands, tasks

logger = logging.getLogger('lol_log')

# Split dates for 2024
SPLITS = [
    {"start": datetime(2024, 1, 10, tzinfo=timezone.utc), "end": datetime(2024, 5, 14, tzinfo=timezone.utc), "name": "Spring Split"},
    {"start": datetime(2024, 5, 15, tzinfo=timezone.utc), "end": datetime(2024, 9, 24, tzinfo=timezone.utc), "name": "Summer Split"},
    {"start": datetime(2024, 9, 25, tzinfo=timezone.utc), "end": None, "name": "Fall Split"},  # End date unknown
]

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
    @commands.has_permissions(administrator=True)
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
    @commands.has_permissions(administrator=True)
    async def check_ranks_and_eligibility(self, ctx):
        await ctx.defer(ephemeral=True)
        await self.update_ranks_and_check()
        await ctx.respond("Updated ranks and checked eligibility for all players.", ephemeral=True)

    async def update_ranks_and_check(self):
        logger.info("Updating ranks and checking eligibility for all players.")
        players = dbInfo.intent_collection.find({"Playing": "Yes"})

        for player in players:
            discord_id = player.get('ID')
            player_record = dbInfo.player_collection.find_one({"discord_id": discord_id})
            
            if not player_record:
                logger.error(f"Player record not found for discord_id {discord_id}")
                continue

            logger.info(f"Processing player: {player_record['name']}")
            puuid = None  # Initialize puuid

            # Update Rank
            if 'game_name' in player_record and 'tag_line' in player_record:
                puuid = await self.get_puuid(player_record['game_name'], player_record['tag_line'])
                if puuid:
                    if not player_record.get('puuid') or player_record.get('puuid') != puuid:
                        dbInfo.player_collection.update_one(
                            {"discord_id": player_record['discord_id']},
                            {"$set": {"puuid": puuid}}
                        )
                        logger.info(f"Stored PUUID for {player_record['name']}")
                else:
                    logger.warning(f"Failed to retrieve PUUID for {player_record['name']}. Skipping rank and eligibility update.")
                    continue

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
                    continue

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

            # Check Eligibility after updating rank
            if puuid:
                split_start = SPLITS[-1]['start'].timestamp()  # Use the start timestamp of the current split
                is_eligible = await self.check_eligibility(puuid, split_start)

                game_count = 30 if is_eligible else 0  # If eligible, set to 30, otherwise set to 0

                if player_record.get("eligible_for_split") != is_eligible or player_record.get("current_split_game_count") != game_count:
                    logger.info(f"Updating eligibility for {player_record['name']}: Eligible: {is_eligible}, Games: {game_count}")
                    dbInfo.player_collection.update_one(
                        {"discord_id": player_record['discord_id']},
                        {"$set": {
                            "eligible_for_split": is_eligible,
                            "last_eligibility_check": datetime.now(pytz.utc),
                            "current_split_game_count": game_count
                        }}
                    )
                else:
                    logger.info(f"No change in eligibility for {player_record['name']}")

        logger.info("Completed rank and eligibility check for all players.")

    async def check_eligibility(self, puuid, split_start_timestamp):
        """Check if a player has played at least 30 matches in the current split."""
        match_count = 0
        start = 0

        while match_count < 30:
            url = f"https://americas.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start={start}&count=20"
            headers = {'X-Riot-Token': config.RIOT_API}
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        matches = await response.json()
                        if not matches:
                            break  # No more matches to fetch

                        for match_id in matches:
                            match_url = f"https://americas.api.riotgames.com/lol/match/v5/matches/{match_id}"
                            async with session.get(match_url, headers=headers) as match_response:
                                if match_response.status == 200:
                                    match_data = await match_response.json()
                                    match_timestamp = match_data['info']['gameStartTimestamp'] / 1000

                                    if match_timestamp >= split_start_timestamp:
                                        match_count += 1

                                    if match_count >= 30:
                                        return True  # Player has met the eligibility criteria

                        if len(matches) < 20:
                            break  # Fewer than 20 matches returned, indicating the end of match history
                        start += 20
                    else:
                        logger.error(f"Error fetching match history for PUUID {puuid}: {await response.text()}")
                        return False

        return match_count >= 30

    async def get_puuid(self, game_name, tag_line):
        import urllib.parse
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
