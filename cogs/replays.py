import io
import logging
import json

import discord
from discord.ext import commands

logger = logging.getLogger('lol_log')


class ReplaysCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.command(description="Submit replay for UR LoL match")
    async def submit_replay(self, ctx, replay: discord.Attachment):
        await self.parse_replay(ctx, replay)

    @staticmethod
    async def parse_replay(ctx, replay: discord.Attachment):
        try:
            if not replay.filename.endswith('.rofl'):
                await ctx.respond("An error occurred. Please ensure the provided file is a valid .rofl file", ephemeral=True)
                return

            raw_bytes = await replay.read()
            buffer = io.BytesIO(raw_bytes)

            # validate magic bytes
            magic = buffer.read(4)
            if not magic == b'RIOT':
                logger.warning(ctx.respond)
                await ctx.respond("An error occurred. Please ensure the provided file is a valid .rofl file", ephemeral=True)
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
                print('UUID: ' + p.uuid)
                print('Win/Loss: ' + p.win)
                print('Kills: ' + p.kills)
                print('Deaths: ' + p.deaths)
                print('Assists: ' + p.assists)
                print('Position: ' + p.position)
                print('- ' * 20)

            await ctx.respond("Replay submitted successfully.", ephemeral=True)
        except Exception as e:
            logger.error(e)
            ctx.respond("An unknown error occurred. Please try again.")


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