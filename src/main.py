import time
import os
import threading
import requests
from flask import Flask
from src.config import BOT_TOKEN, CHECK_EVERY_SECONDS, executor
from src.database import pending, pending_col, history_col
from src.scrapers import check_codeforces, check_codechef, check_leetcode
from src.handlers import process_message

last_update_id = None

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive"

def run_server():
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)

def handle_updates():
    global last_update_id
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    params = {"timeout": 10}
    if last_update_id is not None:
        params["offset"] = last_update_id + 1
    try:
        data = requests.get(url, params=params, timeout=15).json()
    except:
        return
    for update in data.get("result", []):
        last_update_id = update["update_id"]
        executor.submit(process_message, update)

def cleanup_pending():
    now = time.time()
    one_day = 86400
    expired = [k for k, v in pending.items() if now - v.get("time", 0) > one_day]
    for k in expired:
        del pending[k]
        executor.submit(pending_col.delete_one, {"_id": k})
    if expired:
        print(f"Cleaned up {len(expired)} expired pending message(s)")

def delete_telegram_message(chat_id, message_id, doc_id):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage"
    try:
        requests.post(url, data={"chat_id": chat_id, "message_id": message_id}, timeout=5)
    except:
        pass
    history_col.delete_one({"_id": doc_id})

def delete_expired_messages():
    now = time.time()
    expired = list(history_col.find({"delete_at": {"$lte": now}}).limit(100))
    for doc in expired:
        executor.submit(delete_telegram_message, doc["chat_id"], doc["message_id"], doc["_id"])

def main():
    print("Starting Flask Keep-Alive Server...")
    threading.Thread(target=run_server, daemon=True).start()
    
    print("Bot is running...")
    while True:
        handle_updates()
        check_codeforces()
        check_codechef()
        check_leetcode()
        cleanup_pending()
        delete_expired_messages()
        print("Checked all platforms...")
        time.sleep(CHECK_EVERY_SECONDS)

if __name__ == "__main__":
    main()
