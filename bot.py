import os, sqlite3, logging
from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import pytz, asyncio

logging.basicConfig(level=logging.INFO)

TOKEN = os.environ["BOT_TOKEN"]
URL = os.environ["RENDER_EXTERNAL_URL"]
TZ = pytz.timezone("Asia/Dhaka")

app = Flask(__name__)
application = Application.builder().token(TOKEN).build()

conn = sqlite3.connect("reminders.db", check_same_thread=False)
c = conn.cursor()
c.execute("""CREATE TABLE IF NOT EXISTS reminders
(id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, text TEXT, time TEXT)""")
conn.commit()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "স্বাগতম!\n\n"
        "রিমাইন্ডার যোগ করতে:\n/add কাজের_নাম HH:MM\nউদাহরণ: /add পড়াশোনা 19:30\n\n"
        "রুটিন দেখতে: /list\n"
        "মুছতে: /del আইডি"
    )

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        args = context.args
        time_str = args[-1]
        datetime.strptime(time_str, "%H:%M")
        text = " ".join(args[:-1])
        c.execute("INSERT INTO reminders (chat_id, text, time) VALUES (?,?,?)",
                   (update.effective_chat.id, text, time_str))
        conn.commit()
        await update.message.reply_text(f"✅ যোগ হয়েছে: {text} - {time_str}")
    except Exception:
        await update.message.reply_text("ফরম্যাট ভুল। উদাহরণ:\n/add পড়াশোনা 19:30")

async def list_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c.execute("SELECT id, text, time FROM reminders WHERE chat_id=?", (update.effective_chat.id,))
    rows = c.fetchall()
    if not rows:
        await update.message.reply_text("কোনো রিমাইন্ডার নেই।")
        return
    msg = "তোমার রুটিন:\n\n" + "\n".join([f"{r[0]}. {r[1]} - {r[2]}" for r in rows])
    await update.message.reply_text(msg)

async def delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        rid = int(context.args[0])
        c.execute("DELETE FROM reminders WHERE id=? AND chat_id=?", (rid, update.effective_chat.id))
        conn.commit()
        await update.message.reply_text("🗑️ মুছে ফেলা হয়েছে।")
    except Exception:
        await update.message.reply_text("সঠিক আইডি দাও। যেমন: /del 3")

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("add", add))
application.add_handler(CommandHandler("list", list_reminders))
application.add_handler(CommandHandler("del", delete))

bot = Bot(token=TOKEN)

def check_reminders():
    now = datetime.now(TZ).strftime("%H:%M")
    c.execute("SELECT chat_id, text FROM reminders WHERE time=?", (now,))
    for chat_id, text in c.fetchall():
        try:
            asyncio.run(bot.send_message(chat_id=chat_id, text=f"⏰ রিমাইন্ডার: {text}"))
        except Exception as e:
            logging.error(e)

scheduler = BackgroundScheduler()
scheduler.add_job(check_reminders, "cron", minute="*")
scheduler.start()

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    asyncio.run(application.process_update(update))
    return "ok"

@app.route("/")
def index():
    return "Bot is running"

asyncio.run(bot.set_webhook(url=f"{URL}/{TOKEN}"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
