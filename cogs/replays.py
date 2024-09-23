import io
import logging
import json
from datetime import datetime, timezone
import discord
from discord.ext import commands
import app.config as config
import app.dbInfo as dbInfo

logger = logging.getLogger('replay_log')

class PlayerStats:
    def __init__(self, name, uuid, win, kills, deaths, assists, position, team_id):
        self.name = name if name else 'Unknown'
        self.uuid = uuid
        self.win = win
        self.kills = kills
        self.deaths = deaths
        self.assists = assists
        self.position = position
        self.team_id = team_id

    def to_dict(self):
        return {
            'name': self.name,
            'uuid': self.uuid,
            'win': self.win,
            'kills': self.kills,
            'deaths': self.deaths,
            'assists': self.assists,
            'position': self.position,
            'team_id': self.team_id
        }

class ReplaysCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.submissions = {}  # Store submission states

    @commands.slash_command(guild_ids=[config.lol_server], description="Start a replay submission")
    async def start_submission(self, ctx):
        # Create a thread for the user to submit replays
        thread = await ctx.channel.create_thread(name=f"Replay Submission by {ctx.author.name}")
        self.submissions[ctx.author.id] = {
            "thread": thread.id,
            "replays": []
        }
        await ctx.respond("Your replay thread has been created.", ephemeral=True)
        await thread.send(f"{ctx.author.mention}, you can now start uploading your replays in this thread.")

    @commands.slash_command(guild_ids=[config.lol_server], description="Finish uploading replays")
    async def finish(self, ctx):
        submission = self.submissions.get(ctx.author.id)
        if submission and ctx.channel.id == submission["thread"]:
            await self.send_series_summary(ctx, submission["replays"])
        else:
            await ctx.respond("Please start a submission first with /start_submission.", ephemeral=True)

    @commands.slash_command(guild_ids=[config.lol_server], description="Complete the submission process")
    async def complete_submission(self, ctx):
        submission = self.submissions.get(ctx.author.id)
        if submission and ctx.channel.id == submission["thread"]:
            thread = await ctx.guild.fetch_channel(submission["thread"])
            await thread.edit(locked=True)
            await ctx.respond("Submission completed and thread locked.")
            del self.submissions[ctx.author.id]
        else:
            await ctx.respond("No active submission found.", ephemeral=True)

    @staticmethod
    async def parse_replay(ctx, replay: discord.Attachment):
        try:
            if not replay.filename.endswith('.rofl'):
                await ctx.respond("An error occurred. Please ensure the provided file is a valid .rofl file", ephemeral=True)
                return None, None, None

            raw_bytes = await replay.read()
            buffer = io.BytesIO(raw_bytes)

            # Validate magic bytes
            magic = buffer.read(4)
            if magic != b'RIOT':
                await ctx.respond("An error occurred. Please ensure the provided file is a valid .rofl file", ephemeral=True)
                return None, None, None

            # Extract match ID from the file name
            match_id = replay.filename.split('-')[1].split('.')[0]

            # Check if replay already exists in the database
            if dbInfo.replays_collection.find_one({"match_id": match_id}):
                await ctx.respond("This replay has already been uploaded.", ephemeral=True)
                return None, None, None

            # Extract replay data
            buffer.seek(-4, io.SEEK_END)
            json_length_raw = buffer.read(4)
            json_length = int.from_bytes(json_length_raw, "little")
            buffer.seek(-abs(json_length + 4), io.SEEK_CUR)
            json_raw = buffer.read(json_length)
            json_str = json_raw.decode('utf-8')
            replay_outer_data = json.loads(json_str)

            # Extract match metadata
            match_metadata = {
                "game_creation": replay_outer_data.get('gameCreation'),
                "game_duration": replay_outer_data.get('gameDuration'),
                "game_mode": replay_outer_data.get('gameMode'),
                "game_type": replay_outer_data.get('gameType'),
                "platform_id": replay_outer_data.get('platformId'),
                "teams": {}
            }

            for team in replay_outer_data.get('teams', []):
                team_id = team.get('teamId')
                match_metadata["teams"][team_id] = {
                    "win": team.get('win'),
                    "first_blood": team.get('firstBlood'),
                    "first_tower": team.get('firstTower'),
                    "dragon_kills": team.get('dragonKills'),
                    "baron_kills": team.get('baronKills')
                }

            # Extract inner replay data
            replay_inner_json = replay_outer_data.get('statsJson')
            replay_inner_data = json.loads(replay_inner_json)

            players = []

            # Extract exact info from each player
            for p in replay_inner_data:
                player_name = p.get('NAME', 'Unknown')
                if not player_name:
                    logger.warning(f"Player with UUID {p.get('PUUID')} has no name.")

                new_player = PlayerStats(
                    name=player_name,
                    uuid=p.get('PUUID'),
                    win=p.get('WIN'),
                    kills=p.get('CHAMPIONS_KILLED'),
                    deaths=p.get('NUM_DEATHS'),
                    assists=p.get('ASSISTS'),
                    position=p.get('TEAM_POSITION'),
                    team_id=p.get('TEAM')
                )
                players.append(new_player)

            # Store replay data in MongoDB
            replay_data = {
                "match_id": match_id,
                "filename": replay.filename,
                "match_metadata": match_metadata,
                "players": [player.to_dict() for player in players],
                "uploaded_at": datetime.now(timezone.utc)
            }
            dbInfo.replays_collection.insert_one(replay_data)

            return match_metadata, players, match_id
        except Exception as e:
            logger.error(e)
            await ctx.respond("An unknown error occurred and has been logged. Please try again.", ephemeral=True)
            return None, None, None

    async def send_series_summary(self, ctx, replays):
        embed = discord.Embed(
            title="Series Summary", 
            description="Summary of all submitted replays", 
            color=discord.Color.blue()
        )

        team_wins = {"100": 0, "200": 0}
        team_players = {"100": [], "200": []}

        for match_metadata, players, match_id in replays:
            team_100_players = [p for p in players if p.team_id == 100]
            team_200_players = [p for p in players if p.team_id == 200]

            # Convert team ID to string to access the dictionary
            if match_metadata['teams']["100"]['win'] == 'Win':
                team_wins["100"] += 1
            else:
                team_wins["200"] += 1

            for player in team_100_players:
                team_players["100"].append(f"{player.name} (KDA: {player.kills}/{player.deaths}/{player.assists})")

            for player in team_200_players:
                team_players["200"].append(f"{player.name} (KDA: {player.kills}/{player.deaths}/{player.assists})")

        embed.add_field(
            name="Team 100 (Blue Side)",
            value="\n".join(team_players["100"]) or "No players",
            inline=False
        )
        embed.add_field(
            name="Team 200 (Red Side)",
            value="\n".join(team_players["200"]) or "No players",
            inline=False
        )

        # Determine series winner
        if team_wins["100"] > team_wins["200"]:
            winner = "Team 100 (Blue Side) wins the series!"
        elif team_wins["200"] > team_wins["100"]:
            winner = "Team 200 (Red Side) wins the series!"
        else:
            winner = "The series is tied!"

        embed.add_field(
            name="Series Result",
            value=winner,
            inline=False
        )

        await ctx.send(embed=embed, ephemeral=True)


    @commands.Cog.listener()
    async def on_message(self, message):
        # Check if the message is in a submission thread and contains attachments
        if message.author.bot:
            return

        submission = self.submissions.get(message.author.id)
        if submission and message.channel.id == submission["thread"]:
            for attachment in message.attachments:
                if attachment.filename.endswith('.rofl'):
                    match_metadata, players, match_id = await self.parse_replay(message, attachment)
                    if players:
                        submission["replays"].append((match_metadata, players, match_id))
                    await message.channel.send(f"Replay {attachment.filename} uploaded successfully!", ephemeral=True)
                else:
                    await message.channel.send("Please upload a valid .rofl file.", ephemeral=True)

def setup(bot):
    bot.add_cog(ReplaysCog(bot))
