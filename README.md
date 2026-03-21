# 🤖 Code Contest Alerts & Hybrid AI Support Bot

A powerful, highly scalable Telegram Bot built in Python. This bot serves two primary purposes:
1. **Automated Reminders:** Scrapes Codeforces, CodeChef, and LeetCode APIs to alert users of upcoming coding contests.
2. **Hybrid AI Customer Support:** Features a smart auto-reply system that matches keywords to instantly answer user queries. If the bot doesn't know the answer, it forwards the message directly to the Admin. When the Admin replies, the bot **learns the answer** and stores it in the database for the next user!

## ✨ Key Features
* 🚀 **Multi-Platform Alerts:** Automatically tracks and alerts users when contests on **Codeforces, CodeChef, and LeetCode** are starting.
* 🧠 **Self-Learning AI:** A keyword-matching engine (`knowledge base`) that continuously gets smarter as the Admin interacts with users.
* 👥 **Massive Scalability:** Powered by a `ThreadPoolExecutor`, capable of gracefully handling 5,000–10,000 active users concurrently without freezing or crashing.
* 🧹 **6-Hour Auto-Delete:** Protects the cloud database and keeps the chat UI clean by automatically tracking and deleting user messages & bot replies from Telegram after 6 hours via a background thread.
* 📢 **Announcement Broadcasts:** Admins can securely send global announcement blasts to the entire user base. Admins can also grant/revoke announcer permissions to specific moderators.
* ☁️ **MongoDB Integration:** 100% stateless backend design. All user preferences, knowledge bases, sent logs, and pending messages are securely synced to MongoDB Atlas.

---

## 🛠 Setup & Installation Guide

If you are cloning this repository, follow these steps to get the bot running on your local machine or cloud server:

### 1. Requirements
Ensure you have Python 3.8+ installed. 
Install the required dependencies by running:
```bash
pip install -r requirements.txt
```

### 2. Telegram Bot Configuration
1. Open the Telegram app and search for `BotFather`.
2. Send the command `/newbot` and follow the instructions to create your bot.
3. Save the **Bot Token** that BotFather gives you.

To receive direct messages from the bot, you will also need your personal **Admin Chat ID**. You can find this by sending a message to `userinfobot` or `RawDataBot` on Telegram.

### 3. Database Configuration (MongoDB)
This bot relies on MongoDB to store user data and the learning algorithm's knowledge base.
1. Go to [MongoDB Atlas](https://www.mongodb.com/atlas) and create a highly scalable **Free M0 Cluster**.
2. Go to **Database Access** and create a Database User/Password.
3. Go to **Network Access** and add the IP `0.0.0.0/0` to allow your bot to connect from anywhere.
4. Go back to your Cluster, click **Connect -> Drivers**, and copy your `MONGO_URI` connection string.

### 4. Setting up Environment Variables
For security reasons, your keys should absolutely never be pushed to GitHub. 

Create a file named `.env` in the root folder of the project, and paste in your credentials:
```env
BOT_TOKEN="your_bot_token_from_botfather"
ADMIN_CHAT_ID="your_personal_chat_id"
MONGO_URI="mongodb+srv://<username>:<password>@cluster0.abcde.mongodb.net/?retryWrites=true&w=majority"
```

### 5. Start the Bot
Run the main script:
```bash
python Bot.py
```
*(On the very first launch, if you have existing legacy `.json` files in the directory, the bot will automatically detect them and securely migrate the data over to MongoDB before clearing them).*

---

## 💻 Commands Reference
* `/start` - Displays the welcome message and command list.
* `/next` - Fetches and displays a live countdown of upcoming contests.
* `/15`, `/30`, `/60` - Set personal contest reminder times (15 min, 30 min, 1 hr).

**Admin Only Commands:**
* `/stats` - View live database stats (Total users, active today, etc.).
* `/announce <msg>` - Blast a message to every active user.
* `/add_announcer <id>` - Authorize a moderator to use the announcement tool.
* `/remove_announcer <id>` - Revoke announcement permissions.
* `/announcers` - View the list of authorized announcers.
