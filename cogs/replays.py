import io
import logging
import json
from datetime import datetime, timezone
import discord
from discord.ext import commands
import app.config as config
import app.dbInfo as dbInfo

logger = logging.getLogger('lol_log')

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

    @commands.slash_command(guild_ids=[config.lol_server],description="Submit UR League of Legends match replay")
    async def submit_replay(self, ctx, replay: discord.Attachment):
        await ctx.defer(ephemeral=True)
        match_metadata, players, match_id = await self.parse_replay(ctx, replay)
        if players:
            await self.send_replay_summary(ctx, match_metadata, players, match_id)
        await ctx.respond("Replay submitted successfully!", ephemeral=True)

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

    async def send_replay_summary(self, ctx, match_metadata, players, match_id):
        embed = discord.Embed(title="Replay Summary", description=f"Match ID: {match_id}", color=discord.Color.blue())
        
        # Adding player data to the embed
        for player in players:
            player_name = player.name if player.name else "Unknown"
            player_data = (
                f"**Team ID:** {player.team_id}\n"
                f"**Win/Loss:** {player.win}\n"
                f"**Kills:** {player.kills}\n"
                f"**Deaths:** {player.deaths}\n"
                f"**Assists:** {player.assists}\n"
                f"**Position:** {player.position}\n"
            )
            embed.add_field(name=f"Player: {player_name}", value=player_data, inline=False)

        logger.info("Sending embed with player data.")
        await ctx.send(embed=embed)



def setup(bot):
    bot.add_cog(ReplaysCog(bot))
