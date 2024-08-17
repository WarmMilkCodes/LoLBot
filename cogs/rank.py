import discord
from discord.ext import commands
import app.dbInfo as dbInfo
import app.config as config

class RankCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(guild_ids=[config.lol_server], description="Fetch ranks for all players")
    async def fetch_ranks(self, ctx):
        await ctx.defer(ephemeral=True)

        players = dbInfo.player_collection.find({})
        queue_data = {}

        for player in players:
            if "rank_info" in player and player["rank_info"]:
                for rank in player["rank_info"]:
                    queue_type = rank.get("queue_type", "Unknown Queue Type").replace("_", " ").title()
                    tier = rank.get("tier", "Unknown").capitalize()
                    division = rank.get("division", "Unknown").capitalize()
                    rank_text = f"{tier} {division}"
                    
                    if queue_type not in queue_data:
                        queue_data[queue_type] = {}

                    if rank_text not in queue_data[queue_type]:
                        queue_data[queue_type][rank_text] = []

                    queue_data[queue_type][rank_text].append(player["name"])

        embeds = []
        for queue_type, ranks in queue_data.items():
            description = ""
            for rank_text, players in ranks.items():
                players_list = ', '.join(players)
                description += f"**{rank_text}**: {players_list}\n"

            if description:
                embed = discord.Embed(
                    title=f"{queue_type} Ranks",
                    description=description,
                    color=discord.Color.blue()
                )
                embeds.append(embed)

        if embeds:
            for embed in embeds:
                await ctx.respond(embed=embed, ephemeral=True)
        else:
            await ctx.respond("No rank information found for any players.", ephemeral=True)


def setup(bot):
    bot.add_cog(RankCog(bot))
