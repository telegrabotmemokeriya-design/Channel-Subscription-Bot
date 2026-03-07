import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient
from datetime import datetime, timedelta
from ethiopian_date import EthiopianDateConverter
from flask import Flask
from threading import Thread

# ------------------- KEEP ALIVE -------------------
app = Flask('')
@app.route('/')
def home(): return "Bot is running"
def run_web(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
def keep_alive(): Thread(target=run_web, daemon=True).start()

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
    "plan1": {"duration": 30, "price": 200, "label": "🗣 1 ወር ➡️ 200 ብር", "text": "የ1 ወር"},
    "plan2": {"duration": 60, "price": 380, "label": "🗣 2 ወር ➡️ 380 ብር", "text": "የ2 ወር"},
    "plan3": {"duration": 90, "price": 550, "label": "🗣 3 ወር ➡️ 550 ብር", "text": "የ3 ወር"},
    "plan5": {"duration": 150, "price": 1050, "label": "🗣 5 ወር ➡️ 1050 ብር", "text": "የ5 ወር"},
    "plan12": {"duration": 365, "price": 2000, "label": "💎 1 አመት ➡️ 2000 ብር", "text": "የ1 አመት"}
}

# ------------------- HELPERS -------------------
def to_ethiopian(gregorian_ts):
    dt = datetime.fromtimestamp(gregorian_ts)
    conv = EthiopianDateConverter.to_ethiopian(dt.year, dt.month, dt.day)
    return f"{conv[2]}/{conv[1]}/{conv[0]}"

def get_channel_markup(user_id, expiry_ts):
    markup = InlineKeyboardMarkup()
    for ch in VIP_CHANNELS:
        try:
            invite = bot.create_chat_invite_link(ch["id"], member_limit=1, expire_date=int(expiry_ts))
            markup.add(InlineKeyboardButton(f"🔗 {ch['name']} ተቀላቀል", url=invite.invite_link))
        except:
            markup.add(InlineKeyboardButton(f"🔗 {ch['name']}", url="https://t.me/joinchat/example"))
    return markup

# ------------------- COMMANDS -------------------
@bot.message_handler(commands=["start"])
def start(message):
    user_id = message.from_user.id
    if user_id == ADMIN_ID:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📋 የደንበኞች ዝርዝር", callback_data="admin_list"))
        markup.add(InlineKeyboardButton("📢 መልዕክት ላክ (Broadcast)", callback_data="admin_bc"))
        bot.send_message(ADMIN_ID, "🛠 **የአድሚን መቆጣጠሪያ ፓነል**\nእንኳን ደህና መጡ ጌታዬ!", reply_markup=markup, parse_mode="Markdown")
        return

    markup = InlineKeyboardMarkup()
    for key, plan in PLANS.items():
        markup.add(InlineKeyboardButton(plan["label"], callback_data=key))
    bot.send_message(user_id, "👋 እንኳን ደህና መጡ! VIP ለመግባት ጥቅል ይምረጡ:", reply_markup=markup)

# ------------------- CALLBACKS -------------------
@bot.callback_query_handler(func=lambda call: True)
def router(call):
    user_id = call.from_user.id
    mid = call.message.message_id

    if call.data in PLANS:
        users_col.update_one({"user_id": user_id}, {"$set":{"plan": call.data, "username": call.from_user.username}}, upsert=True)
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🏦 CBE Bank", callback_data="p_cbe"),
                   InlineKeyboardButton("🏦 Abyssinia", callback_data="p_aby"))
        markup.add(InlineKeyboardButton("📱 Telebirr", callback_data="p_tele"))
        bot.edit_message_text("💳 እባክዎ የክፍያ አማራጭ ይምረጡ:", user_id, mid, reply_markup=markup)

    elif call.data.startswith("p_"):
        method = call.data.split("_")[1].upper()
        acc = "1000355140206 (CBE)" if method == "CBE" else "167829104 (ABY)" if method == "ABY" else "0965979124 (Telebirr)"
        bot.edit_message_text(f"🏦 **{method} ክፍያ መረጃ**\n\n👤 ስም: Getamesay Fikru\n🔢 ቁጥር: `{acc}`\n\n📸 የከፈሉበትን **Screenshot** እዚህ ይላኩ።", user_id, mid, parse_mode="Markdown")
        bot.register_next_step_handler(call.message, get_screenshot)

    elif call.data.startswith("approve_"):
        tid = int(call.data.split("_")[1])
        udata = users_col.find_one({"user_id": tid})
        
        if not udata or "plan" not in udata:
            bot.send_message(ADMIN_ID, "❌ ስህተት፡ የተጠቃሚው ፕላን አልተገኘም።")
            return

        plan = PLANS[udata["plan"]]
        exp_ts = (datetime.now() + timedelta(days=plan["duration"])).timestamp()
        users_col.update_one({"user_id": tid}, {"$set": {"expiry": exp_ts, "active": True}})
        
        bot.send_message(tid, f"🎉 አባልነትዎ ጸድቋል!\n📅 የሚያበቃው፡ {to_ethiopian(exp_ts)} (ኢትዮ አቆጣጠር)\n\nሊንኩን ተጭነው ይግቡ፡", reply_markup=get_channel_markup(tid, exp_ts))
        bot.edit_message_text(f"✅ ተጠቃሚ {tid} ጸድቋል", user_id, mid)

    elif call.data == "admin_list":
        users = list(users_col.find().sort("expiry", 1))
        if not users:
            bot.send_message(ADMIN_ID, "❌ እስካሁን ምንም ተጠቃሚ የለም።")
            return
        
        report = "👥 **የተጠቃሚዎች ዝርዝር**\n\n"
        for u in users:
            status = "🟢" if u.get("active") else "🔴"
            expiry = to_ethiopian(u['expiry']) if u.get('expiry') else "ያልተከፈለ"
            report += f"{status} @{u.get('username','N/A')} | `{u['user_id']}`\n📅 ማብቂያ፡ {expiry}\n\n"
        bot.send_message(ADMIN_ID, report, parse_mode="Markdown")

    elif call.data == "admin_bc":
        msg = bot.send_message(ADMIN_ID, "📝 ለሁሉም የሚላክ መልዕክት ይጻፉ።\n\nለማቋረጥ /cancel የሚለውን ይጫኑ።")
        bot.register_next_step_handler(msg, run_broadcast)

# ------------------- LOGIC -------------------
def get_screenshot(message):
    if not message.photo:
        bot.reply_to(message, "📸 እባክዎ ፎቶ (Screenshot) ይላኩ።")
        return
    bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ Approve", callback_data=f"approve_{message.from_user.id}"))
    bot.send_message(ADMIN_ID, f"💰 አዲስ ክፍያ ከ @{message.from_user.username}", reply_markup=markup)
    bot.send_message(message.chat.id, "✅ ማስረጃው ተልኳል! አድሚኑ እስኪያረጋግጥ ይጠብቁ።")

def run_broadcast(message):
    if message.text and (message.text.lower() == 'cancel' or message.text == '/cancel'):
        bot.send_message(ADMIN_ID, "❌ ስርጭቱ ተቋርጧል።")
        return
    
    all_users = users_col.find()
    s, f = 0, 0
    for u in all_users:
        try:
            bot.copy_message(u['user_id'], ADMIN_ID, message.message_id)
            s += 1
        except: f += 1
    bot.send_message(ADMIN_ID, f"📢 ስርጭት ተጠናቋል!\n✅ የደረሳቸው: {s}\n❌ የከሸፈባቸው: {f}")

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling()
