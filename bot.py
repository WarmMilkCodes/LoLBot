import discord, os, logging
from config import token as t
from discord.ext import commands

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
logging.basicConfig(level=logging.INFO, filename="bot.log", filemode="a", format="%(asctime)s %(levelname)s:%(message)s")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name="UR LoL"))

# Load all cogs
for filename in os.listdir('./cogs'):
    if filename.endswith('.py'):
        try:
            bot.load_extension(f'cogs.{filename[:-3]}')
            logging.info(f'cogs.{filename[:-3]} loaded.')
        except Exception as e:
            logging.error(f'Error loading cogs.{filename[:-3]}: {e}')

bot.run(t)