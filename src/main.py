import time
import os
import threading
import requests
from flask import Flask
from src.config import BOT_TOKEN, CHECK_EVERY_SECONDS, executor
from src.database import pending, pending_col, history_col
from src.scrapers import check_codeforces, check_codechef, check_leetcode
from src.timetable import check_lectures
from src.handlers import process_message

last_update_id = None

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive"

@app.route('/health')
def health():
    return "OK", 200

@app.route('/warm')
def warm():
    return "Warmed", 200

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

def background_jobs():
    while True:
        check_codeforces()
        check_codechef()
        check_leetcode()
        check_lectures()
        cleanup_pending()
        delete_expired_messages()
        print("Checked all platforms...")
        time.sleep(CHECK_EVERY_SECONDS)

def main():
    print("Starting Flask Keep-Alive Server...")
    threading.Thread(target=run_server, daemon=True).start()
    
    print("Starting Background Jobs...")
    threading.Thread(target=background_jobs, daemon=True).start()
    
    print("Bot is running...")
    while True:
        handle_updates()
        # Sleep for a tiny fraction just to prevent 100% CPU on fast iteration,
        # but the request itself blocks for 10s if there's no message due to long polling.
        time.sleep(0.1)

if __name__ == "__main__":
    main()
