import config, dbInfo, discord, logging
from discord.ext import commands
from discord.commands import Option
from datetime import datetime

# Setup logging
logger = logging.getLogger(__name__)

class EventsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logger

    @commands.Cog.listener()
    async def on_ready(self):
        # Check and add members to database
        for member in self.bot.get_all_members():
            if not member.bot:
                self.add_member_to_db(member)
        self.logger.info("Bot is ready and members have been checked and added to database.")

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
            self.logger.info(f"Added {member.name} to database.")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.bot:
            return
        
        # Add member to database
        self.add_member_to_db(member)

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
        await self.bot.get_channel(admin_channel).send(embed=embed)


def setup(bot):
    bot.add_cog(EventsCog(bot))

