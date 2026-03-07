import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask
from threading import Thread

# ------------------- KEEP ALIVE -------------------
app = Flask('')
@app.route('/')
def home(): return "Bot is running"
def run_web(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)))
def keep_alive(): Thread(target=run_web).start()

# ------------------- CONFIG -------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
MONGO_URI = os.getenv("MONGO_URI")

bot = telebot.TeleBot(BOT_TOKEN)
client = MongoClient(MONGO_URI)
db = client["vipbot"]
users_col = db["users"]

# ------------------- CHANNELS -------------------
VIP_CHANNELS = [
    {"id": -1003128362218, "name": "VIP Channel 1"},
    {"id": -1002978674693, "name": "VIP Channel 2"},
    {"id": -1003009075671, "name": "VIP Channel 3"}
]

# ------------------- PLANS -------------------
PLANS = {
    "plan1": {"duration": 30, "price": 200, "label": "🗣 1 ወር ➡️ 200 ብር"},
    "plan2": {"duration": 60, "price": 380, "label": "🗣 2 ወር ➡️ 380 ብር"},
    "plan3": {"duration": 90, "price": 550, "label": "🗣 3 ወር ➡️ 550 ብር"},
    "plan5": {"duration": 150, "price": 1050, "label": "🗣 5 ወር ➡️ 1050 ብር"},
    "plan12": {"duration": 365, "price": 2000, "label": "💎 1 አመት ➡️ 2000 ብር"}
}

# ------------------- START -------------------
@bot.message_handler(commands=["start"])
def start(message):
    if message.from_user.id == ADMIN_ID:
        markup = InlineKeyboardMarkup()
        for ch in VIP_CHANNELS:
            markup.add(InlineKeyboardButton(f"👤 Manage: {ch['name']}", callback_data=f"manage_{ch['id']}"))
        markup.add(InlineKeyboardButton("➕ አዲስ ቻናል መጨመር", callback_data="add_new"))
        bot.send_message(ADMIN_ID, "✅ አድሚን ፓነል ንቁ ነው", reply_markup=markup)
        return

    text = "👋 እንኳን ወደ VIP ቻናሎቻችን በደህና መጡ!\n\n✅ ከታች ከተዘረዘሩት ጥቅሎች የሚፈልጉትን ይምረጡ:"
    markup = InlineKeyboardMarkup()
    for key, plan in PLANS.items():
        markup.add(InlineKeyboardButton(plan["label"], callback_data=key))
    bot.send_message(message.chat.id, text, reply_markup=markup)

# ------------------- PLAN SELECT -------------------
@bot.callback_query_handler(func=lambda call: call.data.startswith("plan"))
def choose_payment(call):
    plan_key = call.data
    user_id = call.from_user.id
    users_col.update_one({"user_id": user_id}, {"$set":{"plan": plan_key}}, upsert=True)

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🏦 CBE Bank", callback_data="cbe"))
    markup.add(InlineKeyboardButton("🏦 Abyssinia Bank", callback_data="aby"))
    markup.add(InlineKeyboardButton("📱 Telebirr", callback_data="tele"))

    bot.send_message(call.message.chat.id, "💳 ገንዘብ መላኪያ አማራጮች ይምረጡ:", reply_markup=markup)

# ------------------- PAYMENT INFO -------------------
@bot.callback_query_handler(func=lambda call: call.data in ["cbe", "aby", "tele"])
def payment_info(call):
    if call.data=="cbe":
        text="🏦 CBE Bank\nName: Getamesay Fikru\nAccount: 1000355140206\n\n📸 Screenshot ይላኩ"
    elif call.data=="aby":
        text="🏦 Abyssinia Bank\nName: Getamesay Fikru\nAccount: 167829104\n\n📸 Screenshot ይላኩ"
    else:
        text="📱 Telebirr\nName: Getamesay Fikru\nNumber: 0965979124\n\n📸 Screenshot ይላኩ"

    msg = bot.send_message(call.message.chat.id, text)
    bot.register_next_step_handler(msg, get_screenshot)

# ------------------- SCREENSHOT -------------------
def get_screenshot(message):
    if not message.photo:
        bot.send_message(message.chat.id, "📸 Screenshot እባክዎ ይላኩ")
        return
    bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ Approve", callback_data=f"approve_{message.from_user.id}"))
    markup.add(InlineKeyboardButton("❌ Reject", callback_data=f"reject_{message.from_user.id}"))
    bot.send_message(ADMIN_ID, f"💰 አዲስ ክፍያ\nUser ID: {message.from_user.id}", reply_markup=markup)
    bot.send_message(message.chat.id, "✅ የክፍያ ማስረጃዎ ተልኳል። እባክዎ ይጠብቁ።")

# ------------------- APPROVE / REJECT -------------------
@bot.callback_query_handler(func=lambda call: call.data.startswith("approve") or call.data.startswith("reject"))
def approve_reject(call):
    user_id = int(call.data.split("_")[1])
    if call.data.startswith("reject"):
        bot.send_message(user_id,"❌ ክፍያዎ አልተፈቀደም. እባክዎ እንደገና ይሞክሩ.")
        bot.edit_message_text("❌ User Rejected", call.message.chat.id, call.message.message_id)
        users_col.delete_one({"user_id": user_id})
        return

    user = users_col.find_one({"user_id": user_id})
    plan_key = user["plan"]
    plan = PLANS[plan_key]
    expiry = datetime.now() + timedelta(days=plan["duration"])
    expiry_ts = int(expiry.timestamp())
    markup = InlineKeyboardMarkup()
    for ch in VIP_CHANNELS:
        try:
            invite_link = bot.create_chat_invite_link(ch["id"], member_limit=1, expire_date=expiry_ts).invite_link
            markup.add(InlineKeyboardButton(f"☑️ {ch['name']}", url=invite_link))
        except: pass
    bot.send_message(user_id,"🎉 ክፍያዎ ተረጋግጧል! ቻናሎቻችን ከታች ያገኙ:", reply_markup=markup)
    users_col.update_one({"user_id": user_id},{"$set":{"expiry":expiry.timestamp()}})

# ------------------- AUTO REMOVE EXPIRED -------------------
def kick_expired():
    now = datetime.now().timestamp()
    expired = users_col.find({"expiry":{"$lte": now}})
    for user in expired:
        for ch in VIP_CHANNELS:
            try:
                bot.ban_chat_member(ch["id"], user["user_id"])
                bot.unban_chat_member(ch["id"], user["user_id"])
            except: pass
        try:
            bot.send_message(user["user_id"], "⚠️ የVIP ጊዜዎ አብቅቷል። 🔄 እንደገና ይምረጡ.")
        except: pass
        users_col.delete_one({"_id": user["_id"]})

# ------------------- ADMIN VIP LIST -------------------
@bot.message_handler(commands=['listvip'], func=lambda m: m.from_user.id==ADMIN_ID)
def list_vip(message):
    users = list(users_col.find())
    if not users: bot.send_message(ADMIN_ID,"❌ ምንም VIP ተጠቃሚ አልተመዘገበም"); return
    text = "📋 VIP Users List:\n\n"
    for u in users:
        text += f"👤 UserID: {u['user_id']} | Plan: {u.get('plan','N/A')} | Expiry: {datetime.fromtimestamp(u.get('expiry',0)).strftime('%Y-%m-%d %H:%M')}\n"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("☑️ Resend VIP Link", callback_data=f"resend_{u['user_id']}"))
        bot.send_message(ADMIN_ID,text, reply_markup=markup)
        text = ""

@bot.callback_query_handler(func=lambda call: call.data.startswith("resend_"))
def resend_vip_link(call):
    uid = int(call.data.split("_")[1])
    user = users_col.find_one({"user_id": uid})
    if not user: bot.send_message(ADMIN_ID, "❌ User not found"); return
    expiry_ts = int(user.get("expiry", datetime.now().timestamp()))
    markup = InlineKeyboardMarkup()
    for ch in VIP_CHANNELS:
        try:
            invite_link = bot.create_chat_invite_link(ch["id"], member_limit=1, expire_date=expiry_ts).invite_link
            markup.add(InlineKeyboardButton(f"☑️ {ch['name']}", url=invite_link))
        except: pass
    bot.send_message(uid, "🔗 እድሳት ቻናሎች እነሆ:", reply_markup=markup)
    bot.answer_callback_query(call.id, "✅ VIP link resent to user")

# ------------------- RUN -------------------
if __name__=="__main__":
    keep_alive()
    scheduler = BackgroundScheduler()
    scheduler.add_job(kick_expired, 'interval', minutes=10)
    scheduler.start()
    bot.infinity_polling()
