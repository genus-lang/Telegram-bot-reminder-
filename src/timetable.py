from datetime import datetime, timezone, timedelta
from src.database import users, sent, sent_col
from src.config import executor
from src.telegram import send_message
from src.utils import escape_html

TIMETABLE = {
    "CSE": {
        3: {
            1: {
                "Monday": [
                    {"start": "09:00", "end": "10:00", "subject": "CS304 (Compiler)", "faculty": "—", "room": "C101"},
                    {"start": "10:00", "end": "11:00", "subject": "Data Mining", "faculty": "—", "room": "—"},
                    {"start": "11:00", "end": "12:00", "subject": "CS304", "faculty": "—", "room": "C201"},
                    {"start": "12:00", "end": "13:00", "subject": "ME306 (EVS)", "faculty": "—", "room": "C101"},
                    {"start": "16:00", "end": "18:00", "subject": "CS313 (Networks Lab)", "faculty": "SKR", "room": "CC Floor"}
                ],
                "Tuesday": [
                    {"start": "11:00", "end": "12:00", "subject": "CS305 (CN)", "faculty": "SKR", "room": "C101"},
                    {"start": "12:00", "end": "13:00", "subject": "ME306", "faculty": "VJK", "room": "C101"},
                    {"start": "15:00", "end": "16:00", "subject": "CS304", "faculty": "—", "room": "C101"}
                ],
                "Wednesday": [
                    {"start": "10:00", "end": "11:00", "subject": "CS305", "faculty": "SKR", "room": "C101"},
                    {"start": "11:00", "end": "12:00", "subject": "CS351 (Crypto)", "faculty": "HN", "room": "C201"},
                    {"start": "12:00", "end": "13:00", "subject": "CS306 (Graphics)", "faculty": "—", "room": "C101"},
                    {"start": "13:00", "end": "14:00", "subject": "CS305", "faculty": "SKR", "room": "C201"},
                    {"start": "15:00", "end": "16:00", "subject": "CS304", "faculty": "—", "room": "C101"}
                ],
                "Thursday": [
                    {"start": "10:00", "end": "11:00", "subject": "CS351", "faculty": "HN", "room": "C201"},
                    {"start": "11:00", "end": "12:00", "subject": "CS306", "faculty": "—", "room": "C101"},
                    {"start": "12:00", "end": "13:00", "subject": "CS306", "faculty": "—", "room": "C101"},
                    {"start": "13:00", "end": "14:00", "subject": "Data Mining", "faculty": "—", "room": "—"},
                    {"start": "16:00", "end": "18:00", "subject": "CS314 (ML Lab)", "faculty": "TM", "room": "CC Floor"}
                ],
                "Friday": [
                    {"start": "09:00", "end": "10:00", "subject": "CS307 (ML)", "faculty": "—", "room": "—"},
                    {"start": "10:00", "end": "11:00", "subject": "CS306", "faculty": "—", "room": "C101"},
                    {"start": "11:00", "end": "12:00", "subject": "CS304", "faculty": "—", "room": "C101"},
                    {"start": "15:00", "end": "16:00", "subject": "CS305", "faculty": "SKR", "room": "C101"}
                ]
            },
            2: {
                "Monday": [
                    {"start": "09:00", "end": "10:00", "subject": "CS307 (ML)", "faculty": "—", "room": "—"},
                    {"start": "10:00", "end": "11:00", "subject": "CS351", "faculty": "HN", "room": "C201"},
                    {"start": "11:00", "end": "12:00", "subject": "CS304", "faculty": "—", "room": "C201"},
                    {"start": "12:00", "end": "13:00", "subject": "ME306", "faculty": "VJK", "room": "C201"},
                    {"start": "16:00", "end": "18:00", "subject": "CS313 Lab", "faculty": "SKR", "room": "CC Floor"}
                ],
                "Tuesday": [
                    {"start": "11:00", "end": "12:00", "subject": "CS307 (ML)", "faculty": "—", "room": "—"},
                    {"start": "12:00", "end": "13:00", "subject": "ME306", "faculty": "VJK", "room": "C201"},
                    {"start": "13:00", "end": "14:00", "subject": "CS305", "faculty": "SKR", "room": "C201"},
                    {"start": "17:00", "end": "18:00", "subject": "CS306", "faculty": "—", "room": "—"}
                ],
                "Wednesday": [
                    {"start": "10:00", "end": "11:00", "subject": "Data Mining", "faculty": "—", "room": "—"},
                    {"start": "11:00", "end": "12:00", "subject": "CS304", "faculty": "—", "room": "C201"},
                    {"start": "12:00", "end": "13:00", "subject": "CS306", "faculty": "—", "room": "C201"},
                    {"start": "13:00", "end": "14:00", "subject": "CS305", "faculty": "SKR", "room": "C201"},
                    {"start": "16:00", "end": "18:00", "subject": "CS312 (Compiler Lab)", "faculty": "—", "room": "CC Floor"}
                ],
                "Thursday": [
                    {"start": "10:00", "end": "11:00", "subject": "CS351", "faculty": "HN", "room": "C201"},
                    {"start": "11:00", "end": "12:00", "subject": "CS306", "faculty": "—", "room": "C201"},
                    {"start": "12:00", "end": "13:00", "subject": "CS306", "faculty": "—", "room": "C201"},
                    {"start": "13:00", "end": "14:00", "subject": "Data Mining", "faculty": "—", "room": "—"},
                    {"start": "16:00", "end": "18:00", "subject": "CS533 (ML Lab)", "faculty": "TM", "room": "CC Floor"}
                ],
                "Friday": [
                    {"start": "09:00", "end": "10:00", "subject": "CS307", "faculty": "—", "room": "—"},
                    {"start": "10:00", "end": "11:00", "subject": "CS306", "faculty": "—", "room": "C201"},
                    {"start": "11:00", "end": "12:00", "subject": "CS304", "faculty": "—", "room": "C201"},
                    {"start": "17:00", "end": "18:00", "subject": "CS305", "faculty": "SKR", "room": "C201"}
                ]
            }
        }
    }
}

def check_lectures():
    try:
        ist_tz = timezone(timedelta(hours=5, minutes=30))
        now = datetime.now(ist_tz)
        day_name = now.strftime("%A")
        
        for chat_id, info in users.items():
            branch = info.get("college_branch")
            year = info.get("college_year")
            group = info.get("college_group")
            reminder_seconds = info.get("college_reminder")
            
            if not (branch and year and group and reminder_seconds):
                continue
                
            try:
                # If we don't have the user's specific branch/year table yet, it safely skips
                schedule = TIMETABLE[branch][year][group].get(day_name, [])
            except KeyError:
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
                        executor.submit(send_message, chat_id, msg)
    except:
        pass
