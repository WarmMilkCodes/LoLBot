import app.config as config
import app.dbInfo as dbInfo
import logging
import discord, re
from discord.ext import commands
from discord.commands import Option
from discord.ext.commands import MissingAnyRole, CommandInvokeError, CommandError

logger = logging.getLogger('lol_log')

GUILD_ID = config.lol_server

class Transactions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Helper functions
        
    async def update_nickname(self, member, prefix):
        """Update member's nickname with given prefix"""
        try:
            # Remove any existing prefix
            new_nickname = re.sub(r"^(FA \| |S \| |[A-Z]{2,3} \| )", "", member.display_name)
            # Add new prefix
            if prefix:
                new_nickname = f"{prefix} | {new_nickname}"
            await member.edit(nick=new_nickname)
            logger.info(f"Updated nickname for {member.name} to {new_nickname}")
        except Exception as e:
            logger.error(f"Error updating nickname for {member.name}: {e}")


    async def get_gm_id(self, team_code: str) -> int:
        """Retrieve GM ID from the database."""
        team = dbInfo.team_collection.find_one({"team_code": team_code})
        if team:
            return team.get("gm_id")
        return None
    
    async def get_team_role(self, team_code: str) -> int:
        """Retrieve team role ID from the database."""
        team = dbInfo.team_collection.find_one({"team_code": team_code})
        if team:
            return team.get("team_id")
        return None

    async def validate_command_channel(self, ctx):
        """Check if the command is invoked in the correct channel."""
        if ctx.channel.id != config.transaction_bot_channel:
            transaction_bot_channel = ctx.guild.get_channel(config.transaction_bot_channel)
            await ctx.respond(f"This command can only be used in {transaction_bot_channel.mention}", ephemeral=True)
            return False
        return True
    
    async def get_player_info(self, player_id):
        """Fetch player information from the database."""
        return dbInfo.player_collection.find_one({"discord_id": player_id})

    async def update_team_in_database(self, player_id, new_team):
        """Update the player's team information in the database."""
        dbInfo.player_collection.update_one({"discord_id": player_id}, {'$set': {'team': new_team}})

    async def add_role_to_member(self, member, role, reason):
        """Add a role to a member with error handling."""
        try:
            await member.add_roles(role, reason=reason)
        except Exception as e:
            logger.error(f"Error adding role {role} to {member.name}: {e}")

    async def remove_role_from_member(self, member, role, reason):
        """Remove a role from a member with error handling."""
        try:
            await member.remove_roles(role, reason=reason)
        except Exception as e:
            logger.error(f"Error removing role {role} from {member.name}: {e}")


    # Error Handling
            
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """Handle errors globally within the cog."""
        if isinstance(error, MissingAnyRole):
            await ctx.send("You do not have the required roles to use this command", ephemeral=True)
        elif isinstance(error, CommandInvokeError):
            await ctx.respond(f"An error occured while invoking the command: {error.original}", ephemeral=True)
        elif isinstance(error, CommandError):
            await ctx.respond(f"An error occured: {error}", ephemeral=True)
        else:
            await ctx.send(f"An unknown error occured: {error}", ephemeral=True)
        logger.error(f"Error in command {ctx.command}: {error}")


    # Commands
    @commands.slash_command(guild_ids=[config.lol_server], description="Designate team Governor")        
    @commands.has_any_role("League Ops", "Bot Guy")
    async def designate_governor(self, ctx, user: Option(discord.Member), team_code: Option(str, "Enter 3-digit team abbreviation (ex. SDA for San Diego Armada")):
        await ctx.defer()
        try:
            if not await self.validate_command_channel(ctx):
                return
            
            player_entry = await self.get_player_info(user.id)
            if not player_entry or player_entry.get("team") not in [None, team_code.upper(), 'FA']:
                return await ctx.respond(f"{user.mention} cannot be designated as team governor")
            
            team_role_id = await self.get_team_role(team_code.upper())
            if not team_role_id:
                return await ctx.respond(f"Invalid team code used in command: {team_code.upper()}")
            
            FA = discord.utils.get(ctx.guild.roles, name="Free Agents")
            governor_role = discord.utils.get(ctx.guild.roles, name="Franchise Governor")
            await self.add_role_to_member(user, ctx.guild.get_role(team_role_id), "Designated as Governor")
            await self.add_role_to_member(user, ctx.guild.get_role(governor_role), "Designated as Governor")
            await self.remove_role_from_member(user, ctx.guild.get_role(FA), "Designated as Governor")

            message = f"{team_code.upper()} designated {user.mention} as Governor"
            channel = self.bot.get_channel(config.posted_transactions_channel)
            await channel.send(message)

            await self.update_team_in_database(user.id, team_code.upper())
            await self.update_nickname(user, team_code.upper())
            await ctx.respond(f"{team_code.upper()} designates {user.mention} as Governor")

        except Exception as e:
            await ctx.respond(f"There was an error designating {user.mention} as {team_code.upper()}'s Governor:\n{e}")

    @commands.slash_command(guild_ids=[config.lol_server], description="Designate GM to team")
    @commands.has_any_role("League Ops", "Bot Guy")
    async def designate_gm(self, ctx, user: Option(discord.Member), team_code: Option(str, "Enter 3-digit team abbreviation (ex. SDA for San Diego Armada)")):
        await ctx.defer()
        try:
            if not await self.validate_command_channel(ctx):
                return
            
            player_entry = await self.get_player_info(user.id)
            if not player_entry or player_entry.get("team") not in ['FA', team_code.upper()]:
                return await ctx.respond(f"{user.mention} is not a free agent or is signed to a different team and cannot be designated as GM for {team_code.upper()}.")
        
            
            team_role_id = await self.get_team_role(team_code.upper())
            if not team_role_id:
                return await ctx.respond(f"Invalid team code used in command: {team_code.upper()}")
            
            gm_role_id = await self.get_gm_id(team_code.upper())
            if not gm_role_id:
                return await ctx.respond(f"Invalid team code used in command: {team_code.upper()}")

            FA = discord.utils.get(ctx.guild.roles, name="Free Agents")
            await self.add_role_to_member(user, ctx.guild.get_role(team_role_id), "Designated as GM")
            await self.add_role_to_member(user, ctx.guild.get_role(gm_role_id), "Designated as GM")
            await self.remove_role_from_member(user, FA, "Designated as GM")


            message = f"{team_code.upper()} designates {user.mention} as GM"
            channel = self.bot.get_channel(config.posted_transactions_channel)
            await channel.send(message)

            await self.update_team_in_database(user.id, team_code.upper())
            await self.update_nickname(user, team_code.upper())
            await ctx.respond(f"{team_code.upper()} designates {user.mention} as GM.")

        except Exception as e:
            logger.error(f"Error designating {user.name} as GM:\n{e}")
            await ctx.respond(f"There was an error designating {user.mention} as GM:\n{e}")
        # Command can only be invoked in transaction-bot channel
        # Ensure GM is not signed to a DIFFERENT team
        # Should add GM designation in DB
        # Does not add to playing roster automatically - default non-playing, must sign with general command to sign to active roster

    @commands.slash_command(guild_ids=[config.lol_server], description="Relieve GM of duties")
    @commands.has_any_role("League Ops", "Bot Guy")
    async def relieve_gm(self, ctx, user: Option(discord.Member), team_code:Option(str, "Enter 3-digit team abbreviation (ex. SDA for San Diego Armada")):
        await ctx.defer()
        try:
            if not await self.validate_command_channel(ctx):
                return
            
            gm_role_id = await self.get_gm_id(team_code.upper())
            if not gm_role_id:
                return await ctx.respond(f"GM role not found for team: {team_code.upper()}")
            
            GM = ctx.guild.get_role(gm_role_id)
            if GM not in user.roles:
                return await ctx.respond(f"{user.mention} is not the GM of {team_code.upper()}")
            
            await self.remove_role_from_member(user, GM, "Relieved of GM")

            message = f"{team_code.upper()} relieves {user.mention} of GM duties"
            channel = self.bot.get_channel(config.posted_transactions_channel)
            await channel.send(message)

            await ctx.respond(f"{team_code.upper()} relieves {user.mention} of GM duties.")

            team_status = await self.get_player_info(user.id)
            if team_status.get("team") != team_code.upper():
                await self.update_nickname(user, 'FA')

        except Exception as e:
            await ctx.respond(f"Error relieving {user.mention} from GM duties:\n{e}")

    @commands.slash_command(guild_ids=[config.lol_server], description="Sign player to active roster")
    @commands.has_any_role("League Ops", "Bot Guy")
    async def sign_player(self, ctx, user: Option(discord.Member), team_code:Option(str, "Enter 3-digit team abbreviation (ex. SDA for San Diego Armada")):
        await ctx.defer()
        try:
            if not await self.validate_command_channel(ctx):
                return
            
            player_entry = await self.get_player_info(user.id)
            if not player_entry or player_entry.get("team") != "FA":
                return await ctx.respond(f"{user.mention} is already on a team and cannot be signed.")
            
            if not player_entry.get("rank_info"):
                return await ctx.respond(f"{user.mention} does not have rank game data and cannot be signed.")
            
            team_role_id = await self.get_team_role(team_code.upper())
            if not team_role_id:
                return await ctx.respond(f"Invalid team code passed: {team_code.upper()}")
            
            FA = discord.utils.get(ctx.guild.roles, name="Free Agents")
            await self.add_role_to_member(user, ctx.guild.get_role(team_role_id), f"Player signed to {team_code.upper()}")
            await self.remove_role_from_member(user, FA, f"Player signed to {team_code.upper()}")

            gm_role_id = await self.get_gm_id(team_code.upper())
            if not gm_role_id:
                return await ctx.respond(f"No GM role found for team: {team_code.upper()}")
            
            GM = ctx.guild.get_role(gm_role_id)

            message = f"{GM.mention} signs {user.mention} to active roster"
            channel = self.bot.get_channel(config.posted_transactions_channel)
            await channel.send(message)

            await self.update_team_in_database(user.id, team_code.upper())
            await self.update_nickname(user, team_code.upper())
            await ctx.respond(f"{user.mention} has been signed to {team_code.upper()}")

        except Exception as e:
            await ctx.respond(f"Error signing {user.mention} to {team_code.upper():\n{e}}")
            

    @commands.slash_command(guild_ids=[config.lol_server], description="Release player to free agency")
    @commands.has_any_role("League Ops", "Bot Guy")
    async def release_player(self, ctx, user:Option(discord.Member), team_code:Option(str, "Enter 3-digit team abbreviation (ex. SDA for San Diego Armada")):
        await ctx.defer()
        
        try:
            if not await self.validate_command_channel(ctx):
                return
            
            player_entry = await self.get_player_info(user.id)
            if player_entry is None:
                return await ctx.respond(f"Unable to find player: {user.name} in database.", ephemeral=True)
            
            if player_entry['team'] == 'FA':
                return await ctx.respond(f"{user.name} is already a free agent.")
            
            team_role_id = await self.get_team_role(team_code.upper())
            if not team_role_id:
                return await ctx.respond(f"Invalid team code used in command: {team_code.upper()}")
            
            if not user.roles.__contains__(ctx.guild.get_role(team_role_id)):
                return await ctx.respond(f"{user.name} is not signed to {team_code.upper()}'s active roster.")
            
            FA = discord.utils.get(ctx.guild.roles, name="Free Agents")
            await self.remove_role_from_member(user, ctx.guild.get_role(team_role_id), "Player released to free agency")
            await self.add_role_to_member(user, FA, "Player released to free agency")

            gm_role_id = await self.get_gm_id(team_code.upper())
            if not gm_role_id:
                return await ctx.respond(f"No GM role found for team: {team_code.upper()}")
            GM = ctx.guild.get_role(gm_role_id)

            message = f"{GM.mention} releases {user.mention} to free agency"
            channel = self.bot.get_channel(config.posted_transactions_channel)
            await channel.send(message)

            await self.update_team_in_database(user.id, 'FA')
            await self.update_nickname(user, 'FA')
            await ctx.respond(f"{user.mention} has been released from {team_code.upper()} to free agency")

        except Exception as e:
            await ctx.respond(f"Error releasing {user.name}:\n{e}")
            

    @commands.slash_command(guild_ids=[config.lol_server], description="Designate team captain")
    @commands.has_any_role("League Ops", "Bot Guy")
    async def designate_captain(self, ctx, user:Option(discord.Member), team_code:Option(str, "Enter 3-digit team abbreviation (ex. SDA for San Diego Armada")):
        await ctx.defer()
        
        try:
            if not await self.validate_command_channel(ctx):
                return
            
            player_entry = await self.get_player_info(user.id)
            if not player_entry or player_entry.get("team") not in ['FA', team_code.upper()]:
                return await ctx.respond(f"{user.mention} is not a free agent or is signed to a different team and cannot be signed to {team_code.upper()}")
            
            team_role_id = await self.get_team_role(team_code.upper())
            if not team_role_id:
                return await ctx.respond(f"Invalid team code used in command: {team_code.upper()}")
            
            gm_role_id = await self.get_gm_id(team_code.upper())
            if not gm_role_id:
                return await ctx.respond(f"Invalid team code used in command: {team_code.upper()}")
            
            GM = ctx.guild.get_role(gm_role_id)
            FA = discord.utils.get(ctx.guild.roles, name="Free Agents")
            captain_role = discord.utils.get(ctx.guild.roles, name="Captains")
            await self.remove_role_from_member(user, FA, "Designated to captain")
            await self.add_role_to_member(user, ctx.guild.get_role(team_role_id), "Designated as captain")
            await self.add_role_to_member(user, ctx.guild.get_role(captain_role), "Designated as captain")

            message = f"{GM.mention} designates {user.mention} as team captain"
            channel = self.bot.get_channel(config.posted_transactions_channel)
            await channel.send(message)

            await self.update_team_in_database(user.id, team_code.upper())
            await self.update_nickname(user, team_code.upper())
            await ctx.respond(f"{user.mention} has been designated team captain of {team_code.upper()}")

        except Exception as e:
            await ctx.respond(f"Error designating {user.mention} as captain:\n{e}")


    @commands.slash_command(guild_ids=[config.lol_server], description="Relieve team captain of duties")
    @commands.has_any_role("League Ops", "Bot Guy")
    async def relieve_captain(self, ctx, user:Option(discord.Member), team_code:Option(str, "Enter 3-digit team abbreviation (ex. SDA for San Diego Armada")):
        await ctx.defer()
        
        try:
            if not await self.validate_command_channel(ctx):
                return
            
            team_captain_role = discord.utils.get(ctx.guild.roles, name="Captains")
            if team_captain_role not in user.roles:
                return await ctx.respond(f"{user.mention} has not been designated as a team captain.")
            
            player_entry = await self.get_player_info(user.id)
            if not player_entry or player_entry.get("team") != team_code.upper():
                return await ctx.respond(f"{user.mention} is not a member of {team_code.upper()}")
            
            team_role_id = await self.get_team_role(team_code.upper())
            if not team_role_id:
                return await ctx.respond(f"Invalid team code used in command: {team_code.upper()}")
            
            gm_role_id = await self.get_gm_id(team_code.upper())
            if not gm_role_id:
                return await ctx.respond(f"Invalid team code used in command: {team_code.upper()}")
            
            await self.remove_role_from_member(user, team_captain_role, "Relieved of Captaincy")

            GM = ctx.guild.get_role(gm_role_id)
            message = f"{GM.mention} relieves {user.mention} of captain duties"
            channel = self.bot.get_channel(config.posted_transactions_channel)
            await channel.send(message)

            await ctx.respond(f"{GM.mention} relieves {user.mention} of captain duties")

            if player_entry.get('team') != team_code.upper():
                await self.update_nickname(user, 'FA')
    
        except Exception as e:
            await ctx.respond(f"There was an error relieving {user.mention} of captain duties:\n{e}")
        
def setup(bot):
    bot.add_cog(Transactions(bot))