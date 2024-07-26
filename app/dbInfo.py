import pymongo, app.config as config, certifi

MongoURL = config.MONGO_URL
ca = certifi.where()
cluster = pymongo.MongoClient(MongoURL, tlsCAFile=ca)

db = cluster[config.DB_NAME]
intent_collection = db[config.INTENT_COLLECTION]
player_collection = db[config.PLAYER_COLLECTION]
team_collection = db[config.TEAM_COLLECTION]
replays_collection = db[config.REPLAYS_COLLECTION]
providers_collection = db[config.PROVIDERS_COLLECTION]
tournaments_collection = db[config.TOURNAMENTS_COLLECTION]
tournament_codes_collection = db[config.TOURNAMENT_CODES_COLLECTION]
match_details_collection = db[config.MATCH_DETAILS_COLLECTION]

# Providers Collection
def get_provider_id():
    provider = providers_collection.find_one()
    return provider['provider_id'] if provider else None

def save_provider_id(provider_id):
    providers_collection.update_one({}, {"$set": {"provider_id": provider_id}}, upsert=True)

# Tournaments Collection
def get_tournament_id():
    tournament = tournaments_collection.find_one()
    return tournament['tournament_id'] if tournament else None

def save_tournament_id(tournament_id, name):
    tournaments_collection.update_one({}, {"$set": {"tournament_id": tournament_id, "name": name}}, upsert=True)

# TournamentCodes Collection
def save_tournament_codes(tournament_id, tournament_codes):
    tournament_codes_collection.insert_many([{"code": code, "tournament_id": tournament_id, "status": "unused"} for code in tournament_codes])

def get_tournament_codes(tournament_id):
    codes = tournament_codes_collection.find({"tournament_id": tournament_id})
    return [code['code'] for code in codes]

# MatchDetails Collection
def save_match_details(match_details):
    match_details_collection.insert_one(match_details)

def get_match_details(match_id):
    return match_details_collection.find_one({"match_id": match_id})