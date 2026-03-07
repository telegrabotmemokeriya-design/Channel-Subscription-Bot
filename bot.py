import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient
from datetime import datetime, timedelta
from convertdate import ethiopian
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask
from threading import Thread

# ------------------- CONFIG -------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
MONGO_URI = os.getenv("MONGO_URI")

bot = telebot.TeleBot(BOT_TOKEN)
client = MongoClient(MONGO_URI)
db = client["vipbot"]
users_col = db["users"]

# ------------------- VIP CHANNELS -------------------
VIP_CHANNELS = [
    {"id": -1003128362218, "name": "VIP ቻናል 1"},
    {"id": -1002978674693, "name": "VIP ቻናል 2"},
    {"id": -1003009075671, "name": "VIP ቻናል 3"}
]

# ------------------- PLANS -------------------
PLANS = {
    "plan1": {"label": "🔹 1 ወር VIP", "duration": 30},
    "plan2": {"label": "🔸 3 ወር VIP", "duration": 90},
    "plan3": {"label": "⭐ 6 ወር VIP", "duration": 180},
}

# ------------------- KEEP ALIVE -------------------
app = Flask('')

@app.route('/')
def home():
    return "Bot is running"

def run_web():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

def keep_alive():
    t = Thread(target=run_web)
    t.start()

# ------------------- Helper: Convert to Ethiopian Calendar -------------------
def eth_date(timestamp):
    dt = datetime.fromtimestamp(timestamp)
    eth_year, eth_month, eth_day = ethiopian.from_gregorian(dt.year, dt.month, dt.day)
    return f"{eth_day:02d}/{eth_month:02d}/{eth_year}"

# ------------------- ADMIN PANEL /start -------------------
@bot.message_handler(commands=["start"])
def start(message):
    if message.from_user.id == ADMIN_ID:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📋 VIP ተጠቃሚዎች ዝርዝር", callback_data="vip_list"))
        markup.add(InlineKeyboardButton("📢 VIP ቻናሎች", callback_data="vip_channels"))
        bot.send_message(message.chat.id, "✅ አድሚን ፓነል", reply_markup=markup)

# ------------------- ADMIN CALLBACK HANDLER -------------------
@bot.callback_query_handler(func=lambda call: True)
def admin_panel_buttons(call):
    if call.data == "vip_list":
        users = list(users_col.find())
        if not users:
            bot.send_message(ADMIN_ID, "❌ ምንም VIP ተጠቃሚ አልተመዘገበም.")
            return
        text = "📋 VIP ተጠቃሚዎች ዝርዝር:\n\n"
        for u in users:
            expiry_eth = eth_date(u.get("expiry",0))
            text += f"👤 UserID: {u['user_id']} | እቅድ: {u.get('plan','N/A')} | ጊዜ ማብቂያ (ET): {expiry_eth}\n"
            if "channels" in u:
                for ch in u["channels"]:
                    text += f"   🔹 {ch['name']} | [Link]({ch['link']})\n"
            text += "\n"
        bot.send_message(ADMIN_ID, text, parse_mode="Markdown")

    elif call.data == "vip_channels":
        markup = InlineKeyboardMarkup()
        for ch in VIP_CHANNELS:
            markup.add(InlineKeyboardButton(f"{ch['name']}", callback_data=f"channel_{ch['id']}"))
        markup.add(InlineKeyboardButton("➕ አዲስ ቻናል ጨምር", callback_data="add_new"))
        bot.send_message(ADMIN_ID, "📢 VIP ቻናሎች:", reply_markup=markup)

    elif call.data.startswith("channel_"):
        ch_id = int(call.data.split("_")[1])
        ch_name = next((c["name"] for c in VIP_CHANNELS if c["id"]==ch_id), "Unknown")
        users = list(users_col.find({"channels.id": ch_id}))
        if not users:
            bot.send_message(ADMIN_ID, f"❌ {ch_name} ውስጥ ምንም አባል የለም.")
            return
        text = f"📋 {ch_name} ውስጥ አባላት:\n\n"
        for u in users:
            expiry_eth = eth_date(u.get("expiry",0))
            ch_link = next((c["link"] for c in u.get("channels",[]) if c["id"]==ch_id), "")
            text += f"👤 UserID: {u['user_id']} | እቅድ: {u.get('plan','N/A')} | ጊዜ ማብቂያ (ET): {expiry_eth}\n"
            text += f"   🔹 [የግብዣ አገናኝ]({ch_link})\n\n"
        bot.send_message(ADMIN_ID, text, parse_mode="Markdown")

    elif call.data == "add_new":
        bot.send_message(ADMIN_ID, "➕ አዲስ ቻናል መረጃ ላኩ (ID እና ስም). የinput flow እንደሚሰራ ይቀጥሉ.")

# ------------------- PLAN SELECT -------------------
@bot.callback_query_handler(func=lambda call: call.data.startswith("plan"))
def choose_payment(call):
    plan_key = call.data
    user_id = call.from_user.id
    users_col.update_one({"user_id": user_id}, {"$set":{"plan": plan_key}}, upsert=True)

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🏦 CBE ባንክ", callback_data="cbe"))
    markup.add(InlineKeyboardButton("🏦 አቢሲኒያ ባንክ", callback_data="aby"))
    markup.add(InlineKeyboardButton("📱 ቴሌቢር", callback_data="tele"))

    bot.send_message(call.message.chat.id, "💳 ገንዘብ መላኪያ ይምረጡ:", reply_markup=markup)

# ------------------- PAYMENT INFO -------------------
@bot.callback_query_handler(func=lambda call: call.data in ["cbe", "aby", "tele"])
def payment_info(call):
    if call.data=="cbe":
        text="🏦 CBE ባንክ\nስም: Getamesay Fikru\nመለያ: 1000355140206\n\n📸 Screenshot ይላኩ ከላኩ በኋላ"
    elif call.data=="aby":
        text="🏦 አቢሲኒያ ባንክ\nስም: Getamesay Fikru\nመለያ: 167829104\n\n📸 Screenshot ይላኩ ከላኩ በኋላ"
    else:
        text="📱 ቴሌቢር\nስም: Getamesay Fikru\nቁጥር: 0965979124\n\n📸 Screenshot ይላኩ ከላኩ በኋላ"

    msg = bot.send_message(call.message.chat.id, text)
    bot.register_next_step_handler(msg, get_screenshot)

# ------------------- SCREENSHOT -------------------
def get_screenshot(message):
    if message.content_type != 'photo':
        bot.send_message(message.chat.id, "📸 Screenshot እባክዎ ይላኩ")
        return
    bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ አረጋግጥ", callback_data=f"approve_{message.from_user.id}"))
    markup.add(InlineKeyboardButton("❌ አቁም", callback_data=f"reject_{message.from_user.id}"))
    bot.send_message(ADMIN_ID, f"💰 አዲስ ክፍያ\nUser ID: {message.from_user.id}", reply_markup=markup)
    bot.send_message(message.chat.id, "✅ የክፍያ ማስረጃዎ ተልኳል። እባክዎ ይጠብቁ።")

# ------------------- APPROVE / REJECT -------------------
@bot.callback_query_handler(func=lambda call: call.data.startswith("approve") or call.data.startswith("reject"))
def approve_reject(call):
    user_id = int(call.data.split("_")[1])
    if call.data.startswith("reject"):
        bot.send_message(user_id,"❌ ክፍያዎ አልተፈቀደም. እባክዎ እንደገና ይሞክሩ.")
        bot.edit_message_text("❌ ተጠቃሚ ተቋርጧል", call.message.chat.id, call.message.message_id)
        users_col.delete_one({"user_id": user_id})
        return

    user = users_col.find_one({"user_id": user_id})
    plan_key = user["plan"]
    plan = PLANS[plan_key]
    expiry = datetime.now() + timedelta(days=plan["duration"])
    expiry_ts = int(expiry.timestamp())
    links_markup = InlineKeyboardMarkup()
    for ch in VIP_CHANNELS:
        try:
            invite_link = bot.create_chat_invite_link(ch["id"], member_limit=1, expire_date=expiry_ts).invite_link
            links_markup.add(InlineKeyboardButton(f"☑️ ተቀላቀሉ {ch['name']}", url=invite_link))
        except Exception as e:
            print(f"Error creating invite link for {ch['name']}: {e}")
    links_markup.add(InlineKeyboardButton("✅ እንደገና / እንደቀረበ", url=f"https://t.me/{bot.get_me().username}?start"))
    bot.send_message(user_id,"🎉 ክፍያዎ ተረጋግጧል! ቻናሎቻችን ከታች ያገኙ:", reply_markup=links_markup)
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
            except Exception as e:
                print(f"Error removing user {user['user_id']} from {ch['name']}: {e}")
        try:
            bot.send_message(user["user_id"], "⚠️ የVIP ጊዜዎ አብቅቷል። 🔄 እንደገና ይምረጡ.")
        except Exception as e:
            print(f"Error sending message to {user['user_id']}: {e}")
        users_col.delete_one({"_id": user["_id"]})

# ------------------- ADMIN VIP LIST -------------------
@bot.message_handler(commands=['listvip'], func=lambda m: m.from_user.id==ADMIN_ID)
def list_vip(message):
    users = list(users_col.find())
    if not users: 
        bot.send_message(ADMIN_ID,"❌ ምንም VIP ተጠቃሚ አልተመዘገበም")
        return
    text = "📋 VIP ተጠቃሚዎች ዝርዝር:\n\n"
    for u in users: 
        text += f"👤 UserID: {u['user_id']} | እቅድ: {u.get('plan','N/A')} | ጊዜ ማብቂያ: {datetime.fromtimestamp(u.get('expiry',0)).strftime('%Y-%m-%d %H:%M')}\n"
    bot.send_message(ADMIN_ID,text)

# ------------------- RUN -------------------
if __name__=="__main__":
    keep_alive()
    scheduler = BackgroundScheduler()
    scheduler.add_job(kick_expired, 'interval', minutes=10)
    scheduler.start()
    bot.infinity_polling()
