import pymongo, app.config as config, certifi

MongoURL = config.MONGO_URL
ca = certifi.where()
cluster = pymongo.MongoClient(MongoURL, tlsCAFile=ca)

db = cluster[config.DB_NAME]
intent_collection = db[config.INTENT_COLLECTION]
player_collection = db[config.PLAYER_COLLECTION]
team_collection = db[config.TEAM_COLLECTION]
replays_collection = db[config.REPLAYS_COLLECTION]