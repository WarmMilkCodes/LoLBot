import discord, os, logging, asyncio
from config import token as t
from discord.ext import commands

intents = discord.Intents.all()

#configure logging
logger = logging.getLogger('lol_log')
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler('bot.log')
file_handler.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s %(levelname)s:%(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.addHandler(console_handler)


bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user}")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name="UR LoL"))

# Load all cogs
def load_extensions():
    logger.info("Loading cogs...")
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            try:
                bot.load_extension(f'cogs.{filename[:-3]}')
            except Exception as e:
                logging.error(f'Error loading cogs.{filename[:-3]}: {e}')

async def main():
    async with bot:
        load_extensions()
        await bot.start(t)

if __name__ == "__main__":
    asyncio.run(main())