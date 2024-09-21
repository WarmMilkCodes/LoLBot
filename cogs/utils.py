import re
import logging
import discord

logger = logging.getLogger('utils_log')

async def update_nickname(member: discord.Member, prefix: str, user_info):
    """Update member's nickname with the given prefix."""
    try:
        # GM / FO Roles
        gm_role = discord.utils.get(member.guild.roles, name="General Managers")
        owner_role = discord.utils.get(member.guild.roles, name="Franchise Owner")

        # Check if user is GM or Owner
        is_gm_or_owner = gm_role in member.roles or owner_role in member.roles

        if is_gm_or_owner:
            # Extract and preserve the team code prefix
            team_prefix_match = re.match(r"^([A-Z]{2,3}) \| ", member.display_name)
            team_prefix = team_prefix_match.group(1) if team_prefix_match else ""
            new_nickname = re.sub(r" \| \d+$", "", member.display_name)  # Remove existing salary suffix if any
        else:
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

        # Preserve GM/Owner's team code prefix if they have one
        if is_gm_or_owner and team_prefix:
            new_nickname = f"{team_prefix} | {new_nickname}".strip(" | ")

        # Edit member's nickname
        await member.edit(nick=new_nickname)
        logger.info(f"Update nickname for {member.name} to {new_nickname}")
    except Exception as e:
        logger.error(f"Error updating nickname for {member.name}: {e}")