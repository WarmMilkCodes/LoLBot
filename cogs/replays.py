import io
import logging
import json
from datetime import datetime, timezone
import discord
from discord.ext import commands
import app.config as config
import app.dbInfo as dbInfo

logger = logging.getLogger(__name__)

class PlayerStats:
    def __init__(self, name, uuid, win=None, kills=None, deaths=None, assists=None, position=None):
        self.name = name if name else 'Unknown'
        self.uuid = uuid
        self.win = win
        self.kills = kills
        self.deaths = deaths
        self.assists = assists
        self.position = position

    def to_dict(self):
        return {
            "name": self.name,
            "uuid": self.uuid,
            "win": self.win,
            "kills": self.kills,
            "deaths": self.deaths,
            "assists": self.assists,
            "position": self.position
        }

class ReplaysCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(description="Parses a League of Legends replay")
    async def upload(self, ctx, replay: discord.Attachment):
        await ctx.defer()
        players, replay_id = await self.parse_replay(ctx, replay)
        if players:
            await self.send_replay_summary(ctx, players, replay_id)

    @staticmethod
    async def parse_replay(ctx, replay: discord.Attachment):
        try:
            if not replay.filename.endswith('.rofl'):
                await ctx.respond("An error occurred. Please ensure the provided file is a valid .rofl file", ephemeral=True)
                return None, None

            raw_bytes = await replay.read()
            buffer = io.BytesIO(raw_bytes)

            # Validate magic bytes
            magic = buffer.read(4)
            if magic != b'RIOT':
                await ctx.respond("An error occurred. Please ensure the provided file is a valid .rofl file", ephemeral=True)
                return None, None

            # Extract replay data
            buffer.seek(-4, io.SEEK_END)
            json_length_raw = buffer.read(4)
            json_length = int.from_bytes(json_length_raw, "little")
            buffer.seek(-abs(json_length + 4), io.SEEK_CUR)
            json_raw = buffer.read(json_length)
            json_str = json_raw.decode('utf-8')
            replay_outer_data = json.loads(json_str)

            # Extract replay ID from the JSON data
            replay_id = replay_outer_data.get('ID', 'Unknown')
            if not replay_id:
                logger.warning("No replay ID found in JSON data.")

            # Check if replay already exists in the database
            if dbInfo.replays_collection.find_one({"replay_id": replay_id}):
                await ctx.respond("This replay has already been uploaded.", ephemeral=True)
                return None, None

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
                    position=p.get('TEAM_POSITION')
                )
                players.append(new_player)

            # Store replay data in MongoDB
            replay_data = {
                "replay_id": replay_id,
                "filename": replay.filename,
                "players": [player.to_dict() for player in players],
                "uploaded_at": datetime.now(timezone.utc)
            }
            dbInfo.replays_collection.insert_one(replay_data)

            return players, replay_id
        except Exception as e:
            logger.error(e)
            await ctx.respond("An unknown error occurred and has been logged. Please try again.", ephemeral=True)
            return None, None

    async def send_replay_summary(self, ctx, players, replay_id):
        embed = discord.Embed(title="Replay Summary", description=f"Replay ID: {replay_id}", color=discord.Color.blue())
        for player in players:
            embed.add_field(
                name=f"Player {player.name}",
                value=(
                    f"Win/Loss: {player.win}\n"
                    f"Kills: {player.kills}\n"
                    f"Deaths: {player.deaths}\n"
                    f"Assists: {player.assists}\n"
                    f"Position: {player.position}"
                ),
                inline=False
            )

        await ctx.respond(embed=embed)

def setup(bot):
    bot.add_cog(ReplaysCog(bot))
