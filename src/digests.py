from datetime import datetime, timezone, timedelta
from src.database import users
from src.timetable import timetable_cache
from src.config import executor
from src.telegram import send_message
from src.scrapers import fetch_upcoming_contests, fetch_daily_challenge
from src.utils import escape_html

def send_morning_digests():
    print("Generating morning digests...")
    
    try:
        contests = fetch_upcoming_contests()
        # filter only contests starting today (in next 24 hours).
        upcoming_today = [c for c in contests if c[3] <= 24 * 3600]
    except:
        upcoming_today = []
        
    try:
        daily_challenge = fetch_daily_challenge()
    except:
        daily_challenge = None
        
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    now = datetime.now(ist_tz)
    day_name = now.strftime("%A")
    
    contest_text = ""
    if upcoming_today:
        lines = []
        for (plat, name, start, left, rated) in upcoming_today:
            lines.append(f"• <b>{plat}</b>: {escape_html(name)}")
        contest_text = "\n".join(lines)
    else:
        contest_text = "<i>No contests today.</i>"
        
    dc_text = ""
    if daily_challenge:
        dc_text = f"<b>{escape_html(daily_challenge['title'])}</b> ({daily_challenge.get('difficulty', '?')})"
    else:
        dc_text = "<i>Daily challenge unavailable right now.</i>"
    
    for chat_id, info in users.items():
        reminder = info.get("college_reminder", 0)
        branch = info.get("college_branch")
        year = info.get("college_year")
        group = info.get("college_group", 0)
        
        lec_count = 0
        lecs_names = []
        # Support default branch routing without group (MNC/ECE) by treating info.college_group as a string
        if reminder > 0 and branch and year is not None:
            doc_id = f"{branch}_Year{year}"
            cached_doc = timetable_cache.get(doc_id, {})
            schedule = cached_doc.get("groups", {}).get(str(group), {}).get(day_name, [])
            lec_count = len(schedule)
            for lec in schedule:
                lecs_names.append(escape_html(lec["subject"])[:20]) # short name
                
        if lec_count == 0 and not upcoming_today:
            continue # Don't spam users if they literally have nothing to do today and aren't watching contests
            
        lec_text = f"You have <b>{lec_count} classes</b> today."
        if lec_count > 0:
            lec_text += f"\n<i>({', '.join(lecs_names)})</i>"
            
        msg = (
            f"🌅 <b>Good morning!</b> Here is your plan for today:\n\n"
            f"🎓 <b>Lectures:</b>\n{lec_text}\n\n"
            f"🏆 <b>Contests:</b>\n{contest_text}\n\n"
            f"💡 <b>Daily Goal:</b>\nSolve LeetCode {dc_text}"
        )
        
        executor.submit(send_message, chat_id, msg)
