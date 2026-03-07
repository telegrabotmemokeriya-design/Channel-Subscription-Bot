import os
import telebot
import time
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient
from datetime import datetime, timedelta
from ethiopian_date import EthiopianDateConverter
from flask import Flask
from threading import Thread

# ------------------- KEEP ALIVE -------------------
app = Flask('')

@app.route('/')
def home():
    return "Bot is running"

def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

def keep_alive():
    Thread(target=run_web, daemon=True).start()

# ------------------- CONFIG -------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
MONGO_URI = os.getenv("MONGO_URI")

bot = telebot.TeleBot(BOT_TOKEN)
client = MongoClient(MONGO_URI)

db = client["vipbot"]
users_col = db["users"]

VIP_CHANNELS = [
    {"id": -1003128362218, "name": "VIP Channel 1"},
    {"id": -1002978674693, "name": "VIP Channel 2"},
    {"id": -1003009075671, "name": "VIP Channel 3"}
]

PLANS = {
    "plan1": {"duration": 30, "price": 200, "label": "🗣 1 ወር ➡️ 200 ብር"},
    "plan2": {"duration": 60, "price": 380, "label": "🗣 2 ወር ➡️ 380 ብር"},
    "plan3": {"duration": 90, "price": 550, "label": "🗣 3 ወር ➡️ 550 ብር"},
    "plan5": {"duration": 150, "price": 1050, "label": "🗣 5 ወር ➡️ 1050 ብር"},
    "plan12": {"duration": 365, "price": 2000, "label": "💎 1 አመት ➡️ 2000 ብር"}
}

# ------------------- HELPERS -------------------

def check_join_status(user_id, channel_id):
    try:
        member = bot.get_chat_member(channel_id, user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return "✅"
        return "☑️"
    except:
        return "☑️"

def get_channel_markup(user_id):

    markup = InlineKeyboardMarkup()

    for ch in VIP_CHANNELS:

        emoji = check_join_status(user_id, ch["id"])

        try:
            invite = bot.create_chat_invite_link(ch["id"], member_limit=1).invite_link
        except:
            invite = "https://t.me/telegram"

        markup.add(
            InlineKeyboardButton(f"{emoji} {ch['name']}", url=invite)
        )

    markup.add(
        InlineKeyboardButton("🔄 ሁኔታውን አድስ (Refresh Status)", callback_data="refresh_links")
    )

    return markup


def to_ethiopian(ts):

    dt = datetime.fromtimestamp(ts)

    conv = EthiopianDateConverter.to_ethiopian(
        dt.year,
        dt.month,
        dt.day
    )

    return f"{conv[2]}/{conv[1]}/{conv[0]}"

# ------------------- START -------------------

@bot.message_handler(commands=["start"])
def start(message):

    uid = message.from_user.id

    if uid == ADMIN_ID:

        markup = InlineKeyboardMarkup()

        markup.add(
            InlineKeyboardButton("📋 የደንበኞች ዝርዝር", callback_data="admin_list")
        )

        markup.add(
            InlineKeyboardButton("📢 Broadcast", callback_data="admin_bc")
        )

        bot.send_message(
            ADMIN_ID,
            "🛠 የአድሚን ፓነል",
            reply_markup=markup
        )

        return

    markup = InlineKeyboardMarkup()

    for key,plan in PLANS.items():

        markup.add(
            InlineKeyboardButton(plan["label"], callback_data=key)
        )

    bot.send_message(
        uid,
        "👋 እንኳን ደህና መጡ!\nVIP ለመግባት ጥቅል ይምረጡ:",
        reply_markup=markup
    )

# ------------------- CALLBACKS -------------------

@bot.callback_query_handler(func=lambda call:True)
def router(call):

    uid = call.from_user.id
    mid = call.message.message_id

    if call.data in PLANS:

        users_col.update_one(
            {"user_id":uid},
            {"$set":{
                "plan":call.data,
                "username":call.from_user.username
            }},
            upsert=True
        )

        markup = InlineKeyboardMarkup()

        markup.add(
            InlineKeyboardButton("🏦 CBE",callback_data="p_cbe"),
            InlineKeyboardButton("🏦 Abyssinia",callback_data="p_aby"),
            InlineKeyboardButton("📱 Telebirr",callback_data="p_tele")
        )

        bot.edit_message_text(
            "💳 የክፍያ አማራጭ ይምረጡ:",
            uid,
            mid,
            reply_markup=markup
        )

    elif call.data.startswith("p_"):

        method = call.data.split("_")[1]

        if method == "cbe":
            bank = "🏦 CBE\n👤 Getamesay Fikru\n🔢 1000355140206"
        elif method == "aby":
            bank = "🏦 Abyssinia\n👤 Getamesay Fikru\n🔢 167829104"
        else:
            bank = "📱 Telebirr\n👤 Getamesay Fikru\n📞 0965979124"

        bot.edit_message_text(
            f"{bank}\n\n📸 Screenshot ይላኩ",
            uid,
            mid
        )

        bot.register_next_step_handler(
            call.message,
            get_screenshot
        )

    elif call.data.startswith("approve_"):

        tid = int(call.data.split("_")[1])

        udata = users_col.find_one({"user_id":tid})

        if udata and "plan" in udata:

            plan = PLANS[udata["plan"]]

            exp_ts = (
                datetime.now()
                +
                timedelta(days=plan["duration"])
            ).timestamp()

            users_col.update_one(
                {"user_id":tid},
                {"$set":{
                    "expiry":exp_ts,
                    "active":True
                }}
            )

            bot.send_message(
                tid,
                f"🎉 ክፍያዎ ጸድቋል!\n📅 ማብቂያ: {to_ethiopian(exp_ts)}",
                reply_markup=get_channel_markup(tid)
            )

            bot.answer_callback_query(call.id,"Approved")

            bot.send_message(
                ADMIN_ID,
                f"✅ ተጠቃሚ {tid} ጸድቋል!"
            )

# ------------------- SCREENSHOT -------------------

def get_screenshot(message):

    if not message.photo:

        bot.reply_to(
            message,
            "📸 screenshot ይላኩ"
        )

        bot.register_next_step_handler(
            message,
            get_screenshot
        )

        return

    markup = InlineKeyboardMarkup()

    markup.add(
        InlineKeyboardButton(
            "✅ Approve",
            callback_data=f"approve_{message.from_user.id}"
        ),
        InlineKeyboardButton(
            "❌ Reject",
            callback_data=f"reject_{message.from_user.id}"
        )
    )

    bot.forward_message(
        ADMIN_ID,
        message.chat.id,
        message.message_id
    )

    bot.send_message(
        ADMIN_ID,
        f"💰 payment from {message.from_user.id}",
        reply_markup=markup
    )

    bot.send_message(
        message.chat.id,
        "✅ sent to admin"
    )

# ------------------- EXPIRY CHECK -------------------

def check_expiries():

    while True:

        now = datetime.now().timestamp()

        expired = users_col.find({
            "expiry":{"$lt":now},
            "active":True
        })

        for u in expired:

            uid = u["user_id"]

            for ch in VIP_CHANNELS:

                try:
                    bot.ban_chat_member(ch["id"],uid)
                    bot.unban_chat_member(ch["id"],uid)
                except:
                    pass

            users_col.update_one(
                {"user_id":uid},
                {"$set":{"active":False}}
            )

            bot.send_message(
                uid,
                "⚠️ VIP expired"
            )

        time.sleep(3600)

# ------------------- RUN -------------------

if __name__ == "__main__":

    keep_alive()

    Thread(
        target=check_expiries,
        daemon=True
    ).start()

    bot.infinity_polling()
