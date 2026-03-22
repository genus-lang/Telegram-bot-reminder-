import requests
from datetime import datetime, timezone
from src.config import DEFAULT_REMINDER, executor
from src.database import users, sent, sent_col
from src.telegram import send_message, send_photo
from src.utils import escape_html

def is_rated_contest(platform, name):
    """Filter out unrated/practice contests across platforms."""
    name_lower = name.lower()
    if platform == "Codeforces":
        keywords = ["div. 1", "div. 2", "div. 3", "div. 4", "educational", "global round"]
        return any(kw in name_lower for kw in keywords) and "testing" not in name_lower
    elif platform == "CodeChef":
        return "starter" in name_lower
    elif platform == "LeetCode":
        return "weekly" in name_lower
    return True

def fetch_upcoming_contests():
    contests = []
    now_ts = datetime.now(timezone.utc).timestamp()
    
    try:
        url = "https://codeforces.com/api/contest.list"
        data = requests.get(url, timeout=15).json()
        for c in data.get("result", []):
            if c.get("phase") != "BEFORE": continue
            name = c.get("name", "Unknown")
            is_rated = is_rated_contest("Codeforces", name)
            start = c.get("startTimeSeconds")
            if start: contests.append(("Codeforces", name, start, start - now_ts, is_rated))
    except: pass

    try:
        url = "https://www.codechef.com/api/list/contests/all"
        data = requests.get(url, timeout=15).json()
        for c in data.get("future_contests", []):
            name = c.get("contest_name", "Unknown")
            is_rated = is_rated_contest("CodeChef", name)
            start_str = c.get("contest_start_date_iso")
            if start_str:
                start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                start = start_dt.timestamp()
                if start > now_ts:
                    contests.append(("CodeChef", name, start, start - now_ts, is_rated))
    except: pass

    try:
        url = "https://leetcode.com/graphql"
        query = {"query": "{ allContests { title startTime } }"}
        res = requests.post(url, json=query, timeout=15).json()
        for c in res.get("data", {}).get("allContests", []):
            name = c.get("title", "Unknown")
            is_rated = is_rated_contest("LeetCode", name)
            start = c.get("startTime")
            if start and start > now_ts:
                contests.append(("LeetCode", name, start, start - now_ts, is_rated))
    except: pass

    seen = set()
    unique = []
    for c in contests:
        key = (c[0], c[1])
        if key not in seen:
            seen.add(key)
            unique.append(c)
    unique.sort(key=lambda x: x[3])
    return unique

def alert_key(platform, chat_id, contest_name):
    return f"{platform}:{chat_id}:{contest_name}"

def maybe_send(chat_id, platform, contest_name, time_left_seconds):
    key = alert_key(platform, chat_id, contest_name)
    if key in sent: return
    minutes_left = max(1, int(time_left_seconds // 60))
    safe_name = escape_html(contest_name)
    executor.submit(
        send_message,
        chat_id,
        f"🚀 <b>{platform} Alert!</b>\n\n<code>{safe_name}</code>\nStarts in about <b>{minutes_left} minutes</b>!"
    )
    sent.add(key)
    executor.submit(sent_col.insert_one, {"_id": key})

def check_codeforces():
    try:
        url = "https://codeforces.com/api/contest.list"
        data = requests.get(url, timeout=15).json()
        now = datetime.utcnow().timestamp()
        for contest in data.get("result", []):
            if contest.get("phase") != "BEFORE": continue
            name = contest.get("name", "Unknown contest")
            start = contest.get("startTimeSeconds")
            if not start: continue
            for chat_id, info in users.items():
                reminder = int(info.get("reminder", DEFAULT_REMINDER))
                time_left = start - now
                if 0 < time_left <= reminder:
                    maybe_send(chat_id, "Codeforces", name, time_left)
    except: pass

def check_codechef():
    try:
        url = "https://www.codechef.com/api/list/contests/all"
        data = requests.get(url, timeout=15).json()
        now = datetime.now(timezone.utc)
        for contest in data.get("future_contests", []):
            name = contest.get("contest_name", "Unknown contest")
            start_str = contest.get("contest_start_date_iso")
            if not start_str: continue
            start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            time_left = (start - now).total_seconds()
            for chat_id, info in users.items():
                reminder = int(info.get("reminder", DEFAULT_REMINDER))
                if 0 < time_left <= reminder:
                    maybe_send(chat_id, "CodeChef", name, time_left)
    except: pass

def check_leetcode():
    try:
        url = "https://leetcode.com/graphql"
        query = {"query": "{ allContests { title startTime } }"}
        res = requests.post(url, json=query, timeout=15).json()
        contests = res.get("data", {}).get("allContests", [])
        now = datetime.utcnow().timestamp()
        for contest in contests:
            name = contest.get("title", "Unknown contest")
            start = contest.get("startTime")
            if start is None: continue
            for chat_id, info in users.items():
                reminder = int(info.get("reminder", DEFAULT_REMINDER))
                time_left = start - now
                if 0 < time_left <= reminder:
                    maybe_send(chat_id, "LeetCode", name, time_left)
    except: pass
