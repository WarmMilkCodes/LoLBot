import app.config as config
import app.dbInfo as dbInfo
import discord, logging, secrets
from discord.ext import commands
from discord.commands import Option
from discord.ext.commands import CommandError, MissingAnyRole
from bson import ObjectId
from datetime import datetime, timezone
import pytz

logger = logging.getLogger(__name__)

class Transactions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    ### Helper Functions ###

    # Function to retrieve GM ID from database
    async def get_gm_id(self, team_code: str) -> int:
        team = dbInfo.team_collection.find_one(
            {"team_code":team_code}
        )

        if team:
            gm_role_id = team['gm_id']
            return gm_role_id
        return None