import time
import threading
from datetime import datetime, timezone
from src.config import ADMIN_CHAT_ID, MATCH_THRESHOLD, DEFAULT_REMINDER, executor
from src.database import (
    users, users_col, pending, pending_col,
    knowledge, knowledge_col, announcers, announcers_col
)
from src.telegram import send_message, send_chat_action, schedule_delete
from src.utils import extract_keywords, format_countdown, escape_html
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
        score = len(common) / len(stored_keywords) if stored_keywords else 0
        if score > best_score:
            best_score = score
            best_answer = entry["answer"]
    return best_answer, best_score

def broadcast_announcement(msg_to_send, chat_id):
    send_message(chat_id, f"📢 <i>Broadcasting to <code>{len(users)}</code> users...</i>")
    success_count = 0
    safe_msg = escape_html(msg_to_send)
    for u_chat_id in list(users.keys()):
        send_message(u_chat_id, f"📢 <b>Announcement</b>\n\n{safe_msg}")
        success_count += 1
        time.sleep(0.05)
    send_message(chat_id, f"✅ <b>Broadcast complete:</b> Sent to <code>{success_count}</code> users.")

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
            safe_text = escape_html(text)
            send_message(original_user_id, f"👨‍💻 <b>Admin Answered:</b>\n\n<i>\"{safe_text}\"</i>")
            if original_question:
                learn_qa(original_question, text)
                send_message(ADMIN_CHAT_ID, f"🧠 <b>Learned!</b> I'll auto-reply to similar questions next time.")
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
            send_message(chat_id, f"✅ User <code>{new_id}</code> can now safely /announce.")

    elif text.startswith("/remove_announcer ") and chat_id == ADMIN_CHAT_ID:
        rem_id = text[len("/remove_announcer "):].strip()
        if rem_id in announcers and rem_id != ADMIN_CHAT_ID:
            announcers.remove(rem_id)
            executor.submit(announcers_col.delete_one, {"_id": rem_id})
            send_message(chat_id, f"❌ Removed <code>{rem_id}</code> from announcers.")
        elif rem_id == ADMIN_CHAT_ID:
            send_message(chat_id, "⚠️ <i>You cannot remove the main admin.</i>")
        else:
            send_message(chat_id, "⚠️ <i>User not found in announcers list.</i>")

    elif text == "/announcers" and chat_id == ADMIN_CHAT_ID:
        ann_list = "\n".join([f"🔸 <code>{a}</code> {'<i>(Admin)</i>' if a == ADMIN_CHAT_ID else ''}" for a in announcers])
        send_message(chat_id, f"📢 <b>Authorized Announcers:</b>\n{ann_list}")

    elif text == "/start":
        ensure_user(chat_id)
        welcome = (
            "<b>👋 Welcome to the Contest Alert & AI Assistant!</b>\n\n"
            "<b>🔔 Reminders:</b>\n"
            "/15  → Alert 15 mins before\n"
            "/30  → Alert 30 mins before\n"
            "/60  → Alert 1 hour before\n\n"
            "<b>🗓 Live Data:</b>\n"
            "/next  → View upcoming contests\n\n"
            "💬 <i>Or just type any question, and I'll find the answer!</i>"
        )
        if chat_id == ADMIN_CHAT_ID:
            welcome += "\n\n<b>🔐 Admin Commands:</b>\n/stats → Bot stats\n/announce &lt;msg&gt; → Broadcast\n/add_announcer &lt;id&gt; → Add mod\n/remove_announcer &lt;id&gt; → Remove mod\n/announcers → List mods"
        elif chat_id in announcers:
            welcome += "\n\n<b>📢 Announcer Commands:</b>\n/announce &lt;msg&gt; → Broadcast message"
        send_message(chat_id, welcome)

    elif text == "/15":
        update_reminder(chat_id, 900)
        send_message(chat_id, "⏰ Reminder set to <b>15 minutes</b>")

    elif text == "/30":
        update_reminder(chat_id, 1800)
        send_message(chat_id, "⏰ Reminder set to <b>30 minutes</b>")

    elif text == "/60":
        update_reminder(chat_id, 3600)
        send_message(chat_id, "⏰ Reminder set to <b>1 hour</b>")

    elif text == "/next":
        send_message(chat_id, "🔍 <i>Fetching contests...</i>")
        upcoming = fetch_upcoming_contests()
        if not upcoming:
            send_message(chat_id, "😕 <i>No upcoming contests found right now.</i>")
        else:
            lines = ["⏱ <b>Upcoming Contests</b>\n"]
            platform_emoji = {"Codeforces": "🟦", "CodeChef": "🟧", "LeetCode": "🟨"}
            for i, (platform, name, start_ts, time_left, is_rated) in enumerate(upcoming[:10]):
                emoji = platform_emoji.get(platform, "🔹")
                countdown = format_countdown(time_left)
                start_dt = datetime.fromtimestamp(start_ts, tz=timezone.utc)
                date_str = start_dt.strftime("%b %d, %H:%M UTC")
                safe_name = escape_html(name)
                rating_tag = "⭐ <b>[Rated]</b>" if is_rated else "⚪ <i>[Unrated]</i>"
                lines.append(f"{emoji} <b>{platform}</b> {rating_tag}\n   <code>{safe_name}</code>\n   📅 <i>{date_str}</i>\n   ⏳ <b>{countdown}</b>\n")
            send_message(chat_id, "\n".join(lines))

    elif text == "/stats":
        if chat_id != ADMIN_CHAT_ID:
            send_message(chat_id, "🔒 <i>Stats are only available to the admin.</i>")
        else:
            total, active, most = get_stats()
            time_map = {900: "15 min", 1800: "30 min", 3600: "1 hour"}
            send_message(chat_id, f"📊 <b>Bot Statistics</b>\n\n👥 <b>Total Users:</b> <code>{total}</code>\n🔥 <b>Active Today:</b> <code>{active}</code>\n⏰ <b>Most Used Reminder:</b> <code>{time_map.get(most, '30 min')}</code>")

    elif not text.startswith("/") and chat_id != ADMIN_CHAT_ID:
        send_chat_action(chat_id, action="typing")
        answer, score = find_best_match(text)
        if answer and score >= MATCH_THRESHOLD:
            safe_ans = escape_html(answer)
            send_message(chat_id, f"\U0001f916 <i>{safe_ans}</i>")
        else:
            send_message(chat_id, "<i>Let me check this for you...</i> \u23f3")
            first_name = msg.get("from", {}).get("first_name", "Unknown")
            username = msg.get("from", {}).get("username", "")
            user_label = escape_html(f"{first_name} (@{username})" if username else first_name)
            safe_text = escape_html(text)
            
            admin_msg_id = send_message(
                ADMIN_CHAT_ID,
                f"📥 <b>Incoming Question</b>\n\n👤 <b>User:</b> {user_label}\n🆔 <b>Chat ID:</b> <code>{chat_id}</code>\n\n💬 <i>\"{safe_text}\"</i>\n\n↩️ <i>Reply to this message to automatically send an answer back!</i>",
                auto_delete=False # Don't auto delete admin inbox
            )
            if admin_msg_id:
                new_entry = {"chat_id": chat_id, "question": text, "time": time.time()}
                pending[admin_msg_id] = new_entry
                executor.submit(pending_col.insert_one, {"_id": admin_msg_id, **new_entry})
