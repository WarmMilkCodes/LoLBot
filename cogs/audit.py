import discord
from discord.ext import commands, tasks
import logging
import app.config as config
import app.dbInfo as dbInfo
import re

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

    async def update_nickname(self, member, prefix):
        """Update the member's nickname with the given prefix and append salary as suffix if Free Agent, unless Franchise Owner."""
        try:
            # Remove any existing prefix or suffix
            new_nickname = re.sub(r"^(FA \| |S \| |TBD \| |[A-Z]{2,3} \| )", "", member.display_name)
            new_nickname = re.sub(r" \| \d+$", "", new_nickname)  # Remove existing salary suffix if any

            # Franchise Owner logic: Use team_code as prefix if the user has the Franchise Owner role
            franchise_owner_role = discord.utils.get(member.roles, name="Franchise Owner")
            if franchise_owner_role:
                # Retrieve the player's team code from the database
                player_info = dbInfo.player_collection.find_one({"discord_id": member.id})
                team_code = player_info.get("team", "Unassigned") if player_info else "Unassigned"
                
                if team_code != "Unassigned":
                    prefix = team_code  # Set the prefix to the team code for Franchise Owners
                    logger.info(f"User {member.name} (ID: {member.id}) has Franchise Owner role. Prefix set to team_code: {team_code}")
                else:
                    logger.warning(f"User {member.name} (ID: {member.id}) has Franchise Owner role but no team_code found.")
            
            # Add the new prefix if applicable
            if prefix:
                new_nickname = f"{prefix} | {new_nickname}"

            # If the player has the "Free Agents" role, append salary as suffix, but skip this for Franchise Owners
            fa_role = discord.utils.get(member.roles, name="Free Agents")
            if fa_role and not franchise_owner_role:  # Only add salary suffix if they are not a Franchise Owner
                player_info = dbInfo.player_collection.find_one({"discord_id": member.id})
                salary = player_info.get("salary", "TBD") if player_info else "TBD"
                new_nickname = f"{new_nickname} | {salary}"  # Append salary to nickname
                logger.info(f"User {member.name} (ID: {member.id}) has the Free Agents role. Salary: {salary}")

            # Update the member's nickname
            await member.edit(nick=new_nickname)
            logger.info(f"Updated nickname for {member.display_name} to {new_nickname}")

            # Update nickname in the database
            dbInfo.player_collection.update_one({"discord_id": member.id}, {'$set': {'nickname': new_nickname}})
        except Exception as e:
            logger.error(f"Error updating nickname for {member.display_name}: {e}")
        
    
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
                await self.update_nickname(member, prefix)
                
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