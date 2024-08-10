import discord
import logging
from discord.ext import commands
from discord.commands import Option
import app.dbInfo as dbInfo


logger = logging.getLogger(__name__)


class StaffCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot



def setup(bot):
    bot.add_cog(StaffCog(bot))