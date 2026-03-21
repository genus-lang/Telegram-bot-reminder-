import requests
import time
import json
import re
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")


import pymongo

MONGO_URI = os.getenv("MONGO_URI")
client = pymongo.MongoClient(MONGO_URI)
db = client["telegram_bot_db"]

users_col = db["users"]
sent_col = db["sent"]
pending_col = db["pending"]
knowledge_col = db["knowledge"]
announcers_col = db["announcers"]
history_col = db["history"]

DEFAULT_REMINDER = 1800   # 30 min
CHECK_EVERY_SECONDS = 30  # poll more often, but still light
MATCH_THRESHOLD = 0.5     # minimum similarity to auto-reply (0.0 - 1.0)

# ----------------- THREADING UTILS -----------------
executor = ThreadPoolExecutor(max_workers=50)

# ----------------- DB MIGRATION -----------------
# If DB is empty, migrate from local JSON files
if users_col.count_documents({}) == 0:
    print("Migrating JSON data to MongoDB...")
    try:
        with open("users.json", "r") as f:
            u_data = json.load(f)
            if u_data:
                users_col.insert_many([{"_id": str(k), **v} for k, v in u_data.items()])
        with open("sent.json", "r") as f:
            s_data = json.load(f)
            if s_data:
                sent_col.insert_many([{"_id": str(k)} for k in s_data])
        with open("pending.json", "r") as f:
            p_data = json.load(f)
            if p_data:
                pending_col.insert_many([{"_id": str(k), **v} for k, v in p_data.items()])
        with open("knowledge.json", "r") as f:
            k_data = json.load(f)
            if k_data:
                knowledge_col.insert_many(k_data)
        with open("announcers.json", "r") as f:
            a_data = json.load(f)
            if a_data:
                announcers_col.insert_many([{"_id": str(k)} for k in a_data])
        print("Migration complete!")
    except Exception as e:
        print("Migration skip/error:", e)

# ----------------- IN-MEMORY STATE -----------------
# Load DB into RAM for lightning-fast queries
print("Loading data from MongoDB into RAM...")
users = {doc["_id"]: doc for doc in users_col.find()}
pending = {doc["_id"]: doc for doc in pending_col.find()}
sent = set(doc["_id"] for doc in sent_col.find())
knowledge = list(knowledge_col.find())
announcers = set(doc["_id"] for doc in announcers_col.find())

if ADMIN_CHAT_ID not in announcers:
    announcers.add(ADMIN_CHAT_ID)
    announcers_col.insert_one({"_id": ADMIN_CHAT_ID})

last_update_id = None

# ----------------- KNOWLEDGE / MATCHING -----------------
def extract_keywords(text):
    """Extract meaningful keywords from text (lowercase, no short/stop words)."""
    stop_words = {
        "i", "me", "my", "we", "our", "you", "your", "he", "she", "it",
        "they", "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "do", "does", "did", "has", "have", "had", "will", "would", "can",
        "could", "should", "may", "might", "to", "of", "in", "on", "at",
        "for", "with", "and", "or", "but", "not", "so", "if", "then",
        "this", "that", "what", "which", "who", "how", "when", "where",
        "why", "all", "each", "every", "any", "no", "yes", "ok", "hi",
        "hello", "hey", "please", "thanks", "thank", "from", "by", "up",
        "about", "into", "just", "also", "than", "very", "too", "here",
        # Hindi common words
        "kya", "hai", "ka", "ki", "ke", "ko", "se", "me", "ye", "wo",
        "toh", "bhi", "aur", "par", "nahi", "na", "ho", "haan", "ji",
        "bhai", "sir", "mam", "mujhe", "mera", "tera", "uska"
    }
    words = re.findall(r'[a-zA-Z0-9\u0900-\u097F]+', text.lower())
    return [w for w in words if len(w) > 1 and w not in stop_words]

def find_best_match(user_text):
    """
    Find the best matching Q&A from the knowledge base.
    Returns (answer, score) or (None, 0) if no good match.
    """
    user_keywords = set(extract_keywords(user_text))
    if not user_keywords:
        return None, 0

    best_answer = None
    best_score = 0

    for entry in knowledge:
        stored_keywords = set(entry.get("keywords", []))
        if not stored_keywords:
            continue

        # Calculate Jaccard similarity
        common = user_keywords & stored_keywords
        total = user_keywords | stored_keywords
        score = len(common) / len(total) if total else 0

        if score > best_score:
            best_score = score
            best_answer = entry["answer"]

    return best_answer, best_score

def learn_qa(question, answer):
    """Save a new Q&A pair to the knowledge base."""
    keywords = extract_keywords(question)
    # Don't save if question is too short to be meaningful
    if len(keywords) < 1:
        return
    new_qa = {
        "question": question,
        "answer": answer,
        "keywords": keywords
    }
    knowledge.append(new_qa)
    executor.submit(knowledge_col.insert_one, new_qa.copy())

# ----------------- TELEGRAM HELPERS -----------------
def schedule_delete(chat_id, message_id, delay_seconds=21600):
    if not message_id or str(chat_id) == ADMIN_CHAT_ID: return
    executor.submit(history_col.insert_one, {
        "chat_id": str(chat_id),
        "message_id": str(message_id),
        "delete_at": time.time() + delay_seconds
    })

def send_message(chat_id, text, auto_delete=True):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, data={"chat_id": chat_id, "text": text}, timeout=10).json()
        if resp.get("ok"):
            msg_id = str(resp["result"]["message_id"])
            if auto_delete:
                schedule_delete(chat_id, msg_id)
            return msg_id
    except:
        pass
    return None

def send_message_get_id(chat_id, text, auto_delete=True):
    return send_message(chat_id, text, auto_delete)

def send_chat_action(chat_id, action="typing"):
    """Send a chat action like 'typing'."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendChatAction"
    try:
        requests.post(url, data={"chat_id": chat_id, "action": action}, timeout=5)
    except:
        pass

def ensure_user(chat_id):
    if chat_id not in users:
        new_data = {
            "reminder": DEFAULT_REMINDER,
            "joined": str(datetime.now().date()),
            "last_active": str(datetime.now().date())
        }
        users[chat_id] = new_data
        executor.submit(users_col.insert_one, {"_id": chat_id, **new_data})
    return users[chat_id]

def set_active(chat_id):
    ensure_user(chat_id)
    today = str(datetime.now().date())
    if users[chat_id].get("last_active") != today:
        users[chat_id]["last_active"] = today
        executor.submit(users_col.update_one, {"_id": chat_id}, {"$set": {"last_active": today}})

def update_reminder(chat_id, seconds):
    ensure_user(chat_id)
    if users[chat_id].get("reminder") != seconds:
        users[chat_id]["reminder"] = seconds
        executor.submit(users_col.update_one, {"_id": chat_id}, {"$set": {"reminder": seconds}})

# ----------------- TIME FORMATTING -----------------
def format_countdown(seconds):
    """Format seconds into a readable countdown string."""
    if seconds <= 0:
        return "Starting now!"
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    mins = int((seconds % 3600) // 60)
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if mins > 0:
        parts.append(f"{mins}m")
    return " ".join(parts) if parts else "< 1m"

# ----------------- FETCH UPCOMING CONTESTS -----------------
def fetch_upcoming_contests():
    """
    Fetch upcoming contests from all platforms.
    Returns a sorted list of (platform, name, start_timestamp, time_left_seconds).
    """
    contests = []
    now_ts = datetime.now(timezone.utc).timestamp()

    # Codeforces
    try:
        url = "https://codeforces.com/api/contest.list"
        data = requests.get(url, timeout=15).json()
        for c in data.get("result", []):
            if c.get("phase") != "BEFORE":
                continue
            name = c.get("name", "Unknown")
            start = c.get("startTimeSeconds")
            if start:
                contests.append(("Codeforces", name, start, start - now_ts))
    except:
        pass

    # CodeChef
    try:
        url = "https://www.codechef.com/api/list/contests/all"
        data = requests.get(url, timeout=15).json()
        for c in data.get("future_contests", []):
            name = c.get("contest_name", "Unknown")
            start_str = c.get("contest_start_date_iso")
            if start_str:
                start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                start_ts = start_dt.timestamp()
                contests.append(("CodeChef", name, start_ts, start_ts - now_ts))
    except:
        pass

    # LeetCode
    try:
        url = "https://leetcode.com/graphql"
        query = {"query": "{ allContests { title startTime } }"}
        res = requests.post(url, json=query, timeout=15).json()
        for c in res.get("data", {}).get("allContests", []):
            name = c.get("title", "Unknown")
            start = c.get("startTime")
            if start and start > now_ts:
                contests.append(("LeetCode", name, start, start - now_ts))
    except:
        pass

    # Deduplicate by platform + contest name
    seen = set()
    unique = []
    for c in contests:
        key = (c[0], c[1])  # (platform, name)
        if key not in seen:
            seen.add(key)
            unique.append(c)

    # Sort by time left (soonest first)
    unique.sort(key=lambda x: x[3])
    return unique

# ----------------- STATS -----------------
def get_stats():
    today = str(datetime.now().date())
    total_users = len(users)
    active_today = 0

    reminder_count = {900: 0, 1800: 0, 3600: 0}

    for info in users.values():
        if info.get("last_active") == today:
            active_today += 1
        reminder = info.get("reminder", DEFAULT_REMINDER)
        if reminder in reminder_count:
            reminder_count[reminder] += 1

    most_used = max(reminder_count, key=reminder_count.get)
    return total_users, active_today, most_used

# ----------------- TELEGRAM UPDATES -----------------
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
        # Process each message concurrently
        executor.submit(process_message, update)

def broadcast_announcement(msg_to_send, chat_id):
    send_message(chat_id, f"📢 Broadcasting to {len(users)} users...")
    success_count = 0
    # Copy keys to list so it doesn't fail if users dict changes
    for u_chat_id in list(users.keys()):
        send_message(u_chat_id, f"📢 **Announcement**\n\n{msg_to_send}")
        success_count += 1
        time.sleep(0.05)  # slight delay to avoid hitting rate limits too hard
    send_message(chat_id, f"✅ Broadcast sent to {success_count} users.")

def process_message(update):
    msg = update.get("message")
    if not msg:
        return

    chat_id = str(msg["chat"]["id"])
    msg_id = msg.get("message_id")
    if msg_id:
        schedule_delete(chat_id, msg_id)

    text = msg.get("text", "").strip()

    if not text:
        return

    set_active(chat_id)

    # --- ADMIN REPLY DETECTION ---
    # If the admin replies to a forwarded message, route it back to the user
    if chat_id == ADMIN_CHAT_ID and msg.get("reply_to_message"):
        replied_msg_id = str(msg["reply_to_message"]["message_id"])
        if replied_msg_id in pending:
            entry = pending[replied_msg_id]
            original_user_id = entry["chat_id"]
            original_question = entry.get("question", "")

            # Send admin's reply to the user
            send_message(original_user_id, f"\U0001f468\u200d\U0001f4bb Admin: {text}")

            # Learn from this exchange for future auto-replies
            if original_question:
                learn_qa(original_question, text)
                send_message(ADMIN_CHAT_ID, f"\U0001f9e0 Learned! I'll auto-reply similar questions next time.")

            # Clean up
            if replied_msg_id in pending:
                del pending[replied_msg_id]
                executor.submit(pending_col.delete_one, {"_id": replied_msg_id})
            return

    # --- BOT COMMANDS ---
    if text.startswith("/announce ") and chat_id in announcers:
        msg_to_send = text[len("/announce "):].strip()
        if not msg_to_send:
            return
        
        # Run broadcast in background
        threading.Thread(target=broadcast_announcement, args=(msg_to_send, chat_id), daemon=True).start()
        return

    elif text.startswith("/add_announcer ") and chat_id == ADMIN_CHAT_ID:
        new_id = text[len("/add_announcer "):].strip()
        if new_id and new_id not in announcers:
            announcers.add(new_id)
            executor.submit(announcers_col.insert_one, {"_id": new_id})
            send_message(chat_id, f"✅ User {new_id} can now safely /announce.")

    elif text.startswith("/remove_announcer ") and chat_id == ADMIN_CHAT_ID:
        rem_id = text[len("/remove_announcer "):].strip()
        if rem_id in announcers and rem_id != ADMIN_CHAT_ID:
            announcers.remove(rem_id)
            executor.submit(announcers_col.delete_one, {"_id": rem_id})
            send_message(chat_id, f"❌ Removed {rem_id} from announcers.")
        elif rem_id == ADMIN_CHAT_ID:
            send_message(chat_id, "⚠️ You cannot remove the main admin.")
        else:
            send_message(chat_id, "⚠️ User not found in announcers list.")

    elif text == "/announcers" and chat_id == ADMIN_CHAT_ID:
        ann_list = "\n".join([f"- {a} {'(Admin)' if a == ADMIN_CHAT_ID else ''}" for a in announcers])
        send_message(chat_id, f"📢 **Authorized Announcers:**\n{ann_list}")

    elif text == "/start":
        ensure_user(chat_id)
        welcome = (
            "👋 Welcome!\n\n"
            "Commands:\n"
            "/next  → ⏱ countdown to upcoming contests\n"
            "/15  → reminder 15 minutes before\n"
            "/30  → reminder 30 minutes before\n"
            "/60  → reminder 1 hour before\n\n"
            "💬 Or just type any message and the admin will reply!"
        )
        if chat_id == ADMIN_CHAT_ID:
            welcome += (
                "\n\n🔐 Admin Commands:\n"
                "/stats → 📊 bot stats\n"
                "/announce <msg> → 📢 broadcast message\n"
                "/add_announcer <id> → add announcer\n"
                "/remove_announcer <id> → remove announcer\n"
                "/announcers → list announcers"
            )
        elif chat_id in announcers:
            welcome += "\n\n📢 Announcer Commands:\n/announce <msg> → broadcast message"
        send_message(chat_id, welcome)

    elif text == "/15":
        update_reminder(chat_id, 900)
        send_message(chat_id, "⏰ Reminder set to 15 minutes")

    elif text == "/30":
        update_reminder(chat_id, 1800)
        send_message(chat_id, "⏰ Reminder set to 30 minutes")

    elif text == "/60":
        update_reminder(chat_id, 3600)
        send_message(chat_id, "⏰ Reminder set to 1 hour")

    elif text == "/next":
        send_message(chat_id, "🔍 Fetching contests...")
        upcoming = fetch_upcoming_contests()
        if not upcoming:
            send_message(chat_id, "😕 No upcoming contests found right now.")
        else:
            # Show up to 10 upcoming contests
            lines = ["⏱ **Upcoming Contests**\n"]
            platform_emoji = {
                "Codeforces": "🟦",
                "CodeChef": "🟧",
                "LeetCode": "🟨"
            }
            for i, (platform, name, start_ts, time_left) in enumerate(upcoming[:10]):
                emoji = platform_emoji.get(platform, "🔹")
                countdown = format_countdown(time_left)
                start_dt = datetime.fromtimestamp(start_ts, tz=timezone.utc)
                date_str = start_dt.strftime("%b %d, %H:%M UTC")
                lines.append(
                    f"{emoji} {platform}\n"
                    f"   {name}\n"
                    f"   📅 {date_str}\n"
                    f"   ⏳ {countdown}\n"
                )
            send_message(chat_id, "\n".join(lines))

    elif text == "/stats":
        if chat_id != ADMIN_CHAT_ID:
            send_message(chat_id, "🔒 Stats are only available to the admin.")
        else:
            total, active, most = get_stats()
            time_map = {900: "15 min", 1800: "30 min", 3600: "1 hour"}
            send_message(
                chat_id,
                f"📊 Bot Stats\n\n"
                f"👥 Total Users: {total}\n"
                f"📅 Active Today: {active}\n"
                f"⏰ Most Used: {time_map.get(most, '30 min')}"
            )

    # --- SMART REPLY: CHECK KNOWLEDGE BASE FIRST ---
    elif not text.startswith("/") and chat_id != ADMIN_CHAT_ID:
        # Show typing indicator
        send_chat_action(chat_id, action="typing")
        
        # Try to find an answer in the knowledge base
        answer, score = find_best_match(text)

        # Add a small delay so it doesn't feel instantly automated
        time.sleep(1.5)

        if answer and score >= MATCH_THRESHOLD:
            # AI-style auto-reply from learned knowledge
            send_message(chat_id, f"\U0001f916 {answer}")
        else:
            # No good match — smart fallback
            send_message(chat_id, "Let me check this for you... \u23f3")

            # Get user's name for context
            first_name = msg.get("from", {}).get("first_name", "Unknown")
            username = msg.get("from", {}).get("username", "")
            user_label = f"{first_name} (@{username})" if username else first_name

            # Forward to admin with user info
            admin_msg_id = send_message_get_id(
                ADMIN_CHAT_ID,
                f"\U0001f4e9 Message from {user_label}\n"
                f"\U0001f194 Chat ID: {chat_id}\n\n"
                f"\U0001f4ac {text}\n\n"
                f"\u21a9\ufe0f Reply to this message to respond"
            )

            # Track the mapping + original question so we can learn
            if admin_msg_id:
                new_entry = {
                    "chat_id": chat_id,
                    "question": text,
                    "time": time.time()
                }
                pending[admin_msg_id] = new_entry
                executor.submit(pending_col.insert_one, {"_id": admin_msg_id, **new_entry})

# ----------------- ALERT HELPERS -----------------
def alert_key(platform, chat_id, contest_name):
    return f"{platform}:{chat_id}:{contest_name}"

def maybe_send(chat_id, platform, contest_name, time_left_seconds):
    key = alert_key(platform, chat_id, contest_name)
    if key in sent:
        return

    minutes_left = max(1, int(time_left_seconds // 60))
    # Send message in background so it doesn't block contest checker
    executor.submit(
        send_message,
        chat_id,
        f"🚀 {platform} Alert!\n\n"
        f"{contest_name}\n"
        f"Starts in about {minutes_left} minutes"
    )
    
    if key not in sent:
        sent.add(key)
        executor.submit(sent_col.insert_one, {"_id": key})

# ----------------- CODEFORCES -----------------
def check_codeforces():
    try:
        url = "https://codeforces.com/api/contest.list"
        data = requests.get(url, timeout=15).json()
        now = datetime.utcnow().timestamp()

        for contest in data.get("result", []):
            if contest.get("phase") != "BEFORE":
                continue

            name = contest.get("name", "Unknown contest")
            start = contest.get("startTimeSeconds")
            if not start:
                continue

            for chat_id, info in users.items():
                reminder = int(info.get("reminder", DEFAULT_REMINDER))
                time_left = start - now

                if 0 < time_left <= reminder:
                    maybe_send(chat_id, "Codeforces", name, time_left)
    except:
        pass

# ----------------- CODECHEF -----------------
def check_codechef():
    """
    Best-effort version.
    If CodeChef changes its page/API structure, this function may need updates.
    """
    try:
        url = "https://www.codechef.com/api/list/contests/all"
        data = requests.get(url, timeout=15).json()
        now = datetime.now(timezone.utc)

        contests = data.get("future_contests", [])
        for contest in contests:
            name = contest.get("contest_name", "Unknown contest")
            start_str = contest.get("contest_start_date_iso")
            if not start_str:
                continue

            start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            time_left = (start - now).total_seconds()

            for chat_id, info in users.items():
                reminder = int(info.get("reminder", DEFAULT_REMINDER))
                if 0 < time_left <= reminder:
                    maybe_send(chat_id, "CodeChef", name, time_left)
    except:
        pass

# ----------------- LEETCODE -----------------
def check_leetcode():
    """
    Best-effort version.
    LeetCode's public contest data can change, so this may need updates later.
    """
    try:
        url = "https://leetcode.com/graphql"
        query = {
            "query": """
            {
              allContests {
                title
                startTime
              }
            }
            """
        }

        res = requests.post(url, json=query, timeout=15).json()
        contests = res.get("data", {}).get("allContests", [])
        now = datetime.utcnow().timestamp()

        for contest in contests:
            name = contest.get("title", "Unknown contest")
            start = contest.get("startTime")
            if start is None:
                continue

            for chat_id, info in users.items():
                reminder = int(info.get("reminder", DEFAULT_REMINDER))
                time_left = start - now

                if 0 < time_left <= reminder:
                    maybe_send(chat_id, "LeetCode", name, time_left)
    except:
        pass

# ----------------- CLEANUP OLD PENDING -----------------
def cleanup_pending():
    """Remove pending messages older than 24 hours."""
    now = time.time()
    one_day = 86400  # 24 hours in seconds
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

# ----------------- MAIN LOOP -----------------
def main():
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