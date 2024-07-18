import pymongo, config, certifi

MongoURL = config.MongoClient
ca = certifi.where()
cluster = pymongo.MongoClient(MongoURL, tlsCAFile=ca)
db = cluster[config.db]
intent_collection = db[config.intent_collection]
player_collection = db[config.player_collection]
team_collection = db[config.team_collection]
replay_collection = db[config.replay_collection]