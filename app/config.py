import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")
DB_NAME = os.getenv("DB_NAME")
INTENT_COLLECTION = os.getenv("INTENT_COLLECTION")
PLAYER_COLLECTION = os.getenv("PLAYER_COLLECTION")
TEAM_COLLECTION = os.getenv("TEAM_COLLECTION")
PROVIDERS_COLLECTION = os.getenv("PROVIDERS_COLLECTION")
TOURNAMENTS_COLLECTION = os.getenv("TOURNAMENTS_COLLECTION")
TOURNAMENT_CODES_COLLECTION = os.getenv("TOURNAMENT_CODES_COLLECTION")
MATCH_DETAILS_COLLECTION = os.getenv("MATCH_DETAILS_COLLECTION")
REPLAYS_COLLECTION = os.getenv("REPLAYS_COLLECTION")
RIOT_API = os.getenv("RIOT_API")

# Commonly used server channels
bot_admin_channel = 1171263860716601366
bot_testing_channel = 1171263860716601367
riot_id_log_channel = 1194430443362205767
transaction_bot_channel = 1264833838916567090
posted_transactions_channel = 1171263861987475482
submission_log_channel = 1271698169721393193
failure_log_channel = 1171263860716601368
rosters_channel = 1285089150898409522

admin_channels = bot_admin_channel, bot_testing_channel, transaction_bot_channel, submission_log_channel, failure_log_channel

# Server ID
lol_server = 1171263858971770901
