import requests
import time
import json
from src.config import BOT_TOKEN, ADMIN_CHAT_ID, executor
from src.database import history_col

# Use a session to reuse TCP connections for 3x lower latency on consecutive API calls
session = requests.Session()

def schedule_delete(chat_id, message_id, delay_seconds=21600):
    if not message_id or str(chat_id) == ADMIN_CHAT_ID: return
    executor.submit(history_col.insert_one, {
        "chat_id": str(chat_id),
        "message_id": str(message_id),
        "delete_at": time.time() + delay_seconds
    })

def send_message(chat_id, text, auto_delete=True, parse_mode="HTML", reply_markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup is not None:
        payload["reply_markup"] = json.dumps(reply_markup)
    try:
        resp = session.post(url, data=payload, timeout=10).json()
        if resp.get("ok"):
            msg_id = str(resp["result"]["message_id"])
            if auto_delete:
                schedule_delete(chat_id, msg_id)
            return msg_id
    except:
        pass
    return None

def send_photo(chat_id, photo_url, caption="", auto_delete=True, parse_mode="HTML"):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    payload = {"chat_id": chat_id, "photo": photo_url, "caption": caption}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    try:
        resp = session.post(url, data=payload, timeout=10).json()
        if resp.get("ok"):
            msg_id = str(resp["result"]["message_id"])
            if auto_delete:
                schedule_delete(chat_id, msg_id)
            return msg_id
    except:
        pass
    return None

def send_message_get_id(chat_id, text, auto_delete=True, parse_mode="HTML", reply_markup=None):
    return send_message(chat_id, text, auto_delete, parse_mode, reply_markup)

def send_chat_action(chat_id, action="typing"):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendChatAction"
    try:
        session.post(url, data={"chat_id": chat_id, "action": action}, timeout=5)
    except:
        pass

def answer_callback_query(callback_query_id, text=None, show_alert=False):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery"
    payload = {"callback_query_id": callback_query_id, "show_alert": show_alert}
    if text: payload["text"] = text
    try:
        session.post(url, data=payload, timeout=5)
    except:
        pass

def edit_message_text(chat_id, message_id, text, parse_mode="HTML", reply_markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText"
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup is not None:
        payload["reply_markup"] = json.dumps(reply_markup)
    else:
        payload["reply_markup"] = json.dumps({"inline_keyboard": []}) # clear buttons
    try:
        session.post(url, data=payload, timeout=5)
    except:
        pass
