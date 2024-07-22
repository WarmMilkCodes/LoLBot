import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")
DB_NAME = os.getenv("DB_NAME")
INTENT_COLLECTION = os.getenv("INTENT_COLLECTION")
PLAYER_COLLECTION = os.getenv("PLAYER_COLLECTION")
TEAM_COLLECTION = os.getenv("TEAM_COLLECTION")
RIOT_API = os.getenv("RIOT_API")

# Commonly used server channels
bot_admin_channel = 1171263860716601366
riot_id_log_channel = 1194430443362205767