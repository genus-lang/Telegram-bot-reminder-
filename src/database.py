import pymongo
import json
import os
from src.config import MONGO_URI, ADMIN_CHAT_ID

client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
db = client["telegram_bot_db"]

users_col = db["users"]
sent_col = db["sent"]
pending_col = db["pending"]
knowledge_col = db["knowledge"]
announcers_col = db["announcers"]
history_col = db["history"]

# ----------------- DB MIGRATION -----------------
if users_col.count_documents({}) == 0:
    print("Migrating JSON data to MongoDB...")
    try:
        if os.path.exists("data/users.json"):
            with open("data/users.json", "r") as f:
                u_data = json.load(f)
                if u_data: users_col.insert_many([{"_id": str(k), **v} for k, v in u_data.items()])
                
        if os.path.exists("data/sent.json"):
            with open("data/sent.json", "r") as f:
                s_data = json.load(f)
                if s_data: sent_col.insert_many([{"_id": str(k)} for k in s_data])
                
        if os.path.exists("data/pending.json"):
            with open("data/pending.json", "r") as f:
                p_data = json.load(f)
                if p_data: pending_col.insert_many([{"_id": str(k), **v} for k, v in p_data.items()])
                
        if os.path.exists("data/knowledge.json"):
            with open("data/knowledge.json", "r") as f:
                k_data = json.load(f)
                if k_data: knowledge_col.insert_many(k_data)
                
        if os.path.exists("data/announcers.json"):
            with open("data/announcers.json", "r") as f:
                a_data = json.load(f)
                if a_data: announcers_col.insert_many([{"_id": str(k)} for k in a_data])
                
        print("Migration complete!")
    except Exception as e:
        print("Migration skip/error:", e)

# ----------------- IN-MEMORY STATE -----------------
print("Loading data from MongoDB into RAM...")
users = {doc["_id"]: doc for doc in users_col.find()}
pending = {doc["_id"]: doc for doc in pending_col.find()}
sent = set(doc["_id"] for doc in sent_col.find())
knowledge = list(knowledge_col.find())
announcers = set(doc["_id"] for doc in announcers_col.find())

if ADMIN_CHAT_ID and ADMIN_CHAT_ID not in announcers:
    announcers.add(ADMIN_CHAT_ID)
    announcers_col.insert_one({"_id": ADMIN_CHAT_ID})
