# 🤖 Code Contest Alerts & Hybrid AI Support Bot

A powerful, highly scalable Telegram Bot built in Python. This bot serves two primary purposes:
1. **Automated Reminders:** Scrapes Codeforces, CodeChef, and LeetCode APIs to alert users of upcoming coding contests.
2. **Hybrid AI Customer Support:** Features a smart auto-reply system that matches keywords to instantly answer user queries. If the bot doesn't know the answer, it forwards the message directly to the Admin. When the Admin replies, the bot **learns the answer** and stores it in the database for the next user!

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
* 🚀 **Multi-Platform Alerts:** Automatically tracks Codeforces, CodeChef, and LeetCode contests.
* 💡 **Daily Coding Challenge:** Fetches LeetCode's daily challenge with difficulty, tags, and direct link.
* 🎓 **College Lecture Reminders:** Sends class alerts based on branch, year, and group from MongoDB-stored timetables.
* 🧠 **Self-Learning AI:** Keyword-matching engine that gets smarter as the Admin answers questions.
* 🔧 **Admin Control Panel:** Separate admin interface with Stats, Broadcast, Announcers, and Pending Questions.
* 🔕 **Manual Toggle:** Reminders persist until the user manually turns them off.
* ☁️ **MongoDB Atlas:** All data synced to the cloud — zero local state dependencies.
* 🧹 **6-Hour Auto-Delete:** Messages auto-cleaned from Telegram after 6 hours.

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
