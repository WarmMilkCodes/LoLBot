import aiohttp, discord
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
        self.rank_update_task_started = False
        self.eligibility_check_task_started = False
        logger.info("PlayerCog loaded. Waiting for rank update and eligibility check tasks to be started.")

    def cog_unload(self):
        if self.rank_update_task_started:
            self.rank_update_task.cancel()
            logger.info("PlayerCog unloaded and rank task cancelled.")
        if self.eligibility_check_task_started:
            self.eligibility_check_task.cancel()
            logger.info("PlayerCog unloaded and eligibility task cancelled.")

    @commands.slash_command(guild_ids=[config.lol_server], description="Start the rank update task")
    @commands.has_permissions(administrator=True)
    async def start_rank_update_task(self, ctx):
        if not self.rank_update_task_started:
            self.rank_update_task.start()
            self.rank_update_task_started = True
            await ctx.respond("Rank update task started and will run every 24 hours.", ephemeral=True)
            logger.info("Rank update task started by admin command.")
        else:
            await ctx.respond("Rank update task is already running.", ephemeral=True)

    @commands.slash_command(guild_ids=[config.lol_server], description="Start the eligibility check task")
    @commands.has_permissions(administrator=True)
    async def start_eligibility_check_task(self, ctx):
        if not self.eligibility_check_task_started:
            self.eligibility_check_task.start()
            self.eligibility_check_task_started = True
            await ctx.respond("Eligibility check task started and will run every 12 hours.", ephemeral=True)
            logger.info("Eligibility task started by admin command")
        else:
            await ctx.respond("Eligibility check task is already running.", ephemeral=True)


    @tasks.loop(hours=24)
    async def rank_update_task(self):
        logger.info("Rank update task triggered.")
        await self.update_all_ranks()

    @tasks.loop(hours=12)
    async def eligibility_check_task(self):
        logger.info("Eligibility check task triggered.")
        await self.check_player_eligibility()


    @commands.slash_command(guild_ids=[config.lol_server], description="Update player ranks manually")
    @commands.has_permissions(administrator=True)
    async def update_ranks(self, ctx):
        await ctx.defer()
        await self.update_all_ranks()
        await ctx.respond("Updated ranks for all players", ephemeral=True)

    async def update_all_ranks(self):
        logger.info("Updating ranks for all players.")
        failure_channel = self.bot.get_channel(config.failure_log_channel)
        players = dbInfo.intent_collection.find({"Playing": "Yes"})

        for player in players:
            discord_id = player.get('ID')
            player_record = dbInfo.player_collection.find_one({"discord_id": discord_id})
            
            if not player_record:
                logger.error(f"Player record not found for discord_id {discord_id}")
                continue

            logger.info(f"Processing player: {player_record['name']}")
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
                    # Fallback check for existing rank data
                    if player_record.get('rank_info'):
                        logger.warning(f"Failed to retrieve PUUID for {player_record['name']}. Using stored rank info.")
                    else:
                        await self.report_failure(failure_channel, player_record['name'], 'Failed to retrieve PUUID')
                        await self.assign_not_eligible_role(player_record['discord_id'])
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
                    # Fallback check for existing rank data
                    if player_record.get('rank_info'):
                        logger.warning(f"Failed to retrieve Summoner ID for {player_record['name']}. Using stored rank info.")
                    else:
                        await self.report_failure(failure_channel, player_record['name'], 'Failed to retrieve Summoner ID')
                        await self.assign_not_eligible_role(player_record['discord_id'])
                    continue

                rank_info = await self.get_player_rank(summoner_id)
                if rank_info:
                    date_str = datetime.now(pytz.utc).strftime('%m-%d-%Y')
                    historical_rank_info = player_record.get('historical_rank_info', {})

                    if date_str in historical_rank_info and historical_rank_info[date_str] == rank_info:
                        logger.info(f"Rank information for player {player_record['name']} is unchanged for today.")
                        continue

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
                else:
                    # Fallback check for existing rank data
                    if player_record.get('rank_info'):
                        logger.warning(f"Unable to retrieve rank info for {player_record['name']} with API. Using stored rank info.")
                    else:
                        await self.report_failure(failure_channel, player_record['name'], 'Unable to retrieve rank info')
                        await self.assign_not_eligible_role(player_record['discord_id'])
                        dbInfo.player_collection.update_one({"discord_id": player_record['discord_id']}, {"$set": {"eligible": "False"}})
            else:
                logger.error(f"Player {player_record['name']} does not have game_name and tag_line set.")
                await self.report_failure(failure_channel, player_record['name'], 'Riot ID is not set or is invalid.')
                await self.assign_not_eligible_role(player_record['discord_id'])

        logger.info("Completed updating ranks for all players.")

    async def check_player_eligibility(self):
        logger.info("Checking player eligibility for the current split.")
        failure_channel = self.bot.get_channel(config.failure_log_channel)
        players = dbInfo.intent_collection.find({"Playing": "Yes"})

        for player in players:
            discord_id = player.get('ID')
            player_record = dbInfo.player_collection.find_one({"discord_id": discord_id})
            
            if not player_record:
                logger.error(f"Player record not found for discord_id {discord_id}")
                continue

            logger.info(f"Processing player: {player_record['name']} for eligibility check.")
            puuid = player_record.get('puuid')
            if not puuid:
                logger.warning(f"No PUUID found for player {player_record['name']}. Skipping eligibility check.")
                continue

            match_history = await self.get_match_history(puuid)
            eligible_games = [match for match in match_history if self.is_eligible_match(match)]

            if len(eligible_games) >= 30:
                logger.info(f"Player {player_record['name']} has met the eligibility requirements.")
                # Update eligibility in database or notify
            else:
                logger.warning(f"Player {player_record['name']} has not met the eligibility requirements.")
                await self.report_failure(failure_channel, player_record['name'], 'Player has not met the minimum game requirement for the split.')
                #await self.assign_not_eligible_role(player_record['discord_id'])

        logger.info("Completed checking eligibility for all players.")

    async def get_match_history(self, puuid):
        # Implement API call to fetch match history
        url = f"https://<REGION>.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
        headers = {'X-Riot-Token': config.RIOT_API}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Error fetching match history for PUUID {puuid}: {await response.text()}")
                    return []
                
    async def is_eligible_match(self, summoner_id):
        """Check if the player has played the minimum number of matches in the current split."""
        current_split = next((split for split in SPLITS if split['start'] <= datetime.now(timezone.utc) and (split['end'] is None or split['end'] >= datetime.now(timezone.utc))), None)
        
        if not current_split:
            logger.error("No active split found.")
            return False

        start_timestamp = int(current_split['start'].timestamp() * 1000)  # Convert to milliseconds
        match_history_url = f"https://na1.api.riotgames.com/lol/match/v4/matchlists/by-account/{summoner_id}?beginTime={start_timestamp}"

        headers = {'X-Riot-Token': config.RIOT_API}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(match_history_url, headers=headers) as response:
                if response.status == 200:
                    match_history = await response.json()
                    total_matches = len(match_history.get('matches', []))
                    logger.info(f"Player with summoner ID {summoner_id} has played {total_matches} matches in the current split.")
                    return total_matches >= 30  # Check if the player has played at least 30 matches
                else:
                    logger.error(f"Error fetching match history for Summoner ID {summoner_id}: {await response.text()}")
                    return False


    async def assign_not_eligible_role(self, discord_id):
        guild = self.bot.get_guild(config.lol_server)
        member = guild.get_member(discord_id)
        if member:
            not_eligible_role = discord.utils.get(guild.roles, name="Not Eligible")
            if not_eligible_role:
                await member.add_roles(not_eligible_role)
                logger.info(f"Assigned Not Eligible role to {member.name}")
            else:
                logger.error(f"Not Eligible role not found in the server.")
        else:
            logger.error(f"Member with discord_id {discord_id} not found.")

    async def get_puuid(self, game_name, tag_line):
        import urllib.parse
        encoded_game_name = urllib.parse.quote(game_name)
        encoded_tag_line = urllib.parse.quote(tag_line)

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

    async def report_failure(self, channel, player_name, reason):
        if channel:
            message = f"Player: {player_name} | Error: {reason}"
            await channel.send(message)

    


def setup(bot):
    bot.add_cog(PlayerCog(bot))
