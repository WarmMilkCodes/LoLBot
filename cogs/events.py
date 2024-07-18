import config, dbInfo, discord, logging
from discord.ext import commands
from discord.commands import Option
from datetime import datetime

logger = logging.getLogger('lol_log')

class EventsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        logger.info("EventsCog loaded.")

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("Bot is ready. Checking and adding members to the database.")
        for member in self.bot.get_all_members():
            if not member.bot:
                self.add_member_to_db(member)
        logger.info("Bot is ready and members have been checked and added to database.")

    def add_member_to_db(self, member):
        # Check if member is in database
        existing_member = dbInfo.player_collection.find_one({"discord_id": member.id})
        if existing_member is None:
            # Add new member to database
            dbInfo.player_collection.insert_one({
                "discord_id": member.id,
                "name": member.name,
                "team": None,
                "rank": None,
                "joined_at": datetime.utcnow()
            })
            logger.info(f"Added {member.name} ({member.id}) to database.")
        else:
            logger.info(f"Member {member.name} ({member.id}) already exists in database.")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.bot:
            return
        
        logger.info(f"New member joined: {member.name} ({member.id}). Adding to database.")
        # Add member to database
        self.add_member_to_db(member)

        logger.info(f"Notifying admin channel about new member: {member.name} ({member.id}).")
        # Notify in admin channel
        await self.notify_admin_channel(member)

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
            logger.info(f"Admin channel notified about new member: {member.name} ({member.id}).")
        else:
            logger.error(f"Admin channel with ID {admin_channel} not found.")


def setup(bot):
    logger.info("Setting up EventsCog...")
    bot.add_cog(EventsCog(bot))
    logger.info("EventsCog setup completed.")

