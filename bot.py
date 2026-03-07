import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask
from threading import Thread

# ---------------- KEEP ALIVE ----------------
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot Running"

def run_web():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    Thread(target=run_web).start()

# ---------------- CONFIG ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
MONGO_URI = os.getenv("MONGO_URI")

bot = telebot.TeleBot(BOT_TOKEN)

client = MongoClient(MONGO_URI)
db = client["vipbot"]
users_col = db["users"]

# -------- VIP CHANNELS --------
VIP_CHANNELS = [
-1003128362218,
-1002978674693,
-1003009075671
]

# ---------------- START ----------------
@bot.message_handler(commands=["start"])
def start(message):

    if message.from_user.id == ADMIN_ID:
        bot.send_message(message.chat.id,"✅ አድሚን ፓነል ንቁ ነው")
        return

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("💳 VIP ይግዙ", callback_data="buy")
    )

    bot.send_message(
        message.chat.id,
        "እንኳን ወደ VIP ቻናሎቻችን በደህና መጡ!\n\nVIP በመግዛት ሁሉንም ቻናሎቻችን መቀላቀል ይችላሉ።",
        reply_markup=markup
    )

# ---------------- BUY ----------------
@bot.callback_query_handler(func=lambda call: call.data=="buy")
def buy(call):

    msg = bot.send_message(
        call.message.chat.id,
        "እባክዎ የክፍያ screenshot ይላኩ።"
    )

    bot.register_next_step_handler(msg,get_screenshot)

# ---------------- SCREENSHOT ----------------
def get_screenshot(message):

    if not message.photo:
        bot.send_message(message.chat.id,"እባክዎ screenshot ይላኩ።")
        return

    bot.forward_message(
        ADMIN_ID,
        message.chat.id,
        message.message_id
    )

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton(
            "✅ አጽድቅ",
            callback_data=f"approve_{message.from_user.id}"
        )
    )

    bot.send_message(
        ADMIN_ID,
        f"አዲስ ክፍያ ጥያቄ\nUser ID: {message.from_user.id}",
        reply_markup=markup
    )

    bot.send_message(
        message.chat.id,
        "✅ የክፍያዎ ማስረጃ ወደ Admin ተልኳል።\nእባክዎ ይጠብቁ።"
    )

# ---------------- APPROVE ----------------
@bot.callback_query_handler(func=lambda call: call.data.startswith("approve"))
def approve(call):

    user_id = int(call.data.split("_")[1])

    expiry_time = datetime.now() + timedelta(days=30)
    expiry_ts = int(expiry_time.timestamp())

    links = []

    for ch in VIP_CHANNELS:

        try:
            link = bot.create_chat_invite_link(
                ch,
                member_limit=1,
                expire_date=expiry_ts
            )

            links.append(link.invite_link)

        except:
            pass

    text = "🎉 ክፍያዎ ተረጋግጧል!\n\nከታች ያሉትን ሊንኮች በመጠቀም VIP ቻናሎቻችንን መቀላቀል ይችላሉ።\n\n"

    for l in links:
        text += l + "\n"

    bot.send_message(user_id,text)

    users_col.update_one(
        {"user_id":user_id},
        {"$set":{"expiry":expiry_time.timestamp()}},
        upsert=True
    )

    bot.edit_message_text(
        "✅ User ተፈቅዷል",
        call.message.chat.id,
        call.message.message_id
    )

# ---------------- AUTO REMOVE ----------------
def kick_expired():

    now = datetime.now().timestamp()

    users = users_col.find({"expiry":{"$lte":now}})

    for user in users:

        for ch in VIP_CHANNELS:

            try:
                bot.ban_chat_member(ch,user["user_id"])
                bot.unban_chat_member(ch,user["user_id"])
            except:
                pass

        try:
            bot.send_message(
                user["user_id"],
                "⚠️ የVIP ጊዜዎ አብቅቷል።\n\nእንደገና ለመቀላቀል VIP እንደገና ይግዙ።"
            )
        except:
            pass

        users_col.delete_one({"_id":user["_id"]})

# ---------------- RUN ----------------
if __name__ == "__main__":

    keep_alive()

    scheduler = BackgroundScheduler()
    scheduler.add_job(kick_expired,"interval",minutes=5)
    scheduler.start()

    bot.infinity_polling()
