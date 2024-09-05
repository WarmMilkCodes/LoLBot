import asyncio
import aiohttp
import discord
import logging
import pytz
from datetime import datetime, timezone
import app.config as config
import app.dbInfo as dbInfo
from discord.ext import commands, tasks
from discord.ui import Button, View

logger = logging.getLogger('lol_log')

# Split dates for 2024
SPLITS = [
    {"start": datetime(2024, 1, 10, tzinfo=timezone.utc), "end": datetime(2024, 5, 14, tzinfo=timezone.utc), "name": "Spring Split"},
    {"start": datetime(2024, 5, 15, tzinfo=timezone.utc), "end": datetime(2024, 9, 24, tzinfo=timezone.utc), "name": "Summer Split"},
    {"start": datetime(2024, 9, 25, tzinfo=timezone.utc), "end": None, "name": "Fall Split"},  # End date unknown
]

class ConfirmAltView(View):
    def __init__(self, game_name, tag_line, ctx, bot):
        super().__init__(timeout=60)  # Buttons will timeout after 60 seconds
        self.game_name = game_name
        self.tag_line = tag_line
        self.ctx = ctx  # Store ctx to use interaction details
        self.bot = bot

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Add alt account to the database
        alt_account = {"game_name": self.game_name, "tag_line": self.tag_line}

        dbInfo.player_collection.update_one(
            {"discord_id": self.ctx.author.id},  # Get user ID from ctx
            {"$push": {"alt_accounts": alt_account}}  # Push the alt account to the array
        )

        # Log the alt account report in a designated log channel
        alt_log_channel = self.bot.get_channel(config.riot_id_log_channel)
        if alt_log_channel:
            await alt_log_channel.send(f"{self.ctx.author.mention} reported a new alt account: {self.game_name}#{self.tag_line}")

        # Remove embed and buttons after confirmation and make it ephemeral
        await interaction.response.edit_message(content=f"Alt account {self.game_name}#{self.tag_line} has been added.", embed=None, view=None)

    @discord.ui.button(label="This button doesn't work - just click dismiss below.", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # Try to delete the message
            if interaction.message:
                await interaction.message.delete()
                logger.info(f"Deleted message for {interaction.user.name}")
        except Exception as e:
            logger.error(f"Failed to delete the message: {e}")


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

    async def validate_command_channel(self, ctx):
        """Check if the command is invoked in the correct channel."""
        if ctx.channel.id != config.riot_id_log_channel:
            riot_id_log_channel = ctx.guild.get_channel(config.riot_id_log_channel)
            await ctx.respond(f"This command can only be used in {riot_id_log_channel.mention}", ephemeral=True)
            return False
        return True
    
    @commands.slash_command(guild_ids=[config.lol_server], description="Report alt account")
    async def report_alt_account(self, ctx, game_name: discord.Option(str, "Enter game name (no '#' sign or numbers)"), tag_line: discord.Option(str, "Enter tag line (do not include game name or '#')")):
        await ctx.defer(ephemeral=True)

        try:
            if not await self.validate_command_channel(ctx):
                return

            # Fetch user's main account from database
            player_data = dbInfo.player_collection.find_one({"discord_id": ctx.author.id})

            if not player_data:
                return await ctx.respond(f"{ctx.author.mention}, you are not found in the database. Please reach out to staff.", ephemeral=True)

            # Create an embed to display the alt account info and buttons to confirm/cancel
            embed = discord.Embed(title="Confirm Alt Account", description=f"Game Name: **{game_name}**\nTag Line: **{tag_line}**", color=discord.Color.blue())

            # Create the view with Confirm and Cancel buttons
            view = ConfirmAltView(game_name, tag_line, ctx, self.bot)

            # Send the embed with buttons
            await ctx.respond(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.error(f"Error reporting alt account for {ctx.author.name}: {e}")
            await ctx.respond(f"An error occurred while reporting the alt account: {e}", ephemeral=True)


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
            puuid = None  # Initialize puuid

            # Check if game_name and tag_line are set
            if not player_record.get('game_name') or not player_record.get('tag_line'):
                logger.warning(f"Missing game_name or tag_line for {player_record['name']}. Skipping rank and eligibility update.")
                if riot_id_log_channel:
                    await riot_id_log_channel.send(
                        f"Missing Riot ID info for {player_record['name']} ({player_record['discord_id']}). Please ensure their game_name and tag_line are set."
                    )
                continue
            

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
                    if riot_id_log_channel:
                        await riot_id_log_channel.send(
                            f"Failed to retrieve PUUID for {player_record['name']} ({player_record['discord_id']}) - {player_record['game_name']}#{player_record['tag_line']}"
                        )
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
                    if riot_id_log_channel:
                        await riot_id_log_channel.send(
                            f"Failed to retrieve Summoner ID for {player_record['name']} ({player_record['discord_id']}) - PUUID: {puuid}"
                        )
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
                if player_record.get('eligible_for_split'):
                    logger.info(f"{player_record['name']} is already eligible. Skipping further eligibility checks.")
                    continue

                match_history = await self.get_match_history(puuid)
                if match_history is None:
                    logger.error(f"Failed to retrieve match history for {player_record['name']}. Skipping eligibility check.")
                    continue

                eligible_games = [match for match in match_history if self.is_eligible_match(match)]
                game_count = len(eligible_games)
                is_eligible = game_count >= 30

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

    async def get_match_history(self, puuid):
        url = f"https://americas.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
        headers = {'X-Riot-Token': config.RIOT_API}
        start_time = int(self.get_current_split_start().timestamp())
        params = {
            "startTime": start_time,
            "type": "ranked",
            "count": 30
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Error fetching match history for PUUID {puuid}: {await response.text()}")
                    return []

    def get_current_split_start(self):
        current_split = next((split for split in SPLITS if split['start'] <= datetime.now(timezone.utc) and (split['end'] is None or split['end'] >= datetime.now(timezone.utc))), None)
        return current_split['start'] if current_split else None

    async def is_eligible_match(self, match):
        match_timestamp = match.get('timestamp') / 1000  # Assuming match timestamp is in milliseconds
        return match_timestamp >= self.get_current_split_start().timestamp()

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
