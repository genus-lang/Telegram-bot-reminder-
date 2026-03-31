from datetime import datetime, timezone, timedelta
from src.database import users, sent, sent_col, timetable_col
from src.config import executor
from src.telegram import send_message
from src.utils import escape_html
timetable_cache = {}

def check_lectures():
    try:
        global timetable_cache
        ist_tz = timezone(timedelta(hours=5, minutes=30))
        now = datetime.now(ist_tz)
        day_name = now.strftime("%A")
        
        for chat_id, info in users.items():
            branch = info.get("college_branch")
            year = info.get("college_year")
            group = info.get("college_group")
            reminder_seconds = info.get("college_reminder")
            
            if not branch or year is None or group is None or not reminder_seconds:
                continue
            if reminder_seconds <= 0:
                continue
                
            try:
                doc_id = f"{branch}_Year{year}"
                
                # Fetch entirely from safe RAM lookup mapping
                if doc_id not in timetable_cache:
                    doc = timetable_col.find_one({"_id": doc_id})
                    timetable_cache[doc_id] = doc if doc else {}
                    
                cached_doc = timetable_cache[doc_id]
                if not cached_doc: continue
                
                # Extract strict nested target string routes manually
                schedule = cached_doc.get("groups", {}).get(str(group), {}).get(day_name, [])
            except Exception:
                continue
                
            for lecture in schedule:
                start_str = lecture["start"]
                h, m = map(int, start_str.split(":"))
                lec_time = now.replace(hour=h, minute=m, second=0, microsecond=0)
                time_left_seconds = (lec_time - now).total_seconds()
                
                if 0 < time_left_seconds <= reminder_seconds:
                    alert_key = f"lec_{chat_id}_{now.date()}_{start_str}"
                    if alert_key not in sent:
                        sent.add(alert_key)
                        executor.submit(sent_col.insert_one, {"_id": alert_key})
                        
                        sub = escape_html(lecture['subject'])
                        room = escape_html(lecture['room'])
                        prof = escape_html(lecture['faculty'])
                        mins = int(time_left_seconds // 60)
                        
                        msg = (
                            f"🏫 <b>Class Alert!</b>\n\n"
                            f"📚 <b>Subject:</b> {sub}\n"
                            f"📍 <b>Room:</b> {room}\n"
                            f"👨‍🏫 <b>Faculty:</b> {prof}\n\n"
                            f"⏳ Starts in about <b>{mins if mins > 0 else 1} minutes</b>!"
                        )
                        
                        safe_cb_sub = lecture['subject'][:40]
                        markup = {
                            "inline_keyboard": [
                                [
                                    {"text": "✅ Attending", "callback_data": f"att_y_{safe_cb_sub}"},
                                    {"text": "❌ Bunking", "callback_data": f"att_n_{safe_cb_sub}"}
                                ]
                            ]
                        }
                        executor.submit(send_message, chat_id, msg, reply_markup=markup)
    except:
        pass
