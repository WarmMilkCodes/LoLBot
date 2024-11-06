import app.config as config
import app.dbInfo as dbInfo
import discord, logging
from discord.ext import commands
from discord.commands import Option
import aiohttp, asyncio
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

    @commands.slash_command(guild_ids=[config.lol_server], description="Set eligibilty flag to False")
    @commands.has_role("Bot Guy")
    async def eligible_flag_false(self, ctx):
        try:
            await ctx.defer()

            dbInfo.player_collection.update_many(
                {"eligible_for_split": True},
                {"$set": {"eligible_for_split": False}}
            )

            await ctx.respond("Finished setting flags to false", ephemeral=True)

        except Exception as e:
            logger.error(f"Error setting flag to false: {e}")
            await ctx.respond(f"Error setting flags to false - check logs.")

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
            logger.error(f"Error flushing peak ranks: {e}")
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

    @commands.slash_command(guild_ids=[config.lol_server], description="Run debug split check for all playing users")
    @commands.has_role("Bot Guy")
    async def dev_split_check_all(self, ctx):
        await ctx.defer(ephemeral=True)

        # Step 1: Fetch all active players who are playing
        try:
            # Fetch all players who have not left the server
            active_players_cursor = dbInfo.player_collection.find({"left_at": None})
            active_players = list(active_players_cursor)
        except Exception as e:
            logger.error(f"Error fetching active players: {e}")
            await ctx.respond("Error fetching active players.", ephemeral=True)
            return

        total_players = len(active_players)
        processed_players = 0
        errors = 0

        # Prepare a set of Discord IDs of players who are currently playing
        try:
            # Fetch all playing intents where 'Playing' is True
            intents_cursor = dbInfo.intent_collection.find({"Playing": True})
            intents = list(intents_cursor)
            playing_discord_ids = set(intent['id'] for intent in intents)  # 'id' field in intent_collection
        except Exception as e:
            logger.error(f"Error fetching intents: {e}")
            await ctx.respond("Error fetching intents.", ephemeral=True)
            return

        # Filter active players to include only those who are playing
        players_to_process = [player for player in active_players if player['discord_id'] in playing_discord_ids]

        total_players_to_process = len(players_to_process)

        # Step 2: Loop through each player
        for player_record in players_to_process:
            discord_id = player_record['discord_id']
            try:
                logger.info(f"Running debug split check for player: {player_record['name']}")

                # Fetch existing split game counts
                summer_split_game_count = player_record.get('summer_split_game_count', 0)
                fall_split_game_count = player_record.get('fall_split_game_count', 0)

                # Fetch PUUID
                puuid = player_record.get('puuid')

                if not puuid:
                    if not player_record.get('game_name') or not player_record.get('tag_line'):
                        logger.warning(f"Missing game_name or tag_line for {player_record['name']}. Skipping split check.")
                        continue

                    # Fetch PUUID if not already stored
                    try:
                        puuid = await self.get_puuid(player_record['game_name'], player_record['tag_line'])
                        if not puuid:
                            logger.warning(f"Failed to retrieve PUUID for {player_record['name']}.")
                            continue
                        else:
                            dbInfo.player_collection.update_one(
                                {"discord_id": discord_id},
                                {"$set": {"puuid": puuid}}
                            )
                    except Exception as e:
                        logger.error(f"Error fetching PUUID for {player_record['name']}: {e}")
                        continue

                # Get match history
                try:
                    # Adjusted fall_split_end to handle None value
                    fall_split_end = SPLITS[2]["end"] or datetime.now(timezone.utc)
                    match_history = await self.get_match_history(puuid, SPLITS[1]["start"], fall_split_end)
                except Exception as e:
                    logger.error(f"Failed to retrieve match history for {player_record['name']}: {e}")
                    continue

                if not match_history:
                    logger.error(f"No match history found for {player_record['name']}")
                    continue

                # Initialize counts for new games
                new_summer_split_games = 0
                new_fall_split_games = 0

                # Process match history
                for match_id in match_history:
                    try:
                        match_details = await self.get_match_details(match_id)
                    except Exception as e:
                        logger.error(f"Error fetching match details for {match_id}: {e}")
                        continue

                    if not match_details:
                        continue

                    # Get the queue ID
                    queue_id = match_details['info'].get('queueId', 'Unknown Queue ID')

                    # Only consider Solo/Duo games (queueId: 420)
                    if queue_id != 420:
                        continue

                    # Get the game creation timestamp
                    game_timestamp = match_details['info']['gameCreation'] / 1000
                    game_date = datetime.fromtimestamp(game_timestamp, timezone.utc)

                    # Count games for the Summer Split
                    if SPLITS[1]["start"] <= game_date <= SPLITS[1]["end"]:
                        new_summer_split_games += 1

                    # Count games for the Fall Split
                    if SPLITS[2]["start"] <= game_date <= fall_split_end:
                        new_fall_split_games += 1

                # Update total game count
                eligible_match_count = (summer_split_game_count + new_summer_split_games +
                                        fall_split_game_count + new_fall_split_games)

                logger.info(f"Player: {player_record['name']}, Summer Split Games: {new_summer_split_games}, "
                            f"Fall Split Games: {new_fall_split_games}, Total Games: {eligible_match_count}")

                # Update counts in the database
                dbInfo.player_collection.update_one(
                    {"discord_id": discord_id},
                    {
                        "$inc": {
                            "summer_split_game_count": new_summer_split_games,
                            "fall_split_game_count": new_fall_split_games,
                            "eligible_match_count": new_summer_split_games + new_fall_split_games
                        }
                    }
                )

                processed_players += 1

                # Optional: Add a delay to prevent hitting rate limits
                await asyncio.sleep(1)  # Adjust as needed

            except Exception as e:
                logger.error(f"Error processing player {player_record['name']}: {e}")
                errors += 1
                continue

        # Send summary back to the command invoker
        await ctx.respond(
            f"Debug split check completed for all playing users.\n"
            f"Total Players: {total_players_to_process}\n"
            f"Processed Players: {processed_players}\n"
            f"Errors: {errors}",
            ephemeral=True
        )


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
