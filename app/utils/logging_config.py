import logging
import discord
from discord.ext import commands
import config

class DiscordLogHandler(logging.Handler):
    def __init__(self, bot, channel_id):
        super().__init__()
        self.bot = bot
        self.channel_id = channel_id

    async def send_log_message(self, message):
        await self.bot.wait_until_ready()
        channel = self.bot.get_channel(self.channel_id)
        if channel:
            await channel.send(message)
        else:
            print(f"Logging channel with ID {self.channel_id} not found.")

    def emit(self, record):
        log_entry = self.format(record)
        self.bot.loop.create_task(self.send_log_message(f"⚠️ {log_entry}"))

def setup_logging(bot):
    logger = logging.getLogger('lol_log')
    logger.setLevel(logging.INFO)

    # File handler
    file_handler = logging.FileHandler('bot.log')
    file_handler.setLevel(logging.INFO)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # Formatter
    formatter = logging.Formatter('%(asctime)s %(levelname)s:%(name)s:%(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # Discord handler
    discord_handler = DiscordLogHandler(bot, config.log_channel_id)
    discord_handler.setLevel(logging.WARNING)  # Log only WARNING and ERROR messages to Discord
    discord_handler.setFormatter(formatter)
    logger.addHandler(discord_handler)

    return logger
