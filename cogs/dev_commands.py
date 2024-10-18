import app.config as config
import app.dbInfo as dbInfo
import discord, logging
from discord.ext import commands
from discord.commands import Option
import aiohttp
from datetime import datetime, timezone

logger = logging.getLogger('dev_cmd_log')

# Split dates for 2024
SPLITS = [
    {"start": datetime(2024, 1, 10, tzinfo=timezone.utc), "end": datetime(2024, 5, 14, tzinfo=timezone.utc), "name": "Spring Split"},
    {"start": datetime(2024, 5, 15, tzinfo=timezone.utc), "end": datetime(2024, 9, 25, tzinfo=timezone.utc), "name": "Summer Split"},
    {"start": datetime(2024, 9, 25, tzinfo=timezone.utc), "end": None, "name": "Fall Split"},  # End date unknown
]

class DevCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(guild_ids=[config.lol_server], description="Flush peak ranks from DB")
    @commands.has_role("Bot Guy")
    async def dev_flush_peaks(self, ctx):
        try:
            await ctx.defer()
            flush_peaks = dbInfo.player_collection.update_many(
                {},
                {"$unset": {"peak_rank": ""}}
            )
            logger.info(f"Finished flushing {flush_peaks.modified_count} peak ranks from DB.")
            await ctx.respond(f"Flushed {flush_peaks.modified_count} peak ranks.")
        
        except Exception as e:
            logger.error("Error flushing peak ranks: {e}")
            await ctx.respond("Error flushing peak ranks.")


    @commands.slash_command(guild_ids=[config.lol_server], description="Clear split count for specific user")
    @commands.has_role("Bot Guy")
    async def dev_clear_split(self, ctx, user: Option(discord.Member, "Select user you wish to clear the split count of.")):
        discord_id = user.id

        # Clear split counts for user
        dbInfo.player_collection.update_one(
            {"discord_id": discord_id},
             {"$set": {
                 "summer_split_game_count": 0,
                 "fall_split_game_count": 0
             }}
        )

        logger.info(f"Cleared split counts for user: {user.name} ({discord_id})")
        await ctx.respond(f"Cleared split counts for {user.name} ({discord_id})")

    @commands.slash_command(guild_ids=[config.lol_server], description="Run debug split check all users")
    @commands.has_role("Bot Guy")
    async def dev_split_check(self, ctx, user: discord.Option(discord.Member, "Select a user")):
        discord_id = user.id
        await ctx.defer(ephemeral=True)

        player_record = dbInfo.player_collection.find_one({"discord_id": discord_id, "left_at": None})

        if not player_record:
            await ctx.respond(f"Player not found or has left the server.", ephemeral=True)
            logger.info(f"Skipping player {discord_id} because not found or left server.")
            return

        logger.info(f"Running debug split check for player: {player_record['name']}")

        # Fetch existing split game counts
        summer_split_game_count = player_record.get('summer_split_game_count', 0)
        fall_split_game_count = player_record.get('fall_split_game_count', 0)
        total_game_count = summer_split_game_count + fall_split_game_count

        logger.info(f"Initial Summer Split Games: {summer_split_game_count}, Fall Split Games: {fall_split_game_count}")

        eligible_match_count = summer_split_game_count + fall_split_game_count

        # Fetch PUUID
        puuid = player_record.get('puuid')

        if not puuid:
            if not player_record.get('game_name') or not player_record.get('tag_line'):
                logger.warning(f"Missing game_name or tag_line for {player_record['name']}. Skipping split check.")
                await ctx.respond(f"Missing game_name or tag_line for {player_record['name']}.", ephemeral=True)
                return

            # Fetch PUUID if not already stored
            puuid = await self.get_puuid(player_record['game_name'], player_record['tag_line'])
            if not puuid:
                logger.warning(f"Failed to retrieve PUUID for {player_record['name']}.")
                await ctx.respond(f"Failed to retrieve PUUID for {player_record['name']}.", ephemeral=True)
                return
            else:
                dbInfo.player_collection.update_one(
                    {"discord_id": player_record['discord_id']},
                    {"$set": {"puuid": puuid}}
                )

        # Get match history (match IDs) for debugging
        match_history = await self.get_match_history(puuid)
        if match_history is None:
            logger.error(f"Failed to retrieve match history for {player_record['name']}")
            await ctx.respond(f"Failed to retrieve match history for {player_record['name']}.", ephemeral=True)
            return

        # Get the start and end dates for the Summer and Fall splits
        summer_split_start = SPLITS[1]["start"]
        summer_split_end = SPLITS[1]["end"]
        fall_split_start = SPLITS[2]["start"]

        logger.info(f"Summer Split Start: {summer_split_start}, Fall Split Start: {fall_split_start}")

        # Initialize counts for new games
        new_summer_split_games = 0
        new_fall_split_games = 0

        # Process match history for debugging purposes
        for match_id in match_history:
            match_details = await self.get_match_details(match_id)
            if not match_details:
                continue

            # Get the queue ID and game type for each match
            queue_id = match_details['info'].get('queueId', 'Unknown Queue ID')
            game_type = match_details['info'].get('gameType', 'Unknown Game Type')
            logger.info(f"Match {match_id} | Queue ID: {queue_id} | Game Type: {game_type}")

            # Only consider Solo/Duo games (queueId: 420)
            if queue_id != 420:
                logger.info(f"Skipping match {match_id} as it is not a Solo/Duo game.")
                continue

            # Get the game creation timestamp
            game_timestamp = match_details['info']['gameCreation'] / 1000
            game_date = datetime.fromtimestamp(game_timestamp, timezone.utc)

            logger.info(f"Match {match_id} timestamp: {game_date}")

            # Count games for the Summer Split
            if summer_split_start <= game_date <= summer_split_end:
                new_summer_split_games += 1

            # Count games for the Fall Split
            if game_date >= fall_split_start:
                new_fall_split_games += 1

            # Update total game count
            eligible_match_count = summer_split_game_count + new_summer_split_games + fall_split_game_count + new_fall_split_games

        logger.info(f"Player: {player_record['name']}, Summer Split Games: {new_summer_split_games}, Fall Split Games: {new_fall_split_games}, Total Games: {eligible_match_count}")

        # Add to DB
        dbInfo.player_collection.update_one(
            {"discord_id": discord_id },
            {"$set": {"eligible_match_count": eligible_match_count}}
            )

        # Send debug info back to the command invoker
        await ctx.respond(f"Debug split check completed for {player_record['name']}\n"
                        f"Queue ID/Game Type logged.\n"
                        f"Summer Split Games: {new_summer_split_games}, Fall Split Games: {new_fall_split_games}.\n"
                        f"Total Matches: {eligible_match_count}",
                        ephemeral=True)

    # Helper function to fetch PUUID
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

    # Helper function to fetch match history
    async def get_match_history(self, puuid):
        """Get match history for the current and last split."""
        url = f"https://americas.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
        headers = {'X-Riot-Token': config.RIOT_API}
        summer_split_start = int(SPLITS[1]["start"].timestamp())
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
                    return None

    # Helper function to fetch match details
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

def setup(bot):
    bot.add_cog(DevCommands(bot))