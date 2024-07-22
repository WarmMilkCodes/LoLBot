import app.config as config
import app.dbInfo as dbInfo
import discord, logging, secrets
from discord.ext import commands
from discord.commands import Option
from discord.ext.commands import CommandError, MissingAnyRole
from bson import ObjectId
from datetime import datetime, timezone
import pytz

logger = logging.getLogger(__name__)

class Transactions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    ### Helper Functions ###

    # Function to retrieve GM ID from database
    async def get_gm_role(self, team_code: str) -> int:
        team = dbInfo.team_collection.find_one({"team_code":team_code})
        if team:
            gm_role_id = team['gm_id']
            return gm_role_id
        return None

    async def get_team_role(self, team_code: str) -> int:
        team = dbInfo.team_collection.find_one({"team_code":team_code})
        if team:
            team_role_id = team['team_id']
            return team_role_id
        return None
    
    async def get_player_info(self, player_id):
        return dbInfo.player_collection.find_one({"discord_id":player_id})
    
    async def update_team_in_database(self, player_id, new_team):
        dbInfo.player_collection.update_one({"disord_id":player_id}, {"$set": {"team":new_team}})

    
    ### Error Handling ###

    @commands.Cog.listener()
    async def on_error(self, error, ctx):
        if isinstance(error, MissingAnyRole):
            await ctx.send("You do not have the required roles to use this command.")
        else:
            await ctx.send(f"An unknown error occured: {error}", ephemeral=True)

    
    ### Commands ###

    @commands.slash_command(description="Sign player to team")
    @commands.has_any_role("United Rogue Owner", "League Ops", "Bot Guy")
    async def sign_player(self, ctx, user: Option(discord.Member), team_code: Option(str, "Enter 3-letter team abbreviation")):
        logger.info("Sign player command initiated.")
        try:
            guild=ctx.guild

            # Ensure command invoked in correct channel
            transaction_bot_channel_id = config.transaction_bot_channel
            posted_transaction_channel = config.posted_transactions_channel

            if ctx.channel.id != transaction_bot_channel_id:
                logger.info("Sign player command invoked in wrong channel.")
                return await ctx.respond(f"This comand can only be used in {transaction_bot_channel_id.mention}", ephemeral=True)
            
            # Determine player's current team status (signed or free agent)
            logger.info(f"Checking database to see if {user.name} is already on a team.")
            player_entry = dbInfo.player_collection.find_one({
                "discord_id":user.id, 
                "$or": [
                    {"team":"FA"},
                    {"team": None}
                ]
            })

            if not player_entry or player_entry.get("team") != "FA" or player_entry.get("team") != None:
                logger.warning(f"{user.name} is already on a team or was not found in the database.")
            logger.info(f"{user.name} is a free agent, proceeding with signing.")

            team_role_id = await self.get_team_role(team_code.upper())

            logger.info(f"Retrieved team role: {team_code.upper()}")

            if not team_role_id:
                logger.info(f"Invalid team code passed: {team_code.upper()}.")
                return await ctx.respond(f"Invalid team code: {team_code.upper()}")
            
            free_agent_role = discord.utils.get(ctx.guild.roles, name="Free Agents")
            logger.info(f"Removing free agent role from {user.name}")
            await user.remove_roles(free_agent_role)
            logger.info(f"Assigning {team_code.upper()} role to {user.name}")
            await user.add_roles(guild.get_role(team_role_id))

            # Update user's display name with team prefix
            new_nickname = f"{team_code.upper()} | {user.display_name}"
            await user.edit(nick=new_nickname)
            logger.info(f"Updated nickname for {user.name} to {new_nickname}")

            # Get GMs role
            gm_role_id = await self.get_gm_role(team_code.upper())
            if not gm_role_id:
                return await ctx.respond(f"No GM role found for team: {team_code.upper()}.")
            general_manager_role = guild.get_role(gm_role_id)
            logger.info(f"Retrieved {team_code.upper()}'s GM role.")

            # Send message to transaction channel
            message = f"{general_manager_role.mention} signs {user.mention} to roster."
            channel = self.bot.get_channel(config.posted_transactions_channel)
            logger.info("Sending transaction notification to transactions channel.")
            await channel.send(message)

            # Add player's team to their document in DB
            dbInfo.player_collection.find_one_and_update(
                {"discord_id": user.id},
                {"$set": {"team": team_code.upper()}}
            )
            logger.info(f"Succesfully updated {user.name}'s team in player's DB document.")

            await ctx.respond(f"{user.name} has been signed to {team_code.upper()}")
        
        except Exception as e:
            await ctx.respond(f"There was an error while signing {user.name} to {team_code.upper()}.")
            logger.error(f"Error signing {user.name} to {team_code.upper()}: {e}")

def setup(bot):
    bot.add_cog(Transactions(bot))