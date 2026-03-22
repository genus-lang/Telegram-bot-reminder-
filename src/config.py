import os
import threading
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
MONGO_URI = os.getenv("MONGO_URI")

DEFAULT_REMINDER = 1800   # 30 min
CHECK_EVERY_SECONDS = 30  # poll more often, but still light
MATCH_THRESHOLD = 0.75    # 75% of stored keywords must be present in user question

# Threading Executor for background tasks
executor = ThreadPoolExecutor(max_workers=50)
