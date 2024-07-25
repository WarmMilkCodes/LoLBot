import io
import logging
import json
from datetime import datetime

import discord
from discord.ext import commands
import app.config as config
import app.dbInfo as dbInfo

logger = logging.getLogger(__name__)


class ReplaysCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(description="Parses a League of Legends replay")
    async def upload(self, ctx, replay: discord.Attachment):
        await self.parse_replay(ctx, replay)

    @staticmethod
    async def parse_replay(ctx, replay: discord.Attachment):
        try:
            if not replay.filename.endswith('.rofl'):
                await ctx.respond("An error occurred. Please ensure the provided file is a valid .rofl file", ephemeral=True)
                return

            raw_bytes = await replay.read()
            buffer = io.BytesIO(raw_bytes)

            # Validate magic bytes
            magic = buffer.read(4)
            if magic != b'RIOT':
                await ctx.respond("An error occurred. Please ensure the provided file is a valid .rofl file", ephemeral=True)
                return

            # Extract replay data
            buffer.seek(-4, io.SEEK_END)
            json_length_raw = buffer.read(4)
            json_length = int.from_bytes(json_length_raw, "little")
            buffer.seek(-abs(json_length + 4), io.SEEK_CUR)
            json_raw = buffer.read(json_length)
            json_str = json_raw.decode('utf-8')
            replay_outer_data = json.loads(json_str)

            # Extract inner replay data
            replay_inner_json = replay_outer_data.get('statsJson')
            replay_inner_data = json.loads(replay_inner_json)

            players = []

            # Extract exact info from each player
            for p in replay_inner_data:
                new_player = PlayerStats(
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
                "replay_id": replay.id,
                "filename": replay.filename,
                "players": [player.to_dict() for player in players],
                "uploaded_at": datetime.utcnow()
            }
            dbInfo.replays_collection.insert_one(replay_data)

            # Create a detailed message
            embed = discord.Embed(title="Replay Parsed", color=discord.Color.green())
            for player in players:
                embed.add_field(
                    name=f"Player {player.uuid}",
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
        except Exception as e:
            logger.error(e)
            await ctx.respond("An unknown error occurred and has been logged. Please try again.", ephemeral=True)


class PlayerStats:
    def __init__(self, uuid, win=None, kills=None, deaths=None, assists=None, position=None):
        self.uuid = uuid
        self.win = win
        self.kills = kills
        self.deaths = deaths
        self.assists = assists
        self.position = position

    def to_dict(self):
        return {
            "uuid": self.uuid,
            "win": self.win,
            "kills": self.kills,
            "deaths": self.deaths,
            "assists": self.assists,
            "position": self.position
        }

def setup(bot):
    bot.add_cog(ReplaysCog(bot))
