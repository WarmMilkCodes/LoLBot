import discord
from discord.ext import commands, tasks
import logging
import app.config as config
import app.dbInfo as dbInfo
import re
from app.helper import update_nickname
from cogs.salaries import SalaryCog

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
                current_salary = player_info.get("salary", 0)
                manually_adjusted_salary = player_info.get("manual_salary", None)
                rank_info = player_info.get('rank_info', [])
                historical_rank_info = player_info.get('historical_rank_info', {})

                # Calculate the player's highest rank and salary
                salary_cog = SalaryCog(self.bot)
                highest_rank, highest_division = salary_cog.get_highest_rank(rank_info, historical_rank_info)

                # Store peak rank
                if highest_rank and highest_division:
                    new_salary = salary_cog.calculate_salary(highest_rank, highest_division)

                    # Update peak rank in DB
                    dbInfo.player_collection.update_one(
                        {'discord_id': member.id},
                        {'$set': {'peak_rank': {'tier': highest_rank, 'division': highest_division}}}
                    )
                    logger.info(f"Stored peak rank for {member.name}: {highest_rank} {highest_division}")
                else:
                    logger.warning(f"No valid rank found for {member.name}")
                    continue

                if is_free_agent:
                    # Free agent: only update salary if the new one is higher
                    if new_salary > current_salary:
                        logger.info(f"Updating salary for free agent {member.name} from {current_salary} to {new_salary}")
                        dbInfo.player_collection.update_one(
                            {"discord_id": member.id}, 
                            {"$set": {"salary": new_salary}}
                        )
                    else:
                        logger.info(f"Free agent {member.name} has a salary of {current_salary}, no update needed.")
                elif manually_adjusted_salary is not None:
                    # If salary has been manually adjusted, only update if the new salary is higher
                    if new_salary > manually_adjusted_salary:
                        logger.info(f"Updating manually adjusted salary for {member.name} from {manually_adjusted_salary} to {new_salary}")
                        dbInfo.player_collection.update_one(
                            {"discord_id": member.id},
                            {"$set": {"manual_salary": new_salary}}
                        )
                    else:
                        logger.info(f"{member.name} has a manually adjusted salary of {manually_adjusted_salary}, no update needed.")
                elif team_code and team_code != "Unassigned":
                    # Player is on a team: Notify staff if salary should be updated
                    if new_salary > current_salary:
                        notification_message = (
                            f"{member.name}'s salary has increased to {new_salary} but is signed to {team_code}. "
                            f"Please manually adjust their salary."
                        )
                        await audit_channel.send(notification_message)
                        logger.info(f"Sent notification: {notification_message}")

                # Update user's nickname to reflect salary or role
                prefix = 'FA' if is_free_agent else (team_code if team_code != "Unassigned" else 'RFA')
                await update_nickname(member, prefix)
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