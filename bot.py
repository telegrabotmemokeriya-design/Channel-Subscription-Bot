import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask
from threading import Thread

# ---------------- KEEP ALIVE ----------------
app = Flask('')

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

# -------- PLANS --------
PLANS = {
    "plan1": {"duration":30, "price":200},
    "plan2": {"duration":60, "price":380},
    "plan3": {"duration":90, "price":550},
    "plan6": {"duration":180, "price":1050},
    "plan12": {"duration":365, "price":2000}
}

# ---------------- START ----------------
@bot.message_handler(commands=["start"])
def start(message):

    if message.from_user.id == ADMIN_ID:
        bot.send_message(message.chat.id,"✅ አድሚን ፓነል ንቁ ነው")
        return

    text = """
👋 እንኳን ወደ VIP ቻናሎቻችን በደህና መጡ!

✅ ከታች ከተዘረዘሩት ጥቅሎች የሚፈልጉትን ይምረጡ

🗣 1 ወር ➡️ 200 ብር
🗣 2 ወር ➡️ 380 ብር
🗣 3 ወር ➡️ 550 ብር
🗣 6 ወር ➡️ 1050 ብር
🗣 1 አመት ➡️ 2000 ብር
"""
    markup = InlineKeyboardMarkup()
    for key, plan in PLANS.items():
        label = f"{plan['duration']} ቀን - {plan['price']} ብር"
        markup.add(InlineKeyboardButton(label, callback_data=key))

    bot.send_message(message.chat.id, text, reply_markup=markup)

# ---------------- PLAN SELECT ----------------
@bot.callback_query_handler(func=lambda call: call.data.startswith("plan"))
def choose_payment(call):

    plan_key = call.data
    user_id = call.from_user.id
    users_col.update_one(
        {"user_id":user_id},
        {"$set":{"plan":plan_key}},
        upsert=True
    )

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🏦 CBE Bank", callback_data="cbe"))
    markup.add(InlineKeyboardButton("🏦 Abyssinia Bank", callback_data="aby"))
    markup.add(InlineKeyboardButton("📱 Telebirr", callback_data="tele"))

    bot.send_message(
        call.message.chat.id,
        "💳 ገንዘብ መላኪያ አማራጮችን ይምረጡ",
        reply_markup=markup
    )

# ---------------- PAYMENT INFO ----------------
@bot.callback_query_handler(func=lambda call: call.data in ["cbe","aby","tele"])
def payment_info(call):
    text = """
💳 ገንዘብ መላኪያ አማራጮች

👤 Name : Getamesay Fikru
🏦 CBE : 1000355140206
🏦 Abyssinia : 167829104
📱 Telebirr : 0965979124

⚠️ ገንዘቡን ከላኩ በኋላ
📸 የላኩበትን Screenshot ይላኩ
"""
    msg = bot.send_message(call.message.chat.id,text)
    bot.register_next_step_handler(msg,get_screenshot)

# ---------------- SCREENSHOT ----------------
def get_screenshot(message):
    if not message.photo:
        bot.send_message(message.chat.id,"📸 Screenshot እባክዎ ይላኩ")
        return

    bot.forward_message(ADMIN_ID,message.chat.id,message.message_id)

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ Approve", callback_data=f"approve_{message.from_user.id}"))

    bot.send_message(ADMIN_ID,f"💰 አዲስ ክፍያ\nUser ID: {message.from_user.id}", reply_markup=markup)

    bot.send_message(message.chat.id,"✅ የክፍያ ማስረጃዎ ተልኳል። እባክዎ ይጠብቁ።")

# ---------------- APPROVE ----------------
@bot.callback_query_handler(func=lambda call: call.data.startswith("approve"))
def approve(call):
    user_id = int(call.data.split("_")[1])
    user = users_col.find_one({"user_id":user_id})
    plan_key = user["plan"]
    plan = PLANS[plan_key]
    expiry = datetime.now() + timedelta(days=plan["duration"])
    expiry_ts = int(expiry.timestamp())

    links = []
    for ch in VIP_CHANNELS:
        try:
            link = bot.create_chat_invite_link(ch, member_limit=1, expire_date=expiry_ts)
            links.append(link.invite_link)
        except:
            pass

    text = "🎉 ክፍያዎ ተረጋግጧል!\n\nVIP ቻናሎቻችን ከታች ያገኙ\n\n" + "\n".join(links)
    bot.send_message(user_id,text)

    users_col.update_one({"user_id":user_id},{"$set":{"expiry":expiry.timestamp()}})

    bot.edit_message_text("✅ User Approved", call.message.chat.id, call.message.message_id)

# ---------------- AUTO REMOVE ----------------
def kick_expired():
    now = datetime.now().timestamp()
    expired = users_col.find({"expiry":{"$lte":now}})
    for user in expired:
        for ch in VIP_CHANNELS:
            try:
                bot.ban_chat_member(ch,user["user_id"])
                bot.unban_chat_member(ch,user["user_id"])
            except:
                pass
        try:
            bot.send_message(user["user_id"],"⚠️ የVIP ጊዜዎ አብቅቷል።\n\nእንደገና VIP መግዛት ይችላሉ።")
        except:
            pass
        users_col.delete_one({"_id":user["_id"]})

# ---------------- ADMIN VIP LIST ----------------
@bot.message_handler(commands=['listvip'], func=lambda m: m.from_user.id==ADMIN_ID)
def list_vip(message):
    users = list(users_col.find())
    if not users:
        bot.send_message(ADMIN_ID,"❌ ምንም VIP ተጠቃሚ አልተመዘገበም")
        return

    text = "📋 VIP Users List:\n\n"
    for u in users:
        plan = u.get("plan","N/A")
        expiry = datetime.fromtimestamp(u.get("expiry",0)).strftime("%Y-%m-%d %H:%M")
        text += f"👤 UserID: {u['user_id']} | Plan: {plan} | Expiry: {expiry}\n"

    bot.send_message(ADMIN_ID,text)

# ---------------- RUN ----------------
if __name__=="__main__":
    keep_alive()
    scheduler = BackgroundScheduler()
    scheduler.add_job(kick_expired,'interval',minutes=10)
    scheduler.start()
    bot.infinity_polling()
