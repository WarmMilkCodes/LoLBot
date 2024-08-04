from app import config as config
from app import dbInfo as dbInfo
import discord, logging, re
from discord.ext import commands
from discord.commands import Option
from discord.ext.commands import MissingAnyRole, CommandInvokeError, CommandError

logger = logging.getLogger(__name__)

GUILD_ID = config.cod_server

class Transactions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    ############################
    # Helper Functions Section #
    ############################

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

    ##########################
    # Error Handling Section #
    ##########################

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

    #############################
    # Command Functions Section #
    #############################

    @commands.slash_command(description="Sign player to team")
    @commands.has_any_role("League Ops", "Bot Guy")
    async def sign_player(self, ctx, user: Option(discord.Member), team_abbreviation: Option(str, "Enter 3-letter team abbreviation")):
        logger.info("Sign player command initiated.")
        await ctx.defer()
        try:
            if not await self.validate_command_channel(ctx):
                return

            logger.info(f"Signing {user.name} to team {team_abbreviation.upper()}.")

            player_entry = await self.get_player_info(user.id)
            if not player_entry or player_entry.get("Team") != "FA":
                logger.warning(f"{user.name} is already on a team or not found as a free agent - cannot be signed.")
                return await ctx.respond(f"{user.name} is already on a team or not found as a free agent.")
            if not player_entry.get("Rank"):
                logger.warning(f"{user.name} has not been ranked - cannot be signed.")
                return await ctx.respond(f"{user.display_name} has not been ranked - cannot be signed.")
            logger.info(f"{user.name} is a free agent and ranked. Proceeding with signing.")

            team_role_id = await self.get_team_role(team_abbreviation.upper())
            if not team_role_id:
                logger.info(f"Invalid team code passed: {team_abbreviation.upper()}")
                return await ctx.respond(f"Invalid team code: {team_abbreviation.upper()}.")

            FA = discord.utils.get(ctx.guild.roles, name="Free Agents")
            await self.add_role_to_member(user, ctx.guild.get_role(team_role_id), "Player signing")
            await self.remove_role_from_member(user, FA, "Player signing")

            gm_role_id = await self.get_gm_id(team_abbreviation.upper())
            if not gm_role_id:
                return await ctx.respond(f"No GM role found for team: {team_abbreviation.upper()}.")
            GM = ctx.guild.get_role(gm_role_id)

            message = f"{GM.mention} signs {user.mention} to roster."
            channel = self.bot.get_channel(config.posted_transactions_channel)
            await channel.send(message)

            await self.update_team_in_database(user.id, team_abbreviation.upper())
            await self.update_nickname(user, team_abbreviation.upper())
            await ctx.respond(f"{user.name} has been signed to {team_abbreviation.upper()}")

        except Exception as e:
            logger.error(f"Error signing {user.name} to {team_abbreviation.upper()}.\n{e}")
            await ctx.respond(f"Error signing {user.display_name} to {team_abbreviation.upper()}.\n{e}", ephemeral=True)

    
    @commands.slash_command(description="Designate team's General Manager")
    @commands.has_any_role("League Ops", "Bot Guy")
    async def sign_gm(self, ctx, user: Option(discord.Member), team_abbreviation: Option(str, "Enter 3-letter team abbreviation")):
        logger.info("Sign GM command initiated")
        await ctx.defer()
        try:
            if not await self.validate_command_channel(ctx):
                return
            
            logger.info(f"Signing {user.display_name} as GM of team {team_abbreviation.upper()}.")

            player_entry = await self.get_player_info(user.id)
            if player_entry:
                if player_entry.get("Team") != "FA" and player_entry.get("Team") != "Unassigned":
                    if player_entry["Team"] != team_abbreviation.upper():
                        return await ctx.respond(f"{user.display_name} is already signed to a different team as a player. Release the player from their current team first.")

            gm_role_id = await self.get_gm_id(team_abbreviation.upper())
            if not gm_role_id:
                logger.info(f"Invalid team code passed: {team_abbreviation.upper()}")
                return await ctx.respond(f"Invalid team code: {team_abbreviation.upper()}")
            
            existing_gm = await self.get_gm_id(team_abbreviation.upper())
            if existing_gm:
                return await ctx.respond(f"{team_abbreviation.upper()} already has a designated GM.")

            GM = ctx.guild.get_role(gm_role_id)
            await self.add_role_to_member(user, GM, "GM signing")

            message = f"{team_abbreviation.upper()} designates {user.display_name} as General Manager."
            channel = self.bot.get_channel(config.posted_transactions_channel)
            await channel.send(message)

            await self.update_nickname(user, team_abbreviation.upper())
            await ctx.respond(f"{user.display_name} has been designated as GM of {team_abbreviation.upper()}.")

        except Exception as e:
            logger.error(f"Error designating {user.display_name} as GM of {team_abbreviation.upper()}: {e}")
            await ctx.respond(f"There was an error designating {user.display_name} as GM of {team_abbreviation.upper()}.")

    @commands.slash_command(description="Release player to free agency")
    @commands.has_any_role("League Ops", "Bot Guy")
    async def release_player(self, ctx, user: Option(discord.Member), team_abbreviation: Option(str, "Enter 3-letter team abbreviation")):
        """Release a player to free agency."""
        await ctx.defer()
        try:
            if not await self.validate_command_channel(ctx):
                return

            logger.info(f"Releasing {user.name} from team {team_abbreviation.upper()}.")

            player_entry = await self.get_player_info(user.id)
            if player_entry is None:
                logger.error(f"Player entry for {user.name} not found in database")
                return await ctx.respond(f"Player entry for {user.name} not found in database.")

            if player_entry["Team"] == "FA":
                return await ctx.respond(f"{user.name} is already a free agent.")

            team_role_id = await self.get_team_role(team_abbreviation.upper())
            if not team_role_id:
                return await ctx.respond(f"Invalid team code: {team_abbreviation.upper()}.")

            if not user.roles.__contains__(ctx.guild.get_role(team_role_id)):
                return await ctx.respond(f"{user.name} is not signed to {team_abbreviation.upper()}.")

            FA = discord.utils.get(ctx.guild.roles, name="Free Agents")
            await self.add_role_to_member(user, FA, "Player release")
            await self.remove_role_from_member(user, ctx.guild.get_role(team_role_id), "Player release")

            gm_role_id = await self.get_gm_id(team_abbreviation.upper())
            if not gm_role_id:
                return await ctx.respond(f"No GM role found for team: {team_abbreviation.upper()}.")
            GM = ctx.guild.get_role(gm_role_id)

            message = f"{GM.mention} releases {user.mention} to free agency."
            channel = self.bot.get_channel(config.posted_transactions_channel)
            await channel.send(message)

            await self.update_team_in_database(user.id, "FA")
            await self.update_nickname(user, "FA")
            await ctx.respond(f"{user.name} has been released from {team_abbreviation.upper()}.")

        except Exception as e:
            logger.error(f"Error releasing {user.name}.\n{e}")
            await ctx.respond(f"Error releasing {user.name}.\n{e}", ephemeral=True)

    @commands.slash_command(description="Release GM from team")
    @commands.has_any_role("League Ops", "Bot Guy")
    async def release_gm(self, ctx, user: Option(discord.Member), team_abbreviation: Option(str, "Enter 3-letter team abbreviation")):
        """Relieve GM of their duties"""
        await ctx.defer()
        try:
            if not await self.validate_command_channel(ctx):
                return
            
            logger.info(f"Relieving {user.display_name} of GM duties from {team_abbreviation.upper()}")

            gm_role_id = await self.get_gm_id(team_abbreviation.upper())
            if not gm_role_id:
                logger.error(f"GM role not found for team {team_abbreviation.upper()}")
                return await ctx.respond(f"GM role not found for team {team_abbreviation.upper()}.")

            GM = ctx.guild.get_role(gm_role_id)
            if GM not in user.roles:
                return await ctx.respond(f"{user.name} is not the GM of {team_abbreviation.upper()}.")

            await self.remove_role_from_member(user, GM, "GM release")

            message = f"{user.mention} has been relieved of GM duties for {team_abbreviation.upper()}."
            channel = self.bot.get_channel(config.posted_transactions_channel)
            await channel.send(message)

            await self.update_nickname(user, "FA" if await self.get_player_info(user.id).get("Team") == "FA" else "")
            await ctx.respond(f"{user.name} has been relieved of GM duties for {team_abbreviation.upper()}")

        except Exception as e:
            logger.error(f"Error releasing {user.name} from GM duties for {team_abbreviation.upper()}.\n{e}")
            await ctx.respond(f"Error releasing {user.display_name} from GM duties for {team_abbreviation.upper()}.\n{e}", ephemeral=True)


def setup(bot):
    bot.add_cog(Transactions(bot))