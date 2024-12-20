import discord
from discord.ext import commands, tasks
import logging
import config
import dbInfo
import re
from helper import update_nickname
from .salaries import SalaryCog

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

                self.bot.logger.info(f"Auditing member: {member.name}")

                player_info = dbInfo.player_collection.find_one({"discord_id": member.id})
                if not player_info:
                    self.bot.logger.warning(f"No player info found for {member.name} in database")
                    continue

                team_code = player_info.get("team", "Unassigned")
                is_free_agent = discord.utils.get(member.roles, name="Free Agents") is not None
                current_salary = player_info.get("salary", 0)
                manually_adjusted_salary = player_info.get("manual_salary", None)
                rank_info = player_info.get('rank_info', [])
                historical_rank_info = player_info.get('historical_rank_info', {})
                peak_rank = player_info.get('peak_rank', {})

                # Calculate the player's highest rank and salary
                salary_cog = SalaryCog(self.bot)
                highest_rank, highest_division = salary_cog.get_highest_rank(rank_info, historical_rank_info)

                # Store peak rank
                if highest_rank and highest_division:
                    new_salary = salary_cog.calculate_salary(highest_rank, highest_division)
                    
                    # Check if current rank exceeds peak rank
                    if peak_rank:
                        peak_tier = peak_rank.get('tier')
                        peak_division = peak_rank.get('division')

                        # Compare rank order and division
                        if salary_cog.is_rank_higher(highest_rank, highest_division, peak_tier, peak_division):
                            # Update peak rank if current rank is higher
                            dbInfo.player_collection.update_one(
                                {'discord_id': member.id},
                                {'$set': {'peak_rank': {'tier': highest_rank, 'division': highest_division}}}
                            )
                            self.bot.logger.info(f"Stored peak rank for {member.name}: {highest_rank} {highest_division}")

                    else:
                        # If no peak rank exists, store current as peak
                        dbInfo.player_collection.update_one(
                            {'discord_id': member.id},
                            {'$set': {'peak_rank': {'tier': highest_rank, 'division': highest_division}}}
                        )
                        self.bot.logger.info(f"Stored peak rank for {member.name}: {highest_rank} {highest_division}")
                else:
                    self.bot.logger.warning(f"No valid rank found for {member.name}")
                    continue

                # Salary adjustment logic for FA and team players                        
                if is_free_agent:
                    # Free agent: only update salary if the new one is higher
                    if new_salary > current_salary:
                        self.bot.logger.info(f"Updating salary for free agent {member.name} from {current_salary} to {new_salary}")
                        dbInfo.player_collection.update_one(
                            {"discord_id": member.id}, 
                            {"$set": {"salary": new_salary}}
                        )
                    else:
                        self.bot.logger.info(f"Free agent {member.name} has a salary of {current_salary}, no update needed.")
                elif manually_adjusted_salary is not None:
                    # If salary has been manually adjusted, only update if the new salary is higher
                    if new_salary > manually_adjusted_salary:
                        self.bot.logger.info(f"Updating manually adjusted salary for {member.name} from {manually_adjusted_salary} to {new_salary}")
                        dbInfo.player_collection.update_one(
                            {"discord_id": member.id},
                            {"$set": {"manual_salary": new_salary}}
                        )
                    else:
                        self.bot.logger.info(f"{member.name} has a manually adjusted salary of {manually_adjusted_salary}, no update needed.")
                elif team_code and team_code != "Unassigned":
                    # Check if player meets the threshold for a salary increase
                    if self.meets_threshold(highest_rank, highest_division, peak_rank):
                        if new_salary > current_salary:
                            notification_message = (
                                f"{member.name}'s salary has increased to {new_salary} but is signed to {team_code}. "
                                f"Please manually adjust their salary."
                            )
                            await audit_channel.send(notification_message)
                            self.bot.logger.info(f"Sent notification: {notification_message}")

                # Update user's nickname to reflect salary or role
                prefix = 'FA' if is_free_agent else (team_code if team_code != "Unassigned" else 'RFA')
                await update_nickname(member, prefix)
                self.bot.logger.info(f"Nickname updated for {member.display_name}")

            self.bot.logger.info("Audit finished. Next audit will occur in 24 hours.")

    def meets_threshold(self, current_tier, current_division, peak_rank):
        """Check if the player meets the threshold for salary update notification."""
        thresholds = {
            "IRON": ("BRONZE", "III"),
            "BRONZE": ("SILVER", "III"),
            "SILVER": ("GOLD", "III"),
            "GOLD": ("PLATINUM", "III"),
            "PLATINUM": ("DIAMOND", "IV"),
            "DIAMOND": {
                "IV": ("DIAMOND", "II"),
                "III": ("DIAMOND", "II"),
                "II": ("DIAMOND", "I"),
                "I": None  # No further salary updates after reaching Diamond I
            }
        }

        if current_tier in thresholds:
            if current_tier == "DIAMOND":
                if current_division in thresholds[current_tier]:
                    # Diamond 1 has no further updates
                    return thresholds[current_tier][current_division] is not None
            else:
                threshold_tier, threshold_division = thresholds[current_tier]
                # Now passing both current and threshold divisions to is_rank_higher
                return SalaryCog.is_rank_higher(self, current_tier, current_division, threshold_tier, threshold_division)

        return False


    @audit_roles.before_loop
    async def before_audit_roles(self):
        await self.bot.wait_until_ready()

    async def remove_role_from_member(self, member, role, reason):
        """Remove a role from a member with error handling"""
        try:
            await member.remove_roles(role, reason=reason)
        except Exception as e:
            self.bot.logger.error(f"Error removing role {role} from {member.display_name}: {e}")

    async def update_team_in_database(self, player_id, new_team):
        """Update player's team information in database"""
        dbInfo.player_collection.update_one({"discord_id": player_id}, {'$set' : {'team': new_team}})

def setup(bot):
    bot.add_cog(Audit(bot))