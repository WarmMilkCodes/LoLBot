import io
import logging
import json
from datetime import datetime, timezone
import discord
from discord.ext import commands
import app.config as config
import app.dbInfo as dbInfo

logger = logging.getLogger(__name__)


class ReplaysCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(description="parses a league of legends replay")
    async def upload(self, ctx, replay: discord.Attachment):
        await self.parse_replay(ctx, replay)

    @staticmethod
    async def parse_replay(ctx, replay: discord.Attachment):
        try:
            if not replay.filename.endswith('.rofl'):
                await ctx.respond("An error occurred. Please ensure the provided file is a valid .rofl file")
                return

            raw_bytes = await replay.read()
            buffer = io.BytesIO(raw_bytes)

            # validate magic bytes
            magic = buffer.read(4)
            if not magic == b'RIOT':
                await ctx.respond("An error occurred. Please ensure the provided file is a valid .rofl file")
                return

            # extract replay data
            buffer.seek(-4, io.SEEK_END)
            json_length_raw = buffer.read(4)
            json_length = int.from_bytes(json_length_raw, "little")
            buffer.seek(-abs(json_length + 4), io.SEEK_CUR)
            json_raw = buffer.read(json_length)
            json_str = json_raw.decode('utf-8')
            replay_outer_data = json.loads(json_str)

            # extract inner replay data
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

            # Store replay data in database
            replay_data = {
                "replay_id": replay.id,
                "filename": [player.to_dict() for player in players],
                "uploaded_at": datetime.now(timezone.utc)
            }
            dbInfo.replays_collection.insert_one(replay_data)

            # log some basic info for testing
            for p in players:
                logger.info(f"UUID: {p.uuid}")
                logger.info(f"Win/Loss: {p.win}")
                logger.info(f"Kills: {p.kills}")
                logger.info(f"Deaths: {p.deaths}")
                logger.info(f"Assists: {p.assists}")
                logger.info(f"Position: {p.position}")
                print('- ' * 20)

            # Create embed message
            embed = discord.Embed(title="Replay Summary", color=discord.Color.blue())
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
            await ctx.respond("An unknown error occurred and has been logged. Please try again.")


class PlayerStats:
    def __init__(self, uuid, win=None, kills=None, deaths=None, assists=None, position=None):
        self.uuid = uuid
        self.kills = kills
        self.deaths = deaths
        self.assists = assists
        self.position = position
        self.win = win

def setup(bot):
    bot.add_cog(ReplaysCog(bot))