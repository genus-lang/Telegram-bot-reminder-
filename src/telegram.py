import requests
import time
from src.config import BOT_TOKEN, ADMIN_CHAT_ID, executor
from src.database import history_col

def schedule_delete(chat_id, message_id, delay_seconds=21600):
    if not message_id or str(chat_id) == ADMIN_CHAT_ID: return
    executor.submit(history_col.insert_one, {
        "chat_id": str(chat_id),
        "message_id": str(message_id),
        "delete_at": time.time() + delay_seconds
    })

def send_message(chat_id, text, auto_delete=True, parse_mode="HTML"):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    try:
        resp = requests.post(url, data=payload, timeout=10).json()
        if resp.get("ok"):
            msg_id = str(resp["result"]["message_id"])
            if auto_delete:
                schedule_delete(chat_id, msg_id)
            return msg_id
    except:
        pass
    return None

def send_message_get_id(chat_id, text, auto_delete=True, parse_mode="HTML"):
    return send_message(chat_id, text, auto_delete, parse_mode)

def send_chat_action(chat_id, action="typing"):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendChatAction"
    try:
        requests.post(url, data={"chat_id": chat_id, "action": action}, timeout=5)
    except:
        pass
