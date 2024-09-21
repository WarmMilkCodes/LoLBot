import discord
from discord.ext import commands, tasks
import logging
import app.config as config
import app.dbInfo as dbInfo
import re
from cogs.utils import update_nickname

logger = logging.getLogger('lol_log')

class Audit(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.audit_roles.start()

    async def get_team_role(self, team_code: str) -> int:
        """Retrieve team role ID from the database."""
        team = dbInfo.team_collection.find_one({"team_code": team_code})
        if team:
            return team.get("team_id")
        return None

    async def update_roles(self, member, team_role_id, is_free_agent):
        """Update roles for a member based on the team status."""
        guild = member.guild
        team_role = guild.get_role(team_role_id) if team_role_id else None
        fa_role = discord.utils.get(guild.roles, name="Free Agents")
        roles_changed = False

        if is_free_agent:
            if team_role and team_role in member.roles:
                await member.remove_roles(team_role, reason="Audit role update: Free Agent in Database")
                roles_changed = True
            if fa_role not in member.roles:
                await member.add_roles(fa_role, reason="Audit role update: Free Agent in Database")
                roles_changed = True
        else:
            if team_role and team_role not in member.roles:
                await member.add_roles(team_role, reason="Audit role update: Team assignment")
                roles_changed = True
            if fa_role and fa_role in member.roles:
                await member.remove_roles(fa_role, reason="Audit role update: Team assignment")
                roles_changed = True

        return roles_changed

    
    @tasks.loop(hours=24)
    async def audit_roles(self):
        guild = self.bot.get_guild(config.lol_server)
        if guild:
            audit_channel = guild.get_channel(config.failure_log_channel)
            for member in guild.members:
                if member.bot:
                    continue

                logger.info(f"Auditing member: {member.name}")

                player_info = dbInfo.player_collection.find_one({"discord_id": member.id})
                if not player_info:
                    logger.warning(f"No player info found for {member.name} in database")
                    continue

                team_code = player_info.get("team", "Unassigned")
                is_free_agent = discord.utils.get(member.roles, name="Free Agents") is not None

                # Determine the prefix based on the player's team or role
                prefix = ""
                franchise_owner_role = discord.utils.get(member.roles, name="Franchise Owner")
                spectator_role = discord.utils.get(member.roles, name="Spectator")
                not_eligible_role = discord.utils.get(member.roles, name="Not Eligible")

                if franchise_owner_role:
                    prefix = team_code if team_code and team_code != "Unassigned" else ""
                elif is_free_agent:
                    prefix = "FA"
                elif spectator_role in member.roles:
                    prefix = "S"
                elif not_eligible_role in member.roles and not spectator_role:
                    prefix = "TBD"
                elif team_code and team_code != "Unassigned":
                    prefix = team_code

                # Call the update_nickname function with the determined prefix
                await update_nickname(member, prefix, player_info)
                
                logger.info(f"Nickname updated for {member.display_name}")

            logger.info("Audit finished. Next audit will occur in 24 hours.")

    @audit_roles.before_loop
    async def before_audit_roles(self):
        await self.bot.wait_until_ready()

    async def remove_role_from_member(self, member, role, reason):
        """Remove a role from a member with error handling"""
        try:
            await member.remove_roles(role, reason=reason)
        except Exception as e:
            logger.error(f"Error removing role {role} from {member.display_name}: {e}")

    async def update_team_in_database(self, player_id, new_team):
        """Update player's team information in database"""
        dbInfo.player_collection.update_one({"discord_id": player_id}, {'$set' : {'team': new_team}})

def setup(bot):
    bot.add_cog(Audit(bot))