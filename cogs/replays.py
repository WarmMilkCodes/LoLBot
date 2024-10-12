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
    def __init__(self,
                 assists=None,
                 baron_kills=None,
                 barracks_killed=None,
                 barracks_takedowns=None,
                 champions_killed=None,
                 double_kills=None,
                 dragon_kills=None,
                 exp=None,
                 gold_earned=None,
                 id=None,
                 individual_position=None,
                 largest_attack_damage=None,
                 largest_multi_kill=None,
                 magic_damage_dealt_to_champions=None,
                 minions_killed=None,
                 missions_championskilled=None,
                 missions_creepscore=None,
                 missions_creepscoreby10minutes=None,
                 missions_goldperminute=None,
                 missions_minionskilled=None,
                 missions_takedownsbefore15min=None,
                 name=None,
                 num_deaths=None,
                 penta_kills=None,
                 physical_damage_dealt_player=None,
                 physical_damage_dealt_to_champions=None,
                 physical_damage_taken=None,
                 player_position=None,
                 puuid=None,
                 quadra_kills=None,
                 rift_herald_kills=None,
                 sight_wards_bought_in_game=None,
                 skin=None,
                 team_id=None,
                 team_code=None,
                 team_objective=None,
                 team_position=None,
                 time_ccing_others=None,
                 total_damage_dealt=None,
                 total_damage_dealt_to_champions=None,
                 total_damage_taken=None,
                 total_heal_on_teammates=None,
                 total_time_crowd_control_dealt=None,
                 total_time_crowd_control_dealt_to_champions=None,
                 total_time_spent_dead=None,
                 total_units_healed=None,
                 triple_kills=None,
                 true_damage_dealt_player=None,
                 true_damage_dealt_to_champions=None,
                 true_damage_taken=None,
                 victory_point_total=None,
                 vision_score=None,
                 vision_wards_bought_in_game=None,
                 win=None):
        self.assists = assists
        self.baron_kills = baron_kills
        self.barracks_killed = barracks_killed
        self.barracks_takedowns = barracks_takedowns
        self.champions_killed = champions_killed
        self.double_kills = double_kills
        self.dragon_kills = dragon_kills
        self.exp = exp
        self.gold_earned = gold_earned
        self.id = id
        self.individual_position = individual_position
        self.largest_attack_damage = largest_attack_damage
        self.largest_multi_kill = largest_multi_kill
        self.magic_damage_dealt_to_champions = magic_damage_dealt_to_champions
        self.minions_killed = minions_killed
        self.missions_championskilled = missions_championskilled
        self.missions_creepscore = missions_creepscore
        self.missions_creepscoreby10minutes = missions_creepscoreby10minutes
        self.missions_goldperminute = missions_goldperminute
        self.missions_minionskilled = missions_minionskilled
        self.missions_takedownsbefore15min = missions_takedownsbefore15min
        self.name = name
        self.num_deaths = num_deaths
        self.penta_kills = penta_kills
        self.physical_damage_dealt_player = physical_damage_dealt_player
        self.physical_damage_dealt_to_champions = physical_damage_dealt_to_champions
        self.physical_damage_taken = physical_damage_taken
        self.player_position = player_position
        self.puuid = puuid
        self.quadra_kills = quadra_kills
        self.rift_herald_kills = rift_herald_kills
        self.sight_wards_bought_in_game = sight_wards_bought_in_game
        self.skin = skin
        self.team_id = team_id
        self.team_code = team_code
        self.team_objective = team_objective
        self.team_position = team_position
        self.time_ccing_others = time_ccing_others
        self.total_damage_dealt = total_damage_dealt
        self.total_damage_dealt_to_champions = total_damage_dealt_to_champions
        self.total_damage_taken = total_damage_taken
        self.total_heal_on_teammates = total_heal_on_teammates
        self.total_time_crowd_control_dealt = total_time_crowd_control_dealt
        self.total_time_crowd_control_dealt_to_champions = total_time_crowd_control_dealt_to_champions
        self.total_time_spent_dead = total_time_spent_dead
        self.total_units_healed = total_units_healed
        self.triple_kills = triple_kills
        self.true_damage_dealt_player = true_damage_dealt_player
        self.true_damage_dealt_to_champions = true_damage_dealt_to_champions
        self.true_damage_taken = true_damage_taken
        self.victory_point_total = victory_point_total
        self.vision_score = vision_score
        self.vision_wards_bought_in_game = vision_wards_bought_in_game
        self.win = win

    def to_dict(self):
        return {
            'assists': self.assists,
            'baron_kills': self.baron_kills,
            'barracks_killed': self.barracks_killed,
            'barracks_takedowns': self.barracks_takedowns,
            'champions_killed': self.champions_killed,
            'double_kills': self.double_kills,
            'dragon_kills': self.dragon_kills,
            'exp': self.exp,
            'gold_earned': self.gold_earned,
            'id': self.id,
            'individual_position': self.individual_position,
            'largest_attack_damage': self.largest_attack_damage,
            'largest_multi_kill': self.largest_multi_kill,
            'magic_damage_dealt_to_champions': self.magic_damage_dealt_to_champions,
            'minions_killed': self.minions_killed,
            'missions_championskilled': self.missions_championskilled,
            'missions_creepscore': self.missions_creepscore,
            'missions_creepscoreby10minutes': self.missions_creepscoreby10minutes,
            'missions_goldperminute': self.missions_goldperminute,
            'missions_minionskilled': self.missions_minionskilled,
            'missions_takedownsbefore15min': self.missions_takedownsbefore15min,
            'name': self.name,
            'num_deaths': self.num_deaths,
            'penta_kills': self.penta_kills,
            'physical_damage_dealt_player': self.physical_damage_dealt_player,
            'physical_damage_dealt_to_champions': self.physical_damage_dealt_to_champions,
            'physical_damage_taken': self.physical_damage_taken,
            'player_position': self.player_position,
            'puuid': self.puuid,
            'quadra_kills': self.quadra_kills,
            'rift_herald_kills': self.rift_herald_kills,
            'sight_wards_bought_in_game': self.sight_wards_bought_in_game,
            'skin': self.skin,
            'team_id': self.team_id,
            'team_code': self.team_code,
            'team_objective': self.team_objective,
            'team_position': self.team_position,
            'time_ccing_others': self.time_ccing_others,
            'total_damage_dealt': self.total_damage_dealt,
            'total_damage_dealt_to_champions': self.total_damage_dealt_to_champions,
            'total_damage_taken': self.total_damage_taken,
            'total_heal_on_teammates': self.total_heal_on_teammates,
            'total_time_crowd_control_dealt': self.total_time_crowd_control_dealt,
            'total_time_crowd_control_dealt_to_champions': self.total_time_crowd_control_dealt_to_champions,
            'total_time_spent_dead': self.total_time_spent_dead,
            'total_units_healed': self.total_units_healed,
            'triple_kills': self.triple_kills,
            'true_damage_dealt_player': self.true_damage_dealt_player,
            'true_damage_dealt_to_champions': self.true_damage_dealt_to_champions,
            'true_damage_taken': self.true_damage_taken,
            'victory_point_total': self.victory_point_total,
            'vision_score': self.vision_score,
            'vision_wards_bought_in_game': self.vision_wards_bought_in_game,
            'win': self.win
        }


class ReplaysCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.submissions = {} 

    @commands.slash_command(guild_ids=[config.lol_server], description="Start a replay submission")
    @commands.has_any_role("League Ops", "Bot Guy", "General Managers", "Franchise Owner")
    async def start_submission(self, ctx):
        # Create a thread for the user to submit replays
        thread = await ctx.channel.create_thread(name=f"Replay Submission by {ctx.author.name}")
        self.submissions[ctx.author.id] = {
            "thread": thread.id,
            "replays": [],
            "winner": "",
            "loser": ""
        }
        await ctx.respond("Your replay thread has been created.", ephemeral=True)
        await thread.send(f"{ctx.author.mention}, you can now start uploading your replays in this thread.")

    @commands.slash_command(guild_ids=[config.lol_server], description="Start a replay submission")
    @commands.has_any_role("League Ops", "Bot Guy")
    async def associate_puuid(self, ctx, discord_id, puuid):
        try:
            criteria = {'discord_id': int(discord_id)}
            player_info = dbInfo.player_collection.find_one(criteria)
            if player_info is None:
                await ctx.respond(f"player not found via discord id: {discord_id}")
                return
            new_puuid = {"$set": {"raw_puuid": puuid}}
            dbInfo.player_collection.update_one(criteria, new_puuid)

            embed = discord.Embed(
                title="Success!",
                description="",
                color=discord.Color.green()
            )
            embed.add_field(
                name="Name",
                value=player_info['name'],
                inline=False
            )
            embed.add_field(
                name="PUUID",
                value=puuid,
                inline=False
            )
            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(e)
            await ctx.respond("An unknown error occurred and has been logged. Please try again.")
            return

    @commands.slash_command(guild_ids=[config.lol_server], description="Start a replay submission")
    @commands.has_any_role("League Ops", "Bot Guy")
    async def extract_puuids(self, ctx, replay: discord.Attachment):
        try:
            if not replay.filename.endswith('.rofl'):
                await ctx.respond("An error occurred. Please ensure the provided file is a valid .rofl file.")
                return None

            raw_bytes = await replay.read()
            buffer = io.BytesIO(raw_bytes)

            # Validate magic bytes
            magic = buffer.read(4)
            if magic != b'RIOT':
                await ctx.respond("An error occurred. Please ensure the provided file is a valid .rofl file.")
                return None

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
                "teams": []
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
                    puuid=p.get('PUUID'),
                    skin=p.get('SKIN'),
                    team_id=p.get('TEAM'),
                    team_position=p.get('TEAM_POSITION'),
                    win=p.get('WIN')
                )
                players.append(new_player)

            embed = discord.Embed(
                title="PUUID extract",
                description="",
                color=discord.Color.blue()
            )

            for p in players:
                embed.add_field(
                    name=f"{p.name} - {p.skin}",
                    value=f"{p.puuid}",
                    inline=False
                )

            await ctx.send(embed=embed)
        except Exception as e:
            logger.error(e)
            await ctx.respond("An unknown error occurred and has been logged. Please try again.")
            return

    @commands.slash_command(guild_ids=[config.lol_server], description="Finish uploading replays")
    @commands.has_any_role("League Ops", "Bot Guy", "General Managers", "Franchise Owner")
    async def finish(self, ctx):
        submission = self.submissions.get(ctx.author.id)
        if submission and ctx.channel.id == submission["thread"]:
            await self.send_series_summary(ctx, submission)
        else:
            await ctx.respond("Please start a submission first with /start_submission.", ephemeral=True)

    @commands.slash_command(guild_ids=[config.lol_server], description="Complete the submission process")
    @commands.has_any_role("League Ops", "Bot Guy", "General Managers", "Franchise Owner")
    async def complete_submission(self, ctx):
        submission = self.submissions.get(ctx.author.id)
        if submission and ctx.channel.id == submission["thread"]:
            # save down the replays to the database
            for replay_data in submission["replays"]:
                dbInfo.replays_collection.insert_one(replay_data)
            if await self.add_win(submission['winner']) is False:
                await ctx.respond("An error occurred issuing a win")
            if await self.add_loss(submission['loser']) is False:
                await ctx.respond("An error occurred issuing a loss")
            thread = await ctx.guild.fetch_channel(submission["thread"])
            await thread.edit(locked=True)
            await ctx.respond("Submission completed and thread locked.")
            del self.submissions[ctx.author.id]
        else:
            await ctx.respond("No active submission found.", ephemeral=True)

    @staticmethod
    async def determine_team(puuid):
        criteria = {'raw_puuid': puuid}
        player_info = dbInfo.player_collection.find_one(criteria)
        if player_info is None:
            return None
        return player_info['team']

    @staticmethod
    async def add_win(team_code):
        criteria = {'team_code': team_code}
        team_info = dbInfo.team_collection.find_one(criteria)
        if team_info is None:
            return False
        if 'wins' in team_info:
            dbInfo.team_collection.update_one(criteria, {"$inc": {"wins": 1}})
        else:
            new_win = {"$set": {"wins": 1}}
            dbInfo.team_collection.update_one(criteria, new_win)
        return True

    @staticmethod
    async def add_loss(team_code):
        criteria = {'team_code': team_code}
        team_info = dbInfo.team_collection.find_one(criteria)
        if team_info is None:
            return False
        if 'losses' in team_info:
            dbInfo.team_collection.update_one(criteria, {"$inc": {"losses": 1}})
        else:
            new_win = {"$set": {"losses": 1}}
            dbInfo.team_collection.update_one(criteria, new_win)
        return True

    @staticmethod
    async def determine_player_name(puuid):
        criteria = {'raw_puuid': puuid}
        player_info = dbInfo.player_collection.find_one(criteria)
        if player_info is None:
            return None
        return player_info['name']

    @staticmethod
    async def fetch_team_logo_url(team_code):
        criteria = {'team_code': team_code}
        team_info = dbInfo.team_collection.find_one(criteria)
        if team_info is None or team_info['logo'] is None:
            return ""
        return f"https://lol-web-app.onrender.com{team_info['logo']}"

    @staticmethod
    async def parse_replay(message, replay: discord.Attachment):
        try:
            if not replay.filename.endswith('.rofl'):
                await message.channel.send("An error occurred. Please ensure the provided file is a valid .rofl file.")
                return None

            raw_bytes = await replay.read()
            buffer = io.BytesIO(raw_bytes)

            # Validate magic bytes
            magic = buffer.read(4)
            if magic != b'RIOT':
                await message.channel.send("An error occurred. Please ensure the provided file is a valid .rofl file.")
                return None

            # Extract match ID from the file name
            file_name = replay.filename
            if file_name.find("NA1-") == -1 or file_name.find(".rofl") == -1:
                await message.channel.send("Replay names cannot be changed. The expected format is 'NA1-##########.rofl'.")
                return None

            match_id = file_name.split('-')[1].split('.')[0]

            # Check if replay already exists in the database
            if dbInfo.replays_collection.find_one({"match_id": match_id}):
                await message.channel.send("This replay has already been uploaded.")
                return None

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
                "teams": []
            }

            for team in replay_outer_data.get('teams', []):
                team_id = team.get('teamId')
                match_metadata['teams'][team_id] = {
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
                    assists=p.get('ASSISTS'),
                    baron_kills=p.get('BARON_KILLS'),
                    barracks_killed=p.get('BARRACKS_KILLED'),
                    barracks_takedowns=p.get('BARRACKS_TAKEDOWNS'),
                    champions_killed=p.get('CHAMPIONS_KILLED'),
                    double_kills=p.get('DOUBLE_KILLS'),
                    dragon_kills=p.get('DRAGON_KILLS'),
                    exp=p.get('EXP'),
                    gold_earned=p.get('GOLD_EARNED'),
                    id=p.get('ID'),
                    individual_position=p.get('INDIVIDUAL_POSITION'),
                    largest_attack_damage=p.get('LARGEST_ATTACK_DAMAGE'),
                    largest_multi_kill=p.get('LARGEST_MULTI_KILL'),
                    magic_damage_dealt_to_champions=p.get('MAGIC_DAMAGE_DEALT_TO_CHAMPIONS'),
                    minions_killed=p.get('MINIONS_KILLED'),
                    missions_championskilled=p.get('Missions_ChampionsKilled'),
                    missions_creepscore=p.get('Missions_CreepScore'),
                    missions_creepscoreby10minutes=p.get('Missions_CreepScoreBy10Minutes'),
                    missions_goldperminute=p.get('Missions_GoldPerMinute'),
                    missions_minionskilled=p.get('Missions_MinionsKilled'),
                    missions_takedownsbefore15min=p.get('Missions_TakedownsBefore15Min'),
                    name=player_name,
                    num_deaths=p.get('NUM_DEATHS'),
                    penta_kills=p.get('PENTA_KILLS'),
                    physical_damage_dealt_player=p.get('PHYSICAL_DAMAGE_DEALT_PLAYER'),
                    physical_damage_dealt_to_champions=p.get('PHYSICAL_DAMAGE_DEALT_TO_CHAMPIONS'),
                    physical_damage_taken=p.get('PHYSICAL_DAMAGE_TAKEN'),
                    player_position=p.get('PLAYER_POSITION'),
                    puuid=p.get('PUUID'),
                    quadra_kills=p.get('QUADRA_KILLS'),
                    rift_herald_kills=p.get('RIFT_HERALD_KILLS'),
                    sight_wards_bought_in_game=p.get('SIGHT_WARDS_BOUGHT_IN_GAME'),
                    skin=p.get('SKIN'),
                    team_id=p.get('TEAM'),
                    team_code="",
                    team_objective=p.get('TEAM_OBJECTIVE'),
                    team_position=p.get('TEAM_POSITION'),
                    time_ccing_others=p.get('TIME_CCING_OTHERS'),
                    total_damage_dealt=p.get('TOTAL_DAMAGE_DEALT'),
                    total_damage_dealt_to_champions=p.get('TOTAL_DAMAGE_DEALT_TO_CHAMPIONS'),
                    total_damage_taken=p.get('TOTAL_DAMAGE_TAKEN'),
                    total_heal_on_teammates=p.get('TOTAL_HEAL_ON_TEAMMATES'),
                    total_time_crowd_control_dealt=p.get('TOTAL_TIME_CROWD_CONTROL_DEALT'),
                    total_time_crowd_control_dealt_to_champions=p.get('TOTAL_TIME_CROWD_CONTROL_DEALT_TO_CHAMPIONS'),
                    total_time_spent_dead=p.get('TOTAL_TIME_SPENT_DEAD'),
                    total_units_healed=p.get('TOTAL_UNITS_HEALED'),
                    triple_kills=p.get('TRIPLE_KILLS'),
                    true_damage_dealt_player=p.get('TRUE_DAMAGE_DEALT_PLAYER'),
                    true_damage_dealt_to_champions=p.get('TRUE_DAMAGE_DEALT_TO_CHAMPIONS'),
                    true_damage_taken=p.get('TRUE_DAMAGE_TAKEN'),
                    victory_point_total=p.get('VICTORY_POINT_TOTAL'),
                    vision_score=p.get('VISION_SCORE'),
                    vision_wards_bought_in_game=p.get('VISION_WARDS_BOUGHT_IN_GAME'),
                    win=p.get('WIN')
                )
                players.append(new_player)

            # Extract teams from players
            for p in players:
                team = await ReplaysCog.determine_team(p.puuid)
                if team is None:
                    await message.channel.send(f"Warning: Could not find a team for {p.name}({p.skin})")
                    continue
                p.team_code = team
                team_exists = (any(t.get('team') == team for t in match_metadata.get('teams')) and team is not "FA")
                if not team_exists:
                    team_info = {
                        "team": team,
                        "team_code": p.team_id,
                        "win": p.win
                    }
                    match_metadata["teams"].append(team_info)

            replay_data = {
                "season": 1,
                "match_id": match_id,
                "filename": replay.filename,
                "match_metadata": match_metadata,
                "players": [player.to_dict() for player in players],
                "uploaded_at": datetime.now(timezone.utc)
            }

            return replay_data
        except Exception as e:
            logger.error(e)
            await message.channel.send("An unknown error occurred and has been logged. Please try again.")
            return None

    async def send_series_summary(self, ctx, submission):
        replays = submission["replays"]

        if not replays:
            await ctx.respond('please upload some replays')
            return

        team_wins = {}

        for replay_data in replays:

            team_players = {"100": [], "200": []}

            embed = discord.Embed(
                title="Game Summary",
                description="If this game summary is incorrect, please ping a staff member.",
                color=discord.Color.blue()
            )

            team_100_players = [p for p in replay_data['players'] if str(p["team_id"]) == "100"]
            team_200_players = [p for p in replay_data["players"] if str(p["team_id"]) == "200"]

            # Debug: Check how many players are detected for each team
            print(f"Match ID: {replay_data['match_id']}, Team 100 Players: {len(team_100_players)}, Team 200 Players: {len(team_200_players)}")

            for player in team_100_players:
                player_name = await self.determine_player_name(player['puuid'])
                team_players["100"].append(f"{player_name} (KDA: {player['champions_killed']}/{player['num_deaths']}/{player['assists']})")

            for player in team_200_players:
                player_name = await self.determine_player_name(player['puuid'])
                team_players["200"].append(f"{player_name} (KDA: {player['champions_killed']}/{player['num_deaths']}/{player['assists']})")

            # determine team names
            team_100_name = "FA"
            team_200_name = "FA"

            for player in team_100_players:
                team_100_name = await self.determine_team(player['puuid'])
                if team_100_name != "FA":
                    break
            if team_100_name == "FA":
                await ctx.respond('Error: Unable to determine team 100 name')
                return

            for player in team_200_players:
                team_200_name = await self.determine_team(player['puuid'])
                if team_200_name != "FA":
                    break
            if team_200_name == "FA":
                await ctx.respond('Error: Unable to determine team 200 name')
                return

            # add teams to dictionary if they don't exist
            if team_100_name not in team_wins:
                team_wins[team_100_name] = 0
            if team_200_name not in team_wins:
                team_wins[team_200_name] = 0

            # add a win to the team that won the game
            team_100 = next(team for team in replay_data['match_metadata']['teams'] if team['team_code'] == "100")
            if team_100['win'] == 'Win':
                winner = f"{team_100_name} (Blue Side) won this game"
                embed.thumbnail = await self.fetch_team_logo_url(team_100_name)
                team_wins[team_100_name] += 1
            else:
                winner = f"{team_200_name} (Red Side) won this game"
                embed.thumbnail = await self.fetch_team_logo_url(team_200_name)
                team_wins[team_200_name] += 1

            embed.add_field(
                name=f"{team_100_name} (Blue Side)",
                value="\n".join(team_players["100"]) or "No players",
                inline=False
            )
            embed.add_field(
                name=f"{team_200_name} (Red Side)",
                value="\n".join(team_players["200"]) or "No players",
                inline=False
            )

            embed.add_field(
                name="Game Result",
                value=winner,
                inline=False
            )

            await ctx.send(embed=embed)

        embed = discord.Embed(
            title="Series Result",
            description="If the series Result is correct, submit the /complete_submission command to finalize the series. Otherwise, ping staff for any issues.",
            color=discord.Color.blue()
        )

        # Determine game winner
        if team_wins[team_100_name] > team_wins[team_200_name]:
            submission["winner"] = team_100_name
            submission["loser"] = team_200_name
            winner = f"{team_100_name} wins the series!"
            embed.thumbnail = await self.fetch_team_logo_url(team_100_name)
        elif team_wins[team_200_name] > team_wins[team_100_name]:
            submission["winner"] = team_200_name
            submission["loser"] = team_100_name
            winner = f"{team_200_name} wins the series!"
            embed.thumbnail = await self.fetch_team_logo_url(team_200_name)
        else:
            winner = "The series is tied!"

        embed.add_field(
            name="Series Result",
            value=winner,
            inline=False
        )

        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message):
        # Check if the message is in a submission thread and contains attachments
        if message.author.bot:
            return

        submission = self.submissions.get(message.author.id)
        if submission and message.channel.id == submission["thread"]:
            for attachment in message.attachments:
                if attachment.filename.endswith('.rofl'):
                    replay_data = await self.parse_replay(message, attachment)
                    if replay_data is None:
                        continue
                    if replay_data["players"]:
                        submission["replays"].append(replay_data)
                    await message.channel.send(f"Replay {attachment.filename} uploaded successfully!")
                else:
                    await message.channel.send("Please upload a valid .rofl file.")


def setup(bot):
    bot.add_cog(ReplaysCog(bot))