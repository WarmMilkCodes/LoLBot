import discord
import logging
from discord.ext import commands
from discord.commands import Option
import app.dbInfo as dbInfo
import app.config as config

logger = logging.getLogger(__name__)

class StaffCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(guild_ids=[config.lol_server], description="Return player info embed")
    @commands.has_any_role("Bot Guy", "League Ops")
    async def player_info(self, ctx, user: Option(discord.Member)):
        guild = ctx.guild

        allowed_channels = [self.bot.get_channel(ch_id) for ch_id in config.admin_channels]
        if ctx.channel.id not in config.admin_channels:
            channels_str = ', '.join([ch.mention for ch in allowed_channels if ch])
            return await ctx.respond(f"This command can only be used in the following channels: {channels_str}", ephemeral=True)

        team_id = dbInfo.team_collection.find_one({"team_id": {"$in": [r.id for r in user.roles]}}, {"_id": 0, "team_id": 1})
        team_info = "Unassigned"
        if team_id:
            team_role = ctx.guild.get_role(team_id["team_id"])
            if team_role:
                team_info = team_role.mention

        player_intent = dbInfo.intent_collection.find_one({"ID": user.id})
        player_info = dbInfo.player_collection.find_one({"discord_id": user.id}, {"_id": 0})

        # Debugging: Check what data is returned
        logger.debug(f"Player Intent Data: {player_intent}")

        # Handling the rank_info array with proper formatting
        rank_info_array = player_info.get('rank_info', [])
        rank_info_display = ""
        if rank_info_array:
            for rank in rank_info_array:
                queue_type = rank.get('queue_type', 'N/A').replace('_', ' ').title()
                tier = rank.get('tier', 'N/A').capitalize()
                division = rank.get('division', 'N/A').upper()
                rank_info_display += (f"**Queue Type**: {queue_type}\n"
                                      f"**Tier**: {tier}\n"
                                      f"**Division**: {division}\n\n")
        else:
            rank_info_display = "N/A"

        player_info_list = [
            f"**Discord ID**: {user.id}",
            f"**Username**: {user.name}",
            f"**Server Name**: {user.display_name}",
            f"**RiotID**: {player_info.get('game_name', 'N/A')}#{player_info.get('tag_line', 'N/A')}",
            f"**Rank Info**:\n{rank_info_display}"
        ]

        embed = discord.Embed(title=f"Player Info for {user.display_name}", color=discord.Color.blue())
        embed.set_thumbnail(url=user.avatar.url)
        embed.add_field(name="Player Info", value='\n'.join(player_info_list))

        user_roles = '\n'.join([x.mention for x in user.roles if x != ctx.guild.default_role])
        if user_roles:
            embed.add_field(name="User Roles", value=user_roles)

        # Mapping the intent fields to display in the embed
        if player_intent:
            intent_info = '\n'.join([
                f"**Playing**: {player_intent.get('Playing', 'N/A')}",
                f"**Development Team**: {player_intent.get('Development Team', 'N/A')}",
                f"**Production Team**: {player_intent.get('Production Team', 'N/A')}",
                f"**Completed On**: {player_intent.get('Completed On', 'N/A')}"
            ])
            embed.add_field(name="Intent Info", value=intent_info)
        else:
            embed.add_field(name="Intent Info", value="N/A")

        embed.add_field(name="Team Info", value=team_info)

        await ctx.respond(embed=embed)

def setup(bot):
    bot.add_cog(StaffCog(bot))
