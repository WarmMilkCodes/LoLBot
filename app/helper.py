import re
import logging
import discord
import dbInfo

logger = logging.getLogger(__name__)

async def update_nickname(member: discord.Member, prefix: str):
    """Update the member's nickname with the given prefix and append salary as suffix if Free Agent or Restricted Free Agent, unless Franchise Owner."""
    try:
        # Log original nickname
        logger.debug(f"Original nickname: {member.display_name}")
        
        # Remove any existing prefix or suffix
        new_nickname = re.sub(r"^(FA \| |RFA \| |S \| |TBD \| |[A-Z]{2,3} \| )| \| (\d{3}|TBD)$", "", member.display_name).strip()

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
            new_nickname = f"{prefix} | {new_nickname}".strip()

        # Ensure nickname not empty
        if not new_nickname.strip():
            new_nickname = member.name

        logger.debug(f"Processed new nickname: {new_nickname}")

        # Update the member's nickname
        await member.edit(nick=new_nickname)
        logger.info(f"Updated nickname for {member.display_name} to {new_nickname}")

        # Update nickname in the database
        dbInfo.player_collection.update_one({"discord_id": member.id}, {'$set': {'nickname': new_nickname}})
    except Exception as e:
        logger.error(f"Error updating nickname for {member.display_name}: {e}")
