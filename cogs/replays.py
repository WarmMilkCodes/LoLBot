import io
import logging
import json

import discord
from discord.ext import commands

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

            # extract exact info from each player
            for p in replay_inner_data:
                new_player = PlayerStats(p.get('PUUID'))
                new_player.set_win(p.get('WIN'))
                new_player.set_kills(p.get('CHAMPIONS_KILLED'))
                new_player.set_deaths(p.get('NUM_DEATHS'))
                new_player.set_assists(p.get('ASSISTS'))
                new_player.set_position(p.get('TEAM_POSITION'))
                players.append(new_player)

            # print some basic info for testing
            for p in players:
                logger.info(f"UUID: {p.uuid}")
                logger.info(f"Win/Loss: {p.win}")
                logger.info(f"Kills: {p.kills}")
                logger.info(f"Deaths: {p.deaths}")
                logger.info(f"Assists: {p.assists}")
                logger.info(f"Position: {p.position}")
                print('- ' * 20)

            await ctx.respond("Replay parsed successfully.")
        except Exception as e:
            logger.error(e)
            await ctx.respond("An unknown error occurred and has been logged. Please try again.")


class PlayerStats:
    def __init__(self, uuid):
        self.uuid = uuid
        self.kills = None
        self.deaths = None
        self.assists = None
        self.position = None
        self.win = None

    def set_kills(self, kills):
        self.kills = kills

    def set_deaths(self, deaths):
        self.deaths = deaths

    def set_assists(self, assists):
        self.assists = assists

    def set_position(self, position):
        self.position = position

    def set_win(self, win):
        self.win = win


def setup(bot):
    bot.add_cog(ReplaysCog(bot))