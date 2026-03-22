import time
import threading
from datetime import datetime, timezone
from src.config import ADMIN_CHAT_ID, MATCH_THRESHOLD, DEFAULT_REMINDER, executor
from src.database import (
    users, users_col, pending, pending_col,
    knowledge, knowledge_col, announcers, announcers_col
)
from src.telegram import send_message, send_chat_action, schedule_delete
from src.utils import extract_keywords, format_countdown
from src.scrapers import fetch_upcoming_contests

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

def learn_qa(question, answer):
    keywords = extract_keywords(question)
    if len(keywords) < 1: return
    new_qa = {"question": question, "answer": answer, "keywords": keywords}
    knowledge.append(new_qa)
    executor.submit(knowledge_col.insert_one, new_qa.copy())

def get_stats():
    today = str(datetime.now().date())
    total_users = len(users)
    active_today = 0
    reminder_count = {900: 0, 1800: 0, 3600: 0}
    for info in users.values():
        if info.get("last_active") == today: active_today += 1
        reminder = info.get("reminder", DEFAULT_REMINDER)
        if reminder in reminder_count: reminder_count[reminder] += 1
    most_used = max(reminder_count, key=reminder_count.get)
    return total_users, active_today, most_used

def find_best_match(user_text):
    user_keywords = set(extract_keywords(user_text))
    if not user_keywords: return None, 0
    best_answer = None
    best_score = 0
    for entry in knowledge:
        stored_keywords = set(entry.get("keywords", []))
        if not stored_keywords: continue
        common = user_keywords & stored_keywords
        total = user_keywords | stored_keywords
        score = len(common) / len(total) if total else 0
        if score > best_score:
            best_score = score
            best_answer = entry["answer"]
    return best_answer, best_score

def broadcast_announcement(msg_to_send, chat_id):
    send_message(chat_id, f"📢 Broadcasting to {len(users)} users...")
    success_count = 0
    for u_chat_id in list(users.keys()):
        send_message(u_chat_id, f"📢 **Announcement**\n\n{msg_to_send}")
        success_count += 1
        time.sleep(0.05)
    send_message(chat_id, f"✅ Broadcast sent to {success_count} users.")

def process_message(update):
    msg = update.get("message")
    if not msg: return
    chat_id = str(msg["chat"]["id"])
    msg_id = msg.get("message_id")
    if msg_id: schedule_delete(chat_id, msg_id)
    text = msg.get("text", "").strip()
    if not text: return
    set_active(chat_id)

    if chat_id == ADMIN_CHAT_ID and msg.get("reply_to_message"):
        replied_msg_id = str(msg["reply_to_message"]["message_id"])
        if replied_msg_id in pending:
            entry = pending[replied_msg_id]
            original_user_id = entry["chat_id"]
            original_question = entry.get("question", "")
            send_message(original_user_id, f"\U0001f468\u200d\U0001f4bb Admin: {text}")
            if original_question:
                learn_qa(original_question, text)
                send_message(ADMIN_CHAT_ID, f"\U0001f9e0 Learned! I'll auto-reply similar questions next time.")
            del pending[replied_msg_id]
            executor.submit(pending_col.delete_one, {"_id": replied_msg_id})
            return

    if text.startswith("/announce ") and chat_id in announcers:
        msg_to_send = text[len("/announce "):].strip()
        if not msg_to_send: return
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
            "👋 Welcome!\n\nCommands:\n/next  → ⏱ countdown to upcoming contests\n"
            "/15  → reminder 15 minutes before\n/30  → reminder 30 minutes before\n"
            "/60  → reminder 1 hour before\n\n💬 Or just type any message and the admin will reply!"
        )
        if chat_id == ADMIN_CHAT_ID:
            welcome += "\n\n🔐 Admin Commands:\n/stats → 📊 bot stats\n/announce <msg> → 📢 broadcast message\n/add_announcer <id> → add announcer\n/remove_announcer <id> → remove announcer\n/announcers → list announcers"
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
            lines = ["⏱ **Upcoming Contests**\n"]
            platform_emoji = {"Codeforces": "🟦", "CodeChef": "🟧", "LeetCode": "🟨"}
            for i, (platform, name, start_ts, time_left) in enumerate(upcoming[:10]):
                emoji = platform_emoji.get(platform, "🔹")
                countdown = format_countdown(time_left)
                start_dt = datetime.fromtimestamp(start_ts, tz=timezone.utc)
                date_str = start_dt.strftime("%b %d, %H:%M UTC")
                lines.append(f"{emoji} {platform}\n   {name}\n   📅 {date_str}\n   ⏳ {countdown}\n")
            send_message(chat_id, "\n".join(lines))

    elif text == "/stats":
        if chat_id != ADMIN_CHAT_ID:
            send_message(chat_id, "🔒 Stats are only available to the admin.")
        else:
            total, active, most = get_stats()
            time_map = {900: "15 min", 1800: "30 min", 3600: "1 hour"}
            send_message(chat_id, f"📊 Bot Stats\n\n👥 Total Users: {total}\n📅 Active Today: {active}\n⏰ Most Used: {time_map.get(most, '30 min')}")

    elif not text.startswith("/") and chat_id != ADMIN_CHAT_ID:
        send_chat_action(chat_id, action="typing")
        answer, score = find_best_match(text)
        time.sleep(1.5)
        if answer and score >= MATCH_THRESHOLD:
            send_message(chat_id, f"\U0001f916 {answer}")
        else:
            send_message(chat_id, "Let me check this for you... \u23f3")
            first_name = msg.get("from", {}).get("first_name", "Unknown")
            username = msg.get("from", {}).get("username", "")
            user_label = f"{first_name} (@{username})" if username else first_name
            admin_msg_id = send_message(
                ADMIN_CHAT_ID,
                f"\U0001f4e9 Message from {user_label}\n\U0001f194 Chat ID: {chat_id}\n\n\U0001f4ac {text}\n\n\u21a9\ufe0f Reply to this message to respond",
                auto_delete=False # Don't auto delete admin inbox
            )
            if admin_msg_id:
                new_entry = {"chat_id": chat_id, "question": text, "time": time.time()}
                pending[admin_msg_id] = new_entry
                executor.submit(pending_col.insert_one, {"_id": admin_msg_id, **new_entry})
