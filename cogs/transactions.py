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
        team = dbInfo.teams_collection.find_one({"team_code": team_code})
        if team:
            return team.get("gm_id")
        return None
    
    async def get_gov_id(self, team_code: str) -> int:
        """Retrieve governor ID from database"""
        team = dbInfo.team_collection.find_one({"team_code": team_code})
        if team:
            return team.get['gov_id']
        return None
    
    async def get_team_role(self, team_code: str) -> int:
        """Retrieve team role ID from the database."""
        team = dbInfo.teams_collection.find_one({"team_code": team_code})
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
        return dbInfo.player_collection.find_one({"Discord ID": str(player_id)})

    async def update_team_in_database(self, player_id, new_team):
        """Update the player's team information in the database."""
        dbInfo.player_collection.update_one({"Discord ID": str(player_id)}, {'$set': {'Team': new_team}})

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
        ctx.defer()
        # Command can only be invoked in transaction-bot channel
        # Ensure GM is not signed to a DIFFERENT team
        # Should add GM designation in DB
        # Does not add to playing roster automatically - default non-playing, must sign with general command to sign to active roster
        await ctx.respond(f"If this command was finished it would have signed {user.display_name} to {team_code.upper()} - however it is not. So it did not. Check back later.")

    @commands.slash_command(guild_ids=[config.lol_server], description="Relieve GM of duties")
    @commands.has_any_role("League Ops", "Bot Guy")
    async def relieve_gm(self, ctx, user: Option(discord.Member), team_code:Option(str, "Enter 3-digit team abbreviation (ex. SDA for San Diego Armada")):
        ctx.defer()
        await ctx.respond(f"If the command to sign {user.display_name} to {team_code.upper()} didn't work - I don't know why you thought this one would.")

    @commands.slash_command(guild_ids=[config.lol_server], description="Sign player to active roster")
    @commands.has_any_role("League Ops", "Bot Guy")
    async def sign_player(self, ctx, user: Option(discord.Member), team_code:Option(str, "Enter 3-digit team abbreviation (ex. SDA for San Diego Armada")):
        ctx.defer()
        await ctx.respond("Shockingly no. This command isn't ready yet either.")

    @commands.slash_command(guild_ids=[config.lol_server], description="Release player to free agency")
    @commands.has_any_role("League Ops", "Bot Guy")
    async def release_player(self, ctx, user:Option(discord.Member), team_code:Option(str, "Enter 3-digit team abbreviation (ex. SDA for San Diego Armada")):
        ctx.defer()
        await ctx.respond("I'm trying, ok? It's a lot of commands.")

    @commands.slash_command(guild_ids=[config.lol_server], description="Designate team captain")
    @commands.has_any_role("League Ops", "Bot Guy")
    async def designate_captain(self, ctx, user:Option(discord.Member), team_code:Option(str, "Enter 3-digit team abbreviation (ex. SDA for San Diego Armada")):
        ctx.defer()
        await ctx.respond("I don't even know how to go about handling this command - but Gen says there will be captains!")

    @commands.slash_command(guild_ids=[config.lol_server], description="Relieve team captain of duties")
    @commands.has_any_role("League Ops", "Bot Guy")
    async def relieve_captain(self, ctx, user:Option(discord.Member), team_code:Option(str, "Enter 3-digit team abbreviation (ex. SDA for San Diego Armada")):
        ctx.defer()
        await ctx.respond("This one's easy - but... also, not done.")
    
        
def setup(bot):
    bot.add_cog(Transactions(bot))