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
            markup.add(InlineKeyboardButton(f"{emoji} {ch['name']}", url=invite))
        except:
            markup.add(InlineKeyboardButton(f"{emoji} {ch['name']}", url="https://t.me/example"))
    markup.add(InlineKeyboardButton("🔄 ሁኔታውን አድስ (Refresh)", callback_data="refresh_links"))
    return markup

def to_ethiopian(gregorian_ts):
    dt = datetime.fromtimestamp(gregorian_ts)
    conv = EthiopianDateConverter.to_ethiopian(dt.year, dt.month, dt.day)
    return f"{conv[2]}/{conv[1]}/{conv[0]}"

# ------------------- COMMANDS -------------------
@bot.message_handler(commands=["start"])
def start(message):
    user_id = message.from_user.id
    if user_id == ADMIN_ID:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📋 የደንበኞች ዝርዝር", callback_data="admin_list"))
        bot.send_message(ADMIN_ID, "🛠 የአድሚን ፓነል", reply_markup=markup)
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
        users_col.update_one({"user_id": user_id}, {"$set":{"plan": call.data}}, upsert=True)
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🏦 CBE", callback_data="p_cbe"), 
                   InlineKeyboardButton("🏦 Abyssinia", callback_data="p_aby"),
                   InlineKeyboardButton("📱 Telebirr", callback_data="p_tele"))
        bot.edit_message_text("💳 የክፍያ አማራጭ ይምረጡ:", user_id, mid, reply_markup=markup)

    elif call.data.startswith("p_"):
        method = call.data.split("_")[1].upper()
        if method == "CBE":
            bank_info = "🏦 CBE ኢትዮጵያ ንግድ ባንክ\n👤 Getamesay Fikru\n🔢 `1000355140206`"
        elif method == "ABY":
            bank_info = "🏦 Abyssinia ባንክ\n👤 Getamesay Fikru\n🔢 `167829104`"
        else:
            bank_info = "📱 Telebirr (ቴሌብር)\n👤 Getamesay Fikru\n🔢 `0965979124`"
        
        bot.edit_message_text(f"{bank_info}\n\n📸 Screenshot ይላኩ።", user_id, mid, parse_mode="Markdown")
        bot.register_next_step_handler(call.message, get_screenshot)

    elif call.data.startswith("approve_"):
        tid = int(call.data.split("_")[1])
        udata = users_col.find_one({"user_id": tid})
        if udata and "plan" in udata:
            plan = PLANS[udata["plan"]]
            exp_ts = (datetime.now() + timedelta(days=plan["duration"])).timestamp()
            users_col.update_one({"user_id": tid}, {"$set": {"expiry": exp_ts, "active": True}})
            
            bot.send_message(tid, f"🎉 አባልነትዎ ጸድቋል!\n📅 ማብቂያ፡ {to_ethiopian(exp_ts)}\n\nቻናሎቹን ይቀላቀሉ፡", reply_markup=get_channel_markup(tid))
            bot.edit_message_text(f"✅ ተጠቃሚ {tid} ጸድቋል!", ADMIN_ID, mid)
            bot.answer_callback_query(call.id, "ጸድቋል!")

    elif call.data == "refresh_links":
        bot.edit_message_reply_markup(user_id, mid, reply_markup=get_channel_markup(user_id))
        bot.answer_callback_query(call.id, "ሁኔታው ታድሷል!")

    elif call.data.startswith("reject_"):
        tid = call.data.split("_")[1]
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🚫 ስህተት", callback_data=f"rj_wrong_{tid}"),
                   InlineKeyboardButton("📉 አነስተኛ", callback_data=f"rj_less_{tid}"))
        bot.edit_message_text("ምክንያት ይምረጡ፡", ADMIN_ID, mid, reply_markup=markup)

    elif call.data.startswith("rj_"):
        _, r, tid = call.data.split("_")
        reason = "ደረሰኙ ስህተት ነው።" if r == "wrong" else "የከፈሉት መጠን ያንሳል።"
        bot.send_message(int(tid), f"❌ ውድቅ ተደርጓል፡ {reason}")
        bot.edit_message_text(f"🔴 ተጠቃሚ {tid} ውድቅ ተደርጓል", ADMIN_ID, mid)

# ------------------- LOGIC -------------------
def get_screenshot(message):
    if not message.photo:
        bot.reply_to(message, "📸 እባክዎ Screenshot ይላኩ።")
        bot.register_next_step_handler(message, get_screenshot)
        return
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ Approve", callback_data=f"approve_{message.from_user.id}"),
               InlineKeyboardButton("❌ Reject", callback_data=f"reject_{message.from_user.id}"))
    
    bot.send_message(ADMIN_ID, f"💰 አዲስ ክፍያ ከ @{message.from_user.username} (ID: `{message.from_user.id}`)", parse_mode="Markdown")
    bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
    bot.send_message(ADMIN_ID, "ድርጊት ይምረጡ፦", reply_markup=markup)
    bot.send_message(message.chat.id, "✅ ተልኳል! በ1 ሰዓት ውስጥ ይረጋገጣል።")

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling(timeout=60, long_polling_timeout=60)
