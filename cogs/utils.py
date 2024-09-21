import re
import logging
import discord

logger = logging.getLogger('utils_log')

async def update_nickname(member: discord.Member, prefix: str, user_info):
    """Update member's nickname with the given prefix."""
    try:
        # Remove any existing prefix and salary suffix
        new_nickname = re.sub(r"^(FA \| |S \| |[A-Z]{2,3} \| )", "", member.display_name)
        new_nickname = re.sub(r" \| \d+$", "", new_nickname)  # Remove existing salary suffix if any

        # Check if the user is a free agent
        FA = discord.utils.get(member.guild.roles, name="Free Agents")

        if prefix == "FA" and user_info:
            # Fetch salary and append to nickname if Free Agent
            player_salary = user_info.get("salary", "TBD")
            new_nickname = f"{prefix} | {new_nickname} | {player_salary}"
        elif prefix:
            # Add prefix without the salary
            new_nickname = f"{prefix} | {new_nickname}"

        # Clean up trailing '|' if there's no new prefix
        new_nickname = new_nickname.strip(" | ")

        # Edit member's nickname
        await member.edit(nick=new_nickname)
        logger.info(f"Update nickname for {member.name} to {new_nickname}")
    except Exception as e:
        logger.error(f"Error updating nickname for {member.name}: {e}")