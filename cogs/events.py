import config, dbInfo, discord, logging
from discord.ext import commands
from discord.commands import Option
from datetime import datetime

# Implement logging 

class EventsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Add logger instance

    @commands.Cog.listener()
    async def on_ready(self):
        # Add check to verify all members are in the database when bot comes online
        # Redundancy in case bot goes offline and members join while offline
        pass

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.bot:
            return
        
        # Add check to see if member is in player table else add them

        member_pfp = member.avatar.url if member.avatar else member.default_avatar.url

        embed = discord.Embed(title="New Member Joined", color=discord.Color.blue())
        embed.add_field(name="Username", value=member.name, inline=True)
        embed.add_field(name="Discord ID", value=member.id, inline=True)
        embed.set_thumbnail(url=member_pfp)

        # send embed to admin channel for joins
        pass



def setup(bot):
    bot.add_cog(EventsCog(bot))

