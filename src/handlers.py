import time
import threading
from datetime import datetime, timezone, timedelta
from src.config import ADMIN_CHAT_ID, MATCH_THRESHOLD, DEFAULT_REMINDER, executor
from src.database import (
    users, users_col, pending, pending_col,
    knowledge, knowledge_col, announcers, announcers_col, timetable_col
)
from src.telegram import send_message, send_chat_action, schedule_delete
from src.utils import extract_keywords, format_countdown, escape_html
from src.scrapers import fetch_upcoming_contests, fetch_daily_challenge

def get_main_menu():
    return {
        "keyboard": [[{"text": "🏆 Contests"}, {"text": "🎓 Colleges"}]],
        "resize_keyboard": True
    }

def get_admin_menu():
    return {
        "keyboard": [
            [{"text": "📊 Stats"}, {"text": "📢 Broadcast"}],
            [{"text": "👥 Announcers"}, {"text": "🔍 Pending Questions"}],
            [{"text": "🏆 Contests"}, {"text": "🎓 Colleges"}]
        ],
        "resize_keyboard": True
    }

def get_announcer_menu():
    return {
        "keyboard": [
            [{"text": "📢 Announce"}],
            [{"text": "🏆 Contests"}, {"text": "🎓 Colleges"}]
        ],
        "resize_keyboard": True
    }

def get_contest_menu():
    return {
        "keyboard": [
            [{"text": "⏰ 15 Min"}, {"text": "⏰ 30 Min"}, {"text": "⏰ 60 Min"}],
            [{"text": "📅 Upcoming Contests"}, {"text": "💡 Daily Challenge"}],
            [{"text": "🔕 Turn Off Contest Alerts"}],
            [{"text": "🔙 Back to Main Menu"}]
        ],
        "resize_keyboard": True
    }

def get_college_menu():
    return {
        "keyboard": [
            [{"text": "🏫 CSE"}, {"text": "⚙️ MAE"}],
            [{"text": "📡 ECE"}, {"text": "🧮 MNC"}],
            [{"text": "🔙 Back to Main Menu"}]
        ],
        "resize_keyboard": True
    }

def get_year_menu():
    return {
        "keyboard": [
            [{"text": "🎓 Year 1"}, {"text": "🎓 Year 2"}],
            [{"text": "🎓 Year 3"}, {"text": "🎓 Year 4"}],
            [{"text": "🔙 Back to Colleges"}]
        ],
        "resize_keyboard": True
    }

def get_group_menu():
    return {
        "keyboard": [
            [{"text": "👥 Group 1"}, {"text": "👥 Group 2"}],
            [{"text": "🔙 Back to Colleges"}]
        ],
        "resize_keyboard": True
    }

def get_lecture_reminder_menu():
    return {
        "keyboard": [
            [{"text": "🔔 5 Min Before"}, {"text": "🔔 15 Min Before"}],
            [{"text": "🔔 30 Min Before"}, {"text": "🔕 Turn Off Reminders"}],
            [{"text": "🔙 Back to Colleges"}]
        ],
        "resize_keyboard": True
    }

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

def update_user_field(chat_id, field, value):
    ensure_user(chat_id)
    if users[chat_id].get(field) != value:
        users[chat_id][field] = value
        executor.submit(users_col.update_one, {"_id": chat_id}, {"$set": {field: value}})

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

# Track announcers waiting to send a message
_announcer_pending = set()

def process_message(update):
    msg = update.get("message")
    if not msg: return
    chat_id = str(msg["chat"]["id"])
    msg_id = msg.get("message_id")
    if msg_id: schedule_delete(chat_id, msg_id)
    text = msg.get("text", "").strip()
    if not text: return
    set_active(chat_id)

    # --- Convert Natural Language to Commands ---
    text_lower = text.lower()
    if text_lower in ["cancel", "stop", "abort"]: text = "/cancel"
    elif text_lower in ["announcers", "announcers list"]: text = "/announcers"
    elif text_lower in ["start", "hello", "hi", "hey"]: text = "/start"
    elif text_lower in ["stats", "statistics"]: text = "/stats"
    elif text_lower in ["next", "upcoming", "upcoming contests"]: text = "/next"
    elif text_lower in ["15", "15 min", "15 mins", "15 minutes"]: text = "/15"
    elif text_lower in ["30", "30 min", "30 mins", "30 minutes"]: text = "/30"
    elif text_lower in ["60", "60 min", "60 mins", "60 minutes", "1 hour"]: text = "/60"
    elif text_lower.startswith("announce "): text = "/announce " + text[9:]
    elif text_lower.startswith("add announcer "): text = "/add_announcer " + text[14:]
    elif text_lower.startswith("remove announcer "): text = "/remove_announcer " + text[17:]

    # Handle announcers who clicked the 📢 Announce button and are now typing their message
    if chat_id in _announcer_pending and not (text.startswith("/") or text_lower == "cancel"):
        _announcer_pending.discard(chat_id)
        if not text:
            send_message(chat_id, "⚠️ <i>Empty message — announcement cancelled.</i>", reply_markup=get_announcer_menu())
            return
        threading.Thread(target=broadcast_announcement, args=(text, chat_id), daemon=True).start()
        return

    # UX Menu Overrides - Safe Substring Matching
    if "Daily Challenge" in text:
        send_message(chat_id, "💡 <i>Fetching today's coding challenge...</i>")
        challenge = fetch_daily_challenge()
        if challenge:
            diff = challenge['difficulty']
            diff_emoji = {"Easy": "🟢", "Medium": "🟡", "Hard": "🔴"}.get(diff, "⚪")
            tags_str = ", ".join(challenge['tags'][:5]) if challenge['tags'] else "—"
            msg = (
                f"💡 <b>Daily Coding Challenge</b>\n\n"
                f"🆔 <b>#{challenge['id']}</b> | {diff_emoji} <b>{diff}</b>\n"
                f"📝 <b>{escape_html(challenge['title'])}</b>\n\n"
                f"✅ <b>Acceptance:</b> {challenge['acceptance']}%\n"
                f"🏷️ <b>Tags:</b> <i>{escape_html(tags_str)}</i>\n\n"
                f"🔗 <a href=\"{challenge['url']}\">Solve on LeetCode</a>"
            )
            send_message(chat_id, msg)
        else:
            send_message(chat_id, "❌ <i>Could not fetch today's challenge. Try again later!</i>")
        return
    elif "Upcoming Contests" in text:
        text = "/next"
    elif "Contests Menu" in text:
        return
    elif "Contests" in text:
        send_message(chat_id, "🏆 <b>Contests Menu</b>\nSelect an option below:", reply_markup=get_contest_menu())
        return
    elif "Colleges Menu" in text:
        return
    elif "Colleges" in text and "Back" not in text:
        send_message(chat_id, "🎓 <b>Colleges Menu</b>\nSelect your branch:", reply_markup=get_college_menu())
        return
    elif "Main Menu" in text:
        menu = get_admin_menu() if chat_id == ADMIN_CHAT_ID else get_main_menu()
        send_message(chat_id, "🏠 <b>Main Menu</b>\nChoose a category:", reply_markup=menu)
        return
    elif "Back to Colleges" in text:
        send_message(chat_id, "🎓 <b>Colleges Menu</b>\nSelect your branch:", reply_markup=get_college_menu())
        return
        
    elif any(b in text for b in ["CSE", "MAE", "ECE", "MNC"]):
        branch = next(b for b in ["CSE", "MAE", "ECE", "MNC"] if b in text)
        update_user_field(chat_id, "college_branch", branch)
        send_message(chat_id, f"✅ <b>Branch set to {branch}!</b>\n\nNow select your Year:", reply_markup=get_year_menu())
        return
        
    elif any(y in text for y in ["Year 1", "Year 2", "Year 3", "Year 4"]):
        year = next(y.split(" ")[1] for y in ["Year 1", "Year 2", "Year 3", "Year 4"] if y in text)
        update_user_field(chat_id, "college_year", int(year))
        branch = users[chat_id].get("college_branch", "")
        doc_id = f"{branch}_Year{year}"
        doc = timetable_col.find_one({"_id": doc_id})
        has_groups = doc.get("has_groups", True) if doc else True
        if has_groups:
            send_message(chat_id, f"✅ <b>Year {year} selected!</b>\n\nNow select your Group:", reply_markup=get_group_menu())
        else:
            update_user_field(chat_id, "college_group", 0)
            send_message(chat_id, f"✅ <b>Year {year} selected!</b>\n\nWhen should I remind you about your scheduled lectures?", reply_markup=get_lecture_reminder_menu())
        return
        
    elif any(g in text for g in ["Group 1", "Group 2"]):
        group = next(g.split(" ")[1] for g in ["Group 1", "Group 2"] if g in text)
        update_user_field(chat_id, "college_group", int(group))
        send_message(chat_id, f"✅ <b>Group {group} selected!</b>\n\nWhen should I remind you about your scheduled lectures?", reply_markup=get_lecture_reminder_menu())
        return
        
    elif "Before" in text and any(m in text for m in ["15 Min", "30 Min", "5 Min"]):
        minutes = int(next(m.split(" ")[0] for m in ["15 Min", "30 Min", "5 Min"] if m in text))
        update_user_field(chat_id, "college_reminder", minutes * 60)
        send_message(chat_id, f"🎉 <b>Setup Complete!</b>\n\nI will remind you exactly <b>{minutes} minutes</b> before your scheduled {users[chat_id].get('college_branch', 'College')} lectures begin!", reply_markup=get_main_menu())
        return

    elif "Turn Off Reminders" in text:
        update_user_field(chat_id, "college_reminder", 0)
        send_message(chat_id, "🔕 <b>College Reminders Disabled!</b>\n\nYou will no longer receive notifications for lectures. Contest alerts remain active.\n\n<i>To re-enable, go to Colleges and set up again.</i>", reply_markup=get_main_menu() if chat_id != ADMIN_CHAT_ID else get_admin_menu())
        return

    elif "Turn Off Contest" in text:
        update_reminder(chat_id, 0)
        send_message(chat_id, "🔕 <b>Contest Alerts Disabled!</b>\n\nYou will no longer receive contest reminders. College lecture alerts remain active.\n\n<i>To re-enable, go to Contests and pick a time.</i>", reply_markup=get_main_menu() if chat_id != ADMIN_CHAT_ID else get_admin_menu())
        return
        
    elif "15 Min" in text: text = "/15"
    elif "30 Min" in text: text = "/30"
    elif "60 Min" in text: text = "/60"

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

    elif text == "📢 Announce" and chat_id in announcers:
        _announcer_pending.add(chat_id)
        send_message(chat_id,
            "📢 <b>Announce to All Users</b>\n\n"
            "Type your announcement message below and send it.\n"
            "<i>It will be broadcast to all bot users.</i>\n\n"
            "Send <b>Cancel</b> to abort.",
            reply_markup={"keyboard": [[{"text": "Cancel"}]], "resize_keyboard": True}
        )
        return

    elif text == "/cancel" and chat_id in _announcer_pending:
        _announcer_pending.discard(chat_id)
        send_message(chat_id, "❌ <i>Announcement cancelled.</i>", reply_markup=get_announcer_menu())
        return

    elif text.startswith("/add_announcer ") and chat_id == ADMIN_CHAT_ID:
        new_id = text[len("/add_announcer "):].strip()
        if new_id and new_id not in announcers:
            announcers.add(new_id)
            executor.submit(announcers_col.insert_one, {"_id": new_id})
            send_message(chat_id, f"✅ User <code>{new_id}</code> added as an announcer.")
            # Notify the new announcer with their menu
            send_message(new_id,
                "📢 <b>You've been granted Announcer access!</b>\n\n"
                "You can now broadcast messages to all bot users.\n"
                "Tap <b>📢 Announce</b> below to get started.",
                reply_markup=get_announcer_menu()
            )

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
        if chat_id == ADMIN_CHAT_ID:
            welcome = (
                "🔧 <b>Admin Control Panel</b>\n\n"
                "Use the buttons below to manage the bot, view stats, or broadcast messages."
            )
            send_message(chat_id, welcome, reply_markup=get_admin_menu())
        elif chat_id in announcers:
            welcome = (
                "📢 <b>Announcer Panel</b>\n\n"
                "You have announcer privileges. Use <b>📢 Announce</b> to broadcast a message to all users."
            )
            send_message(chat_id, welcome, reply_markup=get_announcer_menu())
        else:
            welcome = (
                "<b>👋 Welcome to the Bot Assistant!</b>\n\n"
                "Use the buttons below to setup push notifications, view live contests, or explore Colleges!"
            )
            send_message(chat_id, welcome, reply_markup=get_main_menu())

    elif "Stats" in text and chat_id == ADMIN_CHAT_ID:
        total, active, most = get_stats()
        time_map = {900: "15 min", 1800: "30 min", 3600: "1 hour", 0: "Off"}
        # Count college reminder users
        college_users = sum(1 for u in users.values() if u.get("college_reminder", 0) > 0)
        contest_users = sum(1 for u in users.values() if u.get("reminder", 0) > 0)
        send_message(chat_id, 
            f"📊 <b>Bot Statistics</b>\n\n"
            f"👥 <b>Total Users:</b> <code>{total}</code>\n"
            f"🔥 <b>Active Today:</b> <code>{active}</code>\n"
            f"⏰ <b>Most Used Reminder:</b> <code>{time_map.get(most, '30 min')}</code>\n\n"
            f"<b>🏆 Contest Alerts Active:</b> <code>{contest_users}</code>\n"
            f"<b>🎓 College Alerts Active:</b> <code>{college_users}</code>")
        return

    elif "Broadcast" in text and chat_id == ADMIN_CHAT_ID:
        send_message(chat_id, "📢 <b>Broadcast Mode</b>\n\nType your message as:\n<code>announce Your message here</code>\n\nThis will be sent to all users.", reply_markup=get_admin_menu())
        return

    elif "Announcers" in text and chat_id == ADMIN_CHAT_ID:
        ann_list = "\n".join([f"🔸 <code>{a}</code> {'<i>(Admin)</i>' if a == ADMIN_CHAT_ID else ''}" for a in announcers])
        send_message(chat_id, 
            f"📢 <b>Authorized Announcers:</b>\n{ann_list}\n\n"
            f"<b>Commands:</b>\n"
            f"<code>add announcer CHAT_ID</code>\n"
            f"<code>remove announcer CHAT_ID</code>", reply_markup=get_admin_menu())
        return

    elif "Pending" in text and chat_id == ADMIN_CHAT_ID:
        if not pending:
            send_message(chat_id, "✅ <b>No pending questions!</b>\n\nAll user questions have been answered.", reply_markup=get_admin_menu())
        else:
            lines = [f"📥 <b>Pending Questions ({len(pending)})</b>\n"]
            for msg_id, entry in list(pending.items())[:10]:
                q = escape_html(entry.get('question', '?')[:50])
                lines.append(f"💬 <i>\"{q}\"</i>\n   from <code>{entry.get('chat_id', '?')}</code>")
            send_message(chat_id, "\n".join(lines), reply_markup=get_admin_menu())
        return

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
        upcoming = [c for c in upcoming if c[3] <= 14 * 24 * 3600]
        if not upcoming:
            send_message(chat_id, "😕 <i>No upcoming contests found in the next 2 weeks.</i>")
        else:
            lines = ["⏱ <b>Upcoming Contests</b>\n"]
            platform_emoji = {"Codeforces": "🟦", "CodeChef": "🟧", "LeetCode": "🟨"}
            for i, (platform, name, start_ts, time_left, is_rated) in enumerate(upcoming[:10]):
                emoji = platform_emoji.get(platform, "🔹")
                countdown = format_countdown(time_left)
                ist_tz = timezone(timedelta(hours=5, minutes=30))
                start_dt = datetime.fromtimestamp(start_ts, tz=ist_tz)
                date_str = start_dt.strftime("%b %d, %I:%M %p IST")
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
