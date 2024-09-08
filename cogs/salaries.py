import discord
from discord.ext import commands
import app.dbInfo as dbInfo
import app.config as config
import logging

logger = logging.getLogger('salary_log')

RANK_ORDER = {
    "IRON": 1,
    "BRONZE": 2,
    "SILVER": 3,
    "GOLD": 4,
    "PLATINUM": 5,
    "EMERALD": 6,
    "DIAMOND": 7,
    "MASTER": 8,
    "GRANDMASTER": 9,
    "CHALLENGER": 10
}

DIVISION_ORDER = {
    'IV': 0,
    'III': 10,
    'II': 20,
    'I': 30
}

BASE_SALARY = {
    'IRON': 10,
    'BRONZE': 50,
    'SILVER': 90,
    'GOLD': 130,
    'PLATINUM': 170,
    'DIAMOND': 210,
    'MASTER': 250,
    'GRANDMASTER': 270,
    'CHALLENGER': 290
}


class SalaryCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def calculate_salary(self, rank, division):
        """Calculate salary based on rank and division"""
        base = BASE_SALARY.get(rank, 0)
        division_bonus = DIVISION_ORDER.get(division, 0)
        return base + division_bonus

    def get_highest_rank(self, rank_info, historical_rank_info):
        """Determine the highest rank a player has from current and historical data"""
        highest_rank = None
        highest_division = None

        # Check current rank_info
        for rank_entry in rank_info:
            if rank_entry['queue_type'] == "RANKED_SOLO_5x5":
                rank = rank_entry.get('tier')
                division = rank_entry.get('division')
                if highest_rank is None or (RANK_ORDER[rank] > RANK_ORDER[highest_rank]) or (RANK_ORDER[rank] == RANK_ORDER[highest_rank] and DIVISION_ORDER[division] > DIVISION_ORDER[highest_division]):
                    highest_rank = rank
                    highest_division = division

        # Check historical rank_info
        for date, rank_data in historical_rank_info.items():
            for rank_entry in rank_data:
                if rank_entry['queue_type'] == "RANKED_SOLO_5x5":
                    rank = rank_entry.get('tier')
                    division = rank_entry.get('division')
                    if highest_rank is None or (RANK_ORDER[rank] > RANK_ORDER[highest_rank]) or (RANK_ORDER[rank] == RANK_ORDER[highest_rank] and DIVISION_ORDER[division] > DIVISION_ORDER[highest_division]):
                        highest_rank = rank
                        highest_division = division

        return highest_rank, highest_division

    @commands.slash_command(guild_ids=[config.lol_server], description="Calculate and display salaries for all players based on their highest rank")
    @commands.has_role("Bot Guy")
    async def calculate_all_salaries(self, ctx):
        await ctx.defer()

        players = dbInfo.player_collection.find({"left_at": None, "salary": None})  # Only active players and those who don't have a salary already
        salary_report = []
        total_salary = 0

        for player in players:
            player_name = player.get('name', 'Unknown')
            rank_info = player.get('rank_info', [])
            historical_rank_info = player.get('historical_rank_info', {})

            # Get the highest rank
            highest_rank, highest_division = self.get_highest_rank(rank_info, historical_rank_info)

            if highest_rank and highest_division:
                salary = self.calculate_salary(highest_rank, highest_division)
                
                # Store the calculated salary in the player's document
                dbInfo.player_collection.update_one(
                    {"discord_id": player['discord_id']},
                    {"$set": {"salary": salary}}
                )

                salary_report.append(f"**{player_name}**: {highest_rank} {highest_division} - Salary: {salary}")
                total_salary += salary
            else:
                salary_report.append(f"**{player_name}**: No rank data - Salary: N/A")

        # Split the report into multiple embeds if the content exceeds the 4096-character limit
        max_length = 4096
        embed_list = []
        description = ""

        for report_line in salary_report:
            if len(description) + len(report_line) > max_length:
                embed = discord.Embed(title="Player Salary Report", description=description, color=discord.Color.green())
                embed_list.append(embed)
                description = ""

            description += report_line + "\n"

        # Add the last part of the report
        if description:
            embed = discord.Embed(title="Player Salary Report", description=description, color=discord.Color.green())
            embed_list.append(embed)

        # Add the total salary to the last embed
        embed_list[-1].set_footer(text=f"Total Salary: {total_salary}")

        # Send all embeds
        for embed in embed_list:
            await ctx.send(embed=embed)


    @commands.slash_command(guild_ids=[config.lol_server], description="Manually adjust a player's salary")
    @commands.has_any_role("Bot Guy", "Commissioner", "URLOL Owner")
    async def adjust_salary(self, ctx, user: discord.Member, new_salary: int):
        """Command for staff to manually adjust a player's salary"""
        player_data = dbInfo.player_collection.find_one({"discord_id": user.id})

        if not player_data:
            return await ctx.respond(f"{user.mention} was not found in the database", ephemeral=True)
        
        current_salary = player_data.get('salary')

        if not current_salary:
            return await ctx.respond(f"{user.mention} does not have a current salary and cannot be manually changed.", ephemeral=True)

        dbInfo.player_collection.update_one(
            {"discord_id": user.id},
            {"$set": {
                "previous_salary": current_salary,
                "manual_salary": new_salary
                }}
        )

        await ctx.respond(f"Adjusted {user.mention}'s salary to {new_salary}.", ephemeral=True)

        # Log the manual adjustment
        logger.info(f"{ctx.author.name} adjusted {user.name}'s salary to {new_salary}")

def setup(bot):
    bot.add_cog(SalaryCog(bot))
