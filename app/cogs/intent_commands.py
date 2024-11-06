import logging
import app.config as config
import app.dbInfo as dbInfo
from discord.ext import commands
from discord.utils import get

class IntentCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(guild_ids=[config.lol_server], description="Returns number of completed intent forms")
    @commands.has_any_role("League Ops", "Bot Guy")
    async def intent_stats(self, ctx):
        guild = ctx.guild
        await self.calculate_intent_stats(ctx, guild)

    async def calculate_intent_stats(self, ctx, guild):
        if guild.id == config.lol_server:
            missing_intent_role = "Missing Intent Form"
            prefix = "**UR LoL Intent Stats**\n"
            intent_playing = dbInfo.intent_collection.count_documents({"Playing": "Yes"})
            intent_not_playing = dbInfo.intent_collection.count_documents({"Playing": "No"})
        
        role = get(guild.roles, name=missing_intent_role)
        users_with_role = [m for m in guild.members if role in m.roles]
        number_of_users = len(users_with_role)

        await ctx.respond(f"{prefix}\nPlaying: {intent_playing}\nNot Playing: {intent_not_playing}\nNot Submitted: {number_of_users}")

def setup(bot):
    bot.add_cog(IntentCommands(bot))