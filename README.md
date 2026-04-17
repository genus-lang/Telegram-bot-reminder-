# 🤖 Code Contest Alerts, College Reminders & Hybrid AI Support Bot

A powerful, highly scalable Telegram Bot built in Python. This bot serves multiple purposes for college students and competitive programmers:
1. **Automated Coding Contest Reminders:** Scrapes Codeforces, CodeChef, LeetCode, AtCoder, HackerRank, HackerEarth, and GeeksforGeeks APIs to alert users of upcoming coding contests.
2. **College Timetable & Lecture Alerts:** Users can receive automated reminders before their college lectures start. Users can also upload their own timetable image, which is parsed by an AI Vision model (Gemini/Groq) to automatically set up personalized class reminders.
3. **Hybrid AI Customer Support:** Features a smart auto-reply system that matches keywords to instantly answer user queries. If the bot doesn't know the answer, it forwards the message directly to the Admin. When the Admin replies, the bot **learns the answer** and stores it in the database for the next user!

## 📁 Folder Structure
```
remainder-bot/
│
├── .env                  # Secret keys (ignored by Git)
├── .gitignore            # Git exclusion rules
├── requirements.txt      # Python dependencies
├── README.md             # This file
│
├── data/                 # Static data & legacy backups
│   ├── timetable/        # Source timetable PDFs
│   │   └── time_table.pdf.pdf
│   ├── users.json        # Legacy backup
│   ├── pending.json
│   └── knowledge.json
│
├── src/                  # Core bot source code
│   ├── __init__.py       # Package initializer
│   ├── config.py         # Environment variables & constants
│   ├── database.py       # MongoDB connection & in-memory caches
│   ├── handlers.py       # User & Admin message routing
│   ├── main.py           # Entry point (while True loop)
│   ├── scrapers.py       # Codeforces, CodeChef, LeetCode APIs
│   ├── telegram.py       # Telegram API helpers
│   ├── timetable.py      # College lecture reminder engine
│   └── utils.py          # Shared utility functions
│
└── tools/                # One-time scripts & testing
    ├── migrate_pdf.py    # PDF → MongoDB migration script
    └── test_timetable.py # Integration test for all branches/years
```

## ✨ Key Features
* 🚀 **Extensive Platform Tracking:** Tracks Codeforces, CodeChef, LeetCode, AtCoder, HackerRank, HackerEarth, and GeeksforGeeks contests with an inline menu to toggle which platforms to receive alerts for.
* 💡 **Daily Coding Challenge:** Fetches LeetCode's daily challenge with difficulty, tags, and a direct link.
* 🎓 **Global & Custom College Timetables:** Sends class alerts based on standard timetables (e.g., branches, years). Users can also upload a photo of their timetable and the bot uses Gemini 1.5 Flash (with Groq Llama 3 Vision fallback) to extract the schedule.
* ⏱ **Custom Reminder Times:** Users can manually select exactly how many minutes before a contest or lecture they want to be notified.
* 🧠 **Self-Learning Auto-Reply AI:** Keyword-matching engine that answers common user questions based on what it learned directly from the Admin's previous replies.
* 🔧 **Admin Control Panel:** Separate admin interface with commands for `/stats`, `/broadcast`, `/announcers`, and resolving Pending Questions.
* 🚦 **Smart Rate Limiting:** Safe broadcast handling with built-in logic handling Telegram's 429 Too Many Requests, which prevents blocks when sending mass reminders.
* ☁️ **Stateless Architecture:** Fully backed by MongoDB Atlas. Supports deployments on Koyeb, Render, or Railway with webhooks or continuous long polling without overlapping conflicts.
* 🧹 **Message Auto-Cleanup:** Clutter-free chats by self-deleting sent messages after 6 hours using a background scheduler.

---

## 🛠 Setup & Installation

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Telegram Bot Setup
1. Search for `BotFather` on Telegram → `/newbot` → save the **Bot Token**.
2. Get your **Admin Chat ID** from `userinfobot` on Telegram.

### 3. MongoDB Setup
1. Create a free cluster on [MongoDB Atlas](https://www.mongodb.com/atlas).
2. Create a Database User and whitelist IP `0.0.0.0/0`.
3. Copy your `MONGO_URI` connection string.

### 4. Environment Variables
Create `.env` in the project root:
```env
BOT_TOKEN="your_bot_token"
ADMIN_CHAT_ID="your_chat_id"
MONGO_URI="mongodb+srv://user:pass@cluster.mongodb.net/?retryWrites=true&w=majority"
```

### 5. Start the Bot
```bash
python -m src.main
```

### 6. (Optional) Migrate Timetable from PDF
```bash
python tools/migrate_pdf.py
```

---

## 👤 User Features
| Button | What it does |
|--------|-------------|
| 🏆 Contests | Set contest reminders (15/30/60 min), view upcoming, get daily challenge |
| 🎓 Colleges | Pick Branch → Year → Group → Set lecture reminder time |
| 🔕 Turn Off | Disable contest or college alerts separately (persists until re-enabled) |

## 🔧 Admin Panel (shown on /start for admin)
| Button | What it does |
|--------|-------------|
| 📊 Stats | Total users, active today, reminder distribution, alert counts |
| 📢 Broadcast | Send announcements to all users via `/announce` |
| 👥 Announcers | View/add/remove authorized announcers |
| 🔍 Pending Questions | View unanswered user questions |



## License
This project is licensed under the CC BY-NC 4.0 License.
Commercial use is not allowed.
