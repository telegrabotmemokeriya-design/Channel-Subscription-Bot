import os
import telebot
import time
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
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
channels_col = db["channels"]
settings_col = db["settings"]

PLANS = {
    "plan1": {"duration": 30, "price": 200, "name": "የ 1 ወር (200 ብር)"},
    "plan2": {"duration": 60, "price": 380, "name": "የ 2 ወር (380 ብር)"},
    "plan3": {"duration": 90, "price": 550, "name": "የ 3 ወር (550 ብር)"},
    "plan5": {"duration": 150, "price": 1050, "name": "የ 5 ወር (1050 ብር)"},
    "plan12": {"duration": 365, "price": 2000, "name": "የ 1 አመት (2000 ብር)"}
}

# ------------------- HELPERS -------------------
def to_ethiopian(ts):
    try:
        dt = datetime.fromtimestamp(ts)
        conv = EthiopianDateConverter.to_ethiopian(dt.year, dt.month, dt.day)
        months = ["", "መስከረም", "ጥቅምት", "ህዳር", "ታህሳስ", "ጥር", "የካቲት", "መጋቢት", "ሚያዝያ", "ግንቦት", "ሰኔ", "ሐምሌ", "ነሐሴ", "ጳጉሜ"]
        return f"{months[conv.month]} / {conv.day} / {conv.year}"
    except: return "ያልታወቀ"

def get_channel_markup(user_id):
    markup = InlineKeyboardMarkup()
    for ch in list(channels_col.find()):
        try:
            member = bot.get_chat_member(ch["id"], user_id)
            status = "✅" if member.status in ['member', 'administrator', 'creator'] else "☑️"
            invite = bot.create_chat_invite_link(ch["id"], member_limit=1).invite_link
            markup.add(InlineKeyboardButton(f"{status} {ch['name']}", url=invite))
        except: continue
    markup.add(InlineKeyboardButton("🔄 ሁሉንም ቻናል መግባትዎን ያረጋግጡ (Refresh)", callback_data="refresh_links"))
    return markup

# ------------------- EXPIRY CHECKER (ራስ-ሰር ማስወገጃ) -------------------
def check_expiry_loop():
    while True:
        try:
            now = datetime.now().timestamp()
            # ጊዜያቸው ያለፈባቸው ግን አሁንም Active የሆኑ ተጠቃሚዎች
            expired_users = users_col.find({"active": True, "expiry": {"$lt": now}})
            
            for u in expired_users:
                uid = u["user_id"]
                # ከሁሉም ቻናሎች ማስወጣት (Ban and Unban to remove)
                for ch in list(channels_col.find()):
                    try:
                        bot.ban_chat_member(ch["id"], uid)
                        bot.unban_chat_member(ch["id"], uid)
                    except Exception as e:
                        print(f"Error kicking {uid} from {ch['id']}: {e}")
                
                # ሁኔታቸውን ወደ False መቀየር
                users_col.update_one({"user_id": uid}, {"$set": {"active": False}})
                
                # ለተጠቃሚው መልዕክት መላክ
                msg = "⚠️ የGett VIP አገልግሎት ጊዜዎ አብቅቷል! ስለዚህ ከቻናሎች ተወግደዋል።\n\nእባክዎ አገልግሎቱን ለመቀጠል ደግመው ይክፈሉ እና አባል ይሁኑ።"
                try: bot.send_message(uid, msg)
                except: pass
        except Exception as e:
            print(f"Loop Error: {e}")
        time.sleep(3600) # በየ 1 ሰዓቱ ያረጋግጣል

# ------------------- COMMANDS -------------------
@bot.message_handler(commands=["start"])
def start(message):
    uid = message.from_user.id
    bot.send_message(uid, "እንኳን ወደ Gett VIP Bot በሰላም መጡ!", reply_markup=main_keyboard())
    if uid == ADMIN_ID:
        adm = InlineKeyboardMarkup()
        adm.add(InlineKeyboardButton("📋 የደንበኞች ዝርዝር", callback_data="admin_list"), InlineKeyboardButton("📢 ብሮድካስት", callback_data="admin_bc"))
        adm.add(InlineKeyboardButton("➕ ቻናል ጨምር", callback_data="add_channel"), InlineKeyboardButton("➖ ቻናል ቀንስ", callback_data="rem_list"))
        bot.send_message(uid, "🛠 አድሚን ፓነል፡", reply_markup=adm)

@bot.message_handler(func=lambda m: m.text == "👤 የእኔ አገልግሎት")
def my_service(message):
    u = users_col.find_one({"user_id": message.from_user.id})
    if not u or not u.get("active"):
        bot.send_message(message.chat.id, "ሰላም፣ የGett VIP አባል አይደሉም። እባክዎ መጀመሪያ ይክፈሉ ወይም ጊዜዎ አልቋል።")
        return
    txt = (f"👤 ስም: {message.from_user.first_name}\n"
           f"💰 ጥቅል: {PLANS.get(u.get('plan'), {'name':'N/A'})['name']}\n"
           f"⏳ ማብቂያ: {to_ethiopian(u['expiry'])}\n\n"
           f"☑️ - Channel ውስጥ አልገባችሁም\n✅ - Channel ውስጥ ገብታችኋል")
    bot.send_message(message.chat.id, txt, reply_markup=get_channel_markup(u['user_id']))

# ------------------- LOGIC -------------------
# (ሌሎቹ ክፍሎች - Approval, Reject, Payment - ልክ እንደበፊቱ ይቀጥላሉ)

def main_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton("💎 VIP ለመመዝገብ"), KeyboardButton("👤 የእኔ አገልግሎት"))
    markup.add(KeyboardButton("🎬 Addis Film Poster"), KeyboardButton("📜 VIP Channel ዝርዝር"))
    markup.add(KeyboardButton("🆘 እገዛ (Help)"))
    return markup

# ------------------- STARTUP -------------------
if __name__ == "__main__":
    keep_alive()
    # ራስ-ሰር ማስወገጃውን በሌላ Thread መጀመር
    Thread(target=check_expiry_loop, daemon=True).start()
    bot.infinity_polling()
