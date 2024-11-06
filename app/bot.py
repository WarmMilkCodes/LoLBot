import discord, os, asyncio, sys
import config
from discord.ext import commands
from utils.logging_config import setup_logging

logger = setup_logging()

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user}")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name="UR LoL"))

# Get the directory of the current script (bot.py)
script_dir = os.path.dirname(os.path.abspath(__file__))

# Add the parent directory to sys.path to ensure 'app' is a recognized package
parent_dir = os.path.dirname(script_dir)
sys.path.insert(0, parent_dir)

def load_extensions():
    bot.logger.info("Loading cogs...")
    # Construct the cogs directory path relative to bot.py
    cogs_dir = os.path.join(script_dir, 'cogs')
    for filename in os.listdir(cogs_dir):
        if filename.endswith('.py'):
            extension_name = f'app.cogs.{filename[:-3]}'
            try:
                bot.load_extension(extension_name)
                bot.logger.info(f'Successfully loaded {extension_name}')
            except Exception as e:
                bot.logger.error(f'Error loading {extension_name}: {e}')

async def main():
    async with bot:
        load_extensions()
        await bot.start(config.DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())