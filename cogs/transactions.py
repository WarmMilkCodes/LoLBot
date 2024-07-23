import app.config as config
import app.dbInfo as dbInfo
import discord, logging
from discord.ext import commands
from discord.commands import Option
from discord.ext.commands import MissingAnyRole


logger = logging.getLogger(__name__)

class Transactions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    ### Helper Functions ###

    async def get_gm_role(self, team_code: str) -> int:
        team = dbInfo.team_collection.find_one({"team_code": team_code})
        if team:
            gm_role_id = team['gm_id']
            return gm_role_id
        return None

    async def get_team_role(self, team_code: str) -> int:
        team = dbInfo.team_collection.find_one({"team_code": team_code})
        if team:
            team_role_id = team['team_id']
            return team_role_id
        return None
    
    async def get_player_info(self, player_id):
        return dbInfo.player_collection.find_one({"discord_id": player_id})
    
    async def update_team_in_database(self, player_id, new_team):
        dbInfo.player_collection.update_one({"discord_id": player_id}, {"$set": {"team": new_team}})

    ### Error Handling ###

    @commands.Cog.listener()
    async def on_error(self, error, ctx):
        if isinstance(error, MissingAnyRole):
            await ctx.send("You do not have the required roles to use this command.")
        else:
            await ctx.send(f"An unknown error occurred: {error}", ephemeral=True)

    ### Commands ###

    @commands.slash_command(description="Sign player to team")
    @commands.has_any_role("United Rogue Owner", "League Ops", "Bot Guy")
    async def sign_player(self, ctx, player: Option(discord.Member), team_code: Option(str, "Enter 3-letter team abbreviation")):
        logger.info("Sign player command initiated.")
        await ctx.defer()  # Defer the response to extend the interaction time
        try:
            guild = ctx.guild

            # Ensure command invoked in correct channel
            transaction_bot_channel_id = config.transaction_bot_channel
            posted_transaction_channel = config.posted_transactions_channel

            if ctx.channel.id != transaction_bot_channel_id:
                logger.info("Sign player command invoked in wrong channel.")
                return await ctx.respond(f"This command can only be used in {transaction_bot_channel_id.mention}", ephemeral=True)
            
            # Determine player's current team status (signed or free agent)
            logger.info(f"Checking database to see if {player.name} ({user.id}) is already on a team.")
            player_entry = dbInfo.player_collection.find_one({
                "discord_id": player.id, 
                "$or": [
                    {"team": "FA"},
                    {"team": None}
                ]
            })

            if player_entry:
                logger.info(f"Found player entry: {player_entry}")
            else:
                logger.warning(f"No player entry found for {user.name} ({user.id})")

            if player_entry and player_entry.get("team") not in ["FA", None]:
                logger.warning(f"{player.name} is already on a team or was not found in the database.")
                return await ctx.respond(f"{player.name} is already on a team or was not found in the database.", ephemeral=True)

            logger.info(f"{player.name} is a free agent, proceeding with signing.")

            team_role_id = await self.get_team_role(team_code.upper())

            logger.info(f"Retrieved team role: {team_code.upper()}")

            if not team_role_id:
                logger.info(f"Invalid team code passed: {team_code.upper()}.")
                return await ctx.respond(f"Invalid team code: {team_code.upper()}", ephemeral=True)
            
            free_agent_role = discord.utils.get(ctx.guild.roles, name="Free Agents")
            if free_agent_role:
                logger.info(f"Removing free agent role from {user.name}")
                await player.remove_roles(free_agent_role)
            
            logger.info(f"Assigning {team_code.upper()} role to {user.name}")
            await player.add_roles(guild.get_role(team_role_id))

            # Update user's nickname with team prefix
            new_nickname = f"{team_code.upper()} | {player.display_name}"
            try:
                await player.edit(nick=new_nickname)
                logger.info(f"Updated nickname for {player.name} to {new_nickname}")
            except discord.Forbidden:
                logger.error(f"Failed to update nickname for {user.name} due to missing permissions.")
                return await ctx.respond(f"Failed to update nickname for {user.name} due to missing permissions.", ephemeral=True)

            # Get GM's role
            gm_role_id = await self.get_gm_role(team_code.upper())
            if not gm_role_id:
                return await ctx.respond(f"No GM role found for team: {team_code.upper()}.", ephemeral=True)
            general_manager_role = guild.get_role(gm_role_id)
            logger.info(f"Retrieved {team_code.upper()}'s GM role.")

            # Send message to transaction channel
            message = f"{general_manager_role.mention} signs {user.mention} to roster."
            channel = self.bot.get_channel(config.posted_transactions_channel)
            logger.info("Sending transaction notification to transactions channel.")
            await channel.send(message)

            # Add player's team to their document in DB
            dbInfo.player_collection.find_one_and_update(
                {"discord_id": player.id},
                {"$set": {"team": team_code.upper()}}
            )
            logger.info(f"Successfully updated {player.name}'s team in player's DB document.")

            await ctx.respond(f"{player.name} has been signed to {team_code.upper()}", ephemeral=True)
        
        except Exception as e:
            logger.error(f"Error signing {player.name} to {team_code.upper()}: {e}")
            await ctx.respond(f"There was an error while signing {user.name} to {team_code.upper()}.", ephemeral=True)


    @commands.slash_command(description="Release player to free agency")
    @commands.has_any_role("United Rogue Owner", "League Ops", "Bot Guy")
    async def release_player(self, ctx, player: Option(discord.member), team_code: Option(str, "Enter 3-letter team abbreviation")):
        guild=ctx.guild
        await ctx.defer()
        try:
            # Ensure command invoked in correct channel
            transaction_bot_channel_id = config.transaction_bot_channel
            posted_transaction_channel = config.posted_transactions_channel

            if ctx.channel.id != transaction_bot_channel_id:
                logger.info("Release player command invoked in wrong channel.")
                return await ctx.respond(f"This command can only be used in {transaction_bot_channel_id.mention}", ephemeral=True)
            
            # Check if player is already a free agent
            player_entry = dbInfo.player_collection.find_one({"discord_id": player.id, "team": "FA"})

            if player_entry["team"] == "FA":
                return await ctx.respond(f"{player.display_name} is already a free agent.")
            
            # Get player's team role
            team_role_id = await self.get_team_role(team_code.upper())
            if not team_role_id:
                return await ctx.respond(f"Invalid team code: {team_code.upper()}.")
            
            # Check if player is on the specified team
            if not player.roles.__contains__(guild.get_role(team_role_id)):
                return await ctx.respond(f"{player.display_name} is not signed to {team_code.upper()}.")
            
            free_agent_role = discord.utils.get(ctx.guild.roles, name="Free Agents")
            await player.add_roles(free_agent_role)
            await player.remove_roles(guild.get_role(team_role_id))

            # Get GM's role
            general_manager_role = await self.get_gm_role(team_code.upper())
            if not general_manager_role:
                return await ctx.respond(f"No GM role found for team {team_code.upper()}.")
            GM = guild.get_role(general_manager_role)

            # Send message to transactions channel
            message = f"{GM.mention} releases {player.mention} to free agency."
            channel = self.bot.get_channel(config.posted_transactions_channel)
            await channel.send(message)


            logger.info(f"{player.name} has been released from {team_code.upper()}.")

        except Exception as e:
            logger.error(f"There was an error releasing {player.name} from {team_code.upper()}: {e}")

def setup(bot):
    bot.add_cog(Transactions(bot))
