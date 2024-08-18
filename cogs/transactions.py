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

            message = f"{user.mention} has been relieved of GM duties for {team_code.upper()}"
            channel = self.bot.get_channel(config.posted_transactions_channel)
            await channel.send(message)

            await ctx.respond(f"{user.mention} has been relieved of GM duties for {team_code.upper()}")

        except Exception as e:
            await ctx.respond(f"Error relieving {user.mention} from GM duties:\n{e}")

    @commands.slash_command(guild_ids=[config.lol_server], description="Sign player to active roster")
    @commands.has_any_role("League Ops", "Bot Guy")
    async def sign_player(self, ctx, user: Option(discord.Member), team_code:Option(str, "Enter 3-digit team abbreviation (ex. SDA for San Diego Armada")):
        await ctx.defer()
        await ctx.respond("Shockingly no. This command isn't ready yet either.")

    @commands.slash_command(guild_ids=[config.lol_server], description="Release player to free agency")
    @commands.has_any_role("League Ops", "Bot Guy")
    async def release_player(self, ctx, user:Option(discord.Member), team_code:Option(str, "Enter 3-digit team abbreviation (ex. SDA for San Diego Armada")):
        await ctx.defer()
        await ctx.respond("I'm trying, ok? It's a lot of commands.")

    @commands.slash_command(guild_ids=[config.lol_server], description="Designate team captain")
    @commands.has_any_role("League Ops", "Bot Guy")
    async def designate_captain(self, ctx, user:Option(discord.Member), team_code:Option(str, "Enter 3-digit team abbreviation (ex. SDA for San Diego Armada")):
        await ctx.defer()
        await ctx.respond("I don't even know how to go about handling this command - but Gen says there will be captains!")

    @commands.slash_command(guild_ids=[config.lol_server], description="Relieve team captain of duties")
    @commands.has_any_role("League Ops", "Bot Guy")
    async def relieve_captain(self, ctx, user:Option(discord.Member), team_code:Option(str, "Enter 3-digit team abbreviation (ex. SDA for San Diego Armada")):
        await ctx.defer()
        await ctx.respond("This one's easy - but... also, not done.")
    
        
def setup(bot):
    bot.add_cog(Transactions(bot))