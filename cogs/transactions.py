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
        
def setup(bot):
    bot.add_cog(Transactions(bot))