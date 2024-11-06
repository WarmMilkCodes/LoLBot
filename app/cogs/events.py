import config
import dbInfo
import discord
import logging
from discord.ext import commands
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)

class EventsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.is_ready = False  # Flag to prevent multiple executions of on_ready

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.is_ready:
            guild = self.bot.get_guild(config.lol_server)  # Get the guild (server) object
            server_members = {member.id for member in guild.members if not member.bot}  # Get current members' IDs
            
            # Get all members from the database
            db_members = dbInfo.player_collection.find({"left_at": None}, {"discord_id": 1})  # Fetch all members without 'left_at'
            db_member_ids = {member["discord_id"] for member in db_members}

            # Find the members who are in the database but not in the server anymore
            missing_members = db_member_ids - server_members

            if missing_members:
                # Update the 'left_at' field for all missing members
                left_date = datetime.now(pytz.utc).strftime('%m-%d-%Y')
                dbInfo.player_collection.update_many(
                    {"discord_id": {"$in": list(missing_members)}},
                    {"$set": {"left_at": left_date}}
                )
                logger.info(f"Marked {len(missing_members)} members as left in the database.")
            else:
                logger.info("No missing members found during reverse sync.")
            
            # Add or update members who are still in the server
            for member in guild.members:
                if not member.bot:
                    avatar_url = str(member.avatar.url if member.avatar else member.default_avatar.url)
                    self.add_member_to_db(member, avatar_url)
            
            logger.info("Bot is ready and members have been checked and added to database.")
            self.is_ready = True

    def add_member_to_db(self, member, avatar_url):
        existing_member = dbInfo.player_collection.find_one({"discord_id": member.id})
        if existing_member is None:
            # Add new member(s) to database
            dbInfo.player_collection.insert_one({
                "discord_id": member.id,
                "name": member.name,
                "team": None,
                "rank": None,
                "joined_at": datetime.now(pytz.utc).strftime('%m-%d-%Y'),
                "left_at": None,  # Initialize with None
                "avatar_url": avatar_url
            })
            logger.info(f"Added {member.name} ({member.id}) to database.")
        else:
            # Update the member's name and avatar in case they changed
            dbInfo.player_collection.update_one(
                {"discord_id": member.id},
                {"$set": {"name": member.name, "avatar_url": avatar_url}}
            )
            logger.info(f"Updated member {member.name} ({member.id}) in database.")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.bot:
            return

        logger.info(f"New member joined: {member.name} ({member.id}). Adding to database.")
        avatar_url = str(member.avatar.url if member.avatar else member.default_avatar.url)

        existing_member = dbInfo.player_collection.find_one({"discord_id": member.id})
        if existing_member:
            # Clear the left_at field if it exists (i.e. member rejoined)
            dbInfo.player_collection.update_one(
                {"discord_id": member.id},
                {"$set": {"left_at": None, "avatar_url": avatar_url}}
            )
            logger.info(f"Cleared 'left_at' date for returning member: {member.name} ({member.id})")
        else:
            # Add the new member to the database
            self.add_member_to_db(member, avatar_url)

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
            {"$set": {"left_at": left_date, "team": None}},
            upsert=True
        )

        logger.info(f"Updated {member.name} ({member.id}) in the database with the date they left: {left_date}")

        dbInfo.intent_collection.find_one_and_delete(
            {"ID": member.id}
        )

        logger.info(f"Deleted {member.name}'s intent collection record due to leaving server.")
        
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
