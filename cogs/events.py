import app.config as config
import app.dbInfo as dbInfo
import discord
import logging
from discord.ext import commands
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)

class EventsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        for member in self.bot.get_all_members():
            if not member.bot:
                self.add_member_to_db(member)
        logger.info("Bot is ready and members have been checked and added to database.")

    def add_member_to_db(self, member):
        existing_member = dbInfo.player_collection.find_one({"discord_id": member.id})
        if existing_member is None:
            # Add new member(s) to database
            dbInfo.player_collection.insert_one({
                "discord_id": member.id,
                "name": member.name,
                "team": None,
                "rank": None,
                "joined_at": datetime.now(pytz.utc).strftime('%m-%d-%Y'),
                "left_at": None  # Initialize with None
            })
            logger.info(f"Added {member.name} ({member.id}) to database.")
        else:
            # Update the member's name in case it has changed
            dbInfo.player_collection.update_one(
                {"discord_id": member.id},
                {"$set": {"name": member.name}}
            )
            logger.info(f"Member {member.name} ({member.id}) already exists in database.")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.bot:
            return
        
        logger.info(f"New member joined: {member.name} ({member.id}). Adding to database.")

        existing_member = dbInfo.player_collection.find_one({"discord_id": member.id})
        if existing_member:
            # Clear the left_at field if it exists
            dbInfo.player_collection.update_one(
                {"discord_id": member.id},
                {"$set": {"left_at": None}}
            )
            logger.info(f"Cleared 'left_at' date for returning member: {member.name} ({member.id})")
        else:
            # Add the new member to the database
            self.add_member_to_db(member)

        # Assign "Missing Intent Form" role to new member
        await self.assign_role(member, "Missing Intent Form")

        # Notify in admin channel
        await self.notify_admin_channel(member)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        """Updates the member's document in the database when they leave the server."""
        if member.bot:
            return
        
        left_date = datetime.now(pytz.utc).strftime('%m-%d-%Y')
        dbInfo.player_collection.update_one(
            {"discord_id": member.id},
            {"$set": {"left_at": left_date}},
            upsert=True
        )

        dbInfo.intent_collection.update_one(
            {"ID": member.id},
            {"$set": {"left_at": left_date}},
            upsert=True
        )
        logger.info(f"Updated {member.name} ({member.id}) in the database(s) with the date they left: {left_date}")

        member_pfp = member.avatar.url if member.avatar else member.default_avatar.url
        embed = discord.Embed(title="Member Left", color=discord.Color.red())
        embed.add_field(name="Display Name", value=member.display_name, inline=True)
        embed.add_field(name="Username", value=member.name, inline=True)
        embed.add_field(name="Discord ID", value=member.id, inline=True)
        embed.set_thumbnail(url=member_pfp)

        admin_channel = config.bot_admin_channel
        channel = self.bot.get_channel(admin_channel)
        if channel:
            await channel.send(embed=embed)
        else:
            logger.error(f"Admin channel with ID {admin_channel} not found.")

    async def assign_role(self, member, role_name):
        guild = member.guild
        role = discord.utils.get(guild.roles, name=role_name)

        if role:
            await member.add_roles(role)
            logger.info(f"Assigned role '{role_name}' to {member.name}")
        else:
            logger.error(f"Role '{role_name}' not found in guild '{guild.name}'.")

    async def notify_admin_channel(self, member):
        member_pfp = member.avatar.url if member.avatar else member.default_avatar.url
        embed = discord.Embed(title="New Member Joined", color=discord.Color.blue())
        embed.add_field(name="Display Name", value=member.display_name, inline=True)
        embed.add_field(name="Username", value=member.name, inline=True)
        embed.add_field(name="Discord ID", value=member.id, inline=True)
        embed.set_thumbnail(url=member_pfp)

        admin_channel = config.bot_admin_channel
        channel = self.bot.get_channel(admin_channel)

        if channel:
            await channel.send(embed=embed)
        else:
            logger.error(f"Admin channel with ID {admin_channel} not found.")

def setup(bot):
    bot.add_cog(EventsCog(bot))
