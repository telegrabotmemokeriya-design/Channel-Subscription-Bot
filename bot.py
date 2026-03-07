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
    "plan1": {"duration": 30, "price": 200, "label": "🗣 1 ወር ➡️ 200 ብር", "text": "የ1 ወር"},
    "plan2": {"duration": 60, "price": 380, "label": "🗣 2 ወር ➡️ 380 ብር", "text": "የ2 ወር"},
    "plan3": {"duration": 90, "price": 550, "label": "🗣 3 ወር ➡️ 550 ብር", "text": "የ3 ወር"},
    "plan5": {"duration": 150, "price": 1050, "label": "🗣 5 ወር ➡️ 1050 ብር", "text": "የ5 ወር"},
    "plan12": {"duration": 365, "price": 2000, "label": "💎 1 አመት ➡️ 2000 ብር", "text": "የ1 አመት"}
}

# ------------------- AUTO-EXPIRY LOGIC (ባለቤት ማስወጫ) -------------------
def check_expiries():
    """በየ 1 ሰዓቱ ዳታቤዙን እየፈተሸ ጊዜው ያለፈበትን ሰው ያስወጣል"""
    while True:
        try:
            now = datetime.now().timestamp()
            # ጊዜያቸው ያለፈባቸውና ገና ያልተወገዱ (active: True) የሆኑትን ፈልግ
            expired_users = users_col.find({"expiry": {"$lt": now}, "active": True})
            
            for user in expired_users:
                user_id = user["user_id"]
                for ch in VIP_CHANNELS:
                    try:
                        bot.ban_chat_member(ch["id"], user_id)
                        bot.unban_chat_member(ch["id"], user_id) # ለወደፊት ተመልሰው መግባት እንዲችሉ
                    except Exception as e:
                        print(f"Error kicking {user_id}: {e}")
                
                # ሁኔታቸውን ወደ መደበኛ ቀይር
                users_col.update_one({"user_id": user_id}, {"$set": {"active": False}})
                try:
                    bot.send_message(user_id, "⚠️ የቪአይፒ አባልነትዎ ጊዜ ተጠናቅቋል። እባክዎ በድጋሚ በመክፈል አባልነትዎን ያድሱ።")
                except: pass
                print(f"User {user_id} has been removed due to expiry.")
                
        except Exception as e:
            print(f"Expiry Checker Error: {e}")
        
        time.sleep(3600) # በየ 1 ሰዓቱ አንዴ ቼክ ያደርጋል

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
            markup.add(InlineKeyboardButton(f"🔗 {ch['name']}", url="https://t.me/example"))
    return markup

def get_start_markup():
    markup = InlineKeyboardMarkup()
    for key, plan in PLANS.items():
        markup.add(InlineKeyboardButton(plan["label"], callback_data=key))
    return markup

# ------------------- COMMANDS -------------------
@bot.message_handler(commands=["start"])
def start(message):
    user_id = message.from_user.id
    if user_id == ADMIN_ID:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📋 የደንበኞች ዝርዝር", callback_data="admin_list"))
        markup.add(InlineKeyboardButton("📢 መልዕክት ላክ (Broadcast)", callback_data="admin_bc"))
        bot.send_message(ADMIN_ID, "🛠 **የአድሚን ፓነል**", reply_markup=markup)
        return
    bot.send_message(user_id, "👋 እንኳን ደህና መጡ! VIP ለመግባት ጥቅል ይምረጡ:", reply_markup=get_start_markup())

# ------------------- CALLBACKS -------------------
@bot.callback_query_handler(func=lambda call: True)
def router(call):
    user_id = call.from_user.id
    mid = call.message.message_id

    if call.data in PLANS:
        users_col.update_one({"user_id": user_id}, {"$set":{"plan": call.data, "username": call.from_user.username}}, upsert=True)
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🏦 CBE", callback_data="p_cbe"), InlineKeyboardButton("🏦 Abyssinia", callback_data="p_aby"))
        markup.add(InlineKeyboardButton("📱 Telebirr", callback_data="p_tele"))
        markup.add(InlineKeyboardButton("🔙 ተመለስ", callback_data="back_to_plans"))
        bot.edit_message_text("💳 የክፍያ አማራጭ ይምረጡ:", user_id, mid, reply_markup=markup)

    elif call.data == "back_to_plans":
        bot.edit_message_text("👋 VIP ለመግባት ጥቅል ይምረጡ:", user_id, mid, reply_markup=get_start_markup())

    elif call.data.startswith("p_"):
        method = call.data.split("_")[1].upper()
        acc = "1000355140206 (CBE)" if method == "CBE" else "167829104 (ABY)" if method == "ABY" else "0965979124 (Tele)"
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 ተመለስ", callback_data="back_to_plans"))
        bot.edit_message_text(f"🏦 **{method} መረጃ**\n\n🔢 ቁጥር: `{acc}`\n\n📸 Screenshot ይላኩ።", user_id, mid, parse_mode="Markdown", reply_markup=markup)
        bot.register_next_step_handler(call.message, get_screenshot)

    elif call.data.startswith("approve_"):
        tid = int(call.data.split("_")[1])
        udata = users_col.find_one({"user_id": tid})
        if not udata or "plan" not in udata:
            bot.answer_callback_query(call.id, "❌ ፕላን አልተገኘም!", show_alert=True)
            return
        plan = PLANS[udata["plan"]]
        exp_ts = (datetime.now() + timedelta(days=plan["duration"])).timestamp()
        users_col.update_one({"user_id": tid}, {"$set": {"expiry": exp_ts, "active": True}})
        bot.send_message(tid, f"🎉 አባልነትዎ ጸድቋል!\n📅 ማብቂያ፡ {to_ethiopian(exp_ts)}", reply_markup=get_channel_markup(tid, exp_ts))
        bot.edit_message_text(f"✅ ተጠቃሚ {tid} ጸድቋል!", ADMIN_ID, mid)

    elif call.data.startswith("reject_"):
        tid = call.data.split("_")[1]
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🚫 የተሳሳተ ደረሰኝ", callback_data=f"rj_wrong_{tid}"))
        markup.add(InlineKeyboardButton("📉 የብር መጠን ያንሳል", callback_data=f"rj_less_{tid}"))
        bot.edit_message_text("❌ ውድቅ የሚደረግበት ምክንያት ይምረጡ፡", ADMIN_ID, mid, reply_markup=markup)

    elif call.data.startswith("rj_"):
        _, reason, tid = call.data.split("_")
        msg = "❌ ይቅርታ፣ ደረሰኝዎ ተቀባይነት አላገኘም።\n\nምክንያት፡ "
        msg += "ደረሰኙ ትክክል አይደለም።" if reason == "wrong" else "የከፈሉት መጠን አያንስም።"
        try:
            bot.send_message(int(tid), msg)
            bot.edit_message_text(f"🔴 ተጠቃሚ {tid} ውድቅ ተደርጓል", ADMIN_ID, mid)
        except: pass

    elif call.data == "admin_list":
        users = list(users_col.find().sort("expiry", 1))
        report = "👥 ተጠቃሚዎች:\n\n" + "\n".join([f"@{u.get('username','N/A')} | {to_ethiopian(u.get('expiry', 0)) if u.get('expiry') else 'Pending'}" for u in users])
        bot.send_message(ADMIN_ID, report if users else "ምንም ተጠቃሚ የለም")

    elif call.data == "admin_bc":
        msg = bot.send_message(ADMIN_ID, "📝 መልዕክት ይጻፉ (ለማቋረጥ /cancel)፡")
        bot.register_next_step_handler(msg, run_broadcast)

# ------------------- LOGIC -------------------
def get_screenshot(message):
    if message.text == "/start":
        start(message)
        return
    if not message.photo:
        bot.reply_to(message, "📸 እባክዎ ደረሰኝ (Screenshot) ይላኩ።")
        bot.register_next_step_handler(message, get_screenshot)
        return

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ Approve", callback_data=f"approve_{message.from_user.id}"),
               InlineKeyboardButton("❌ Reject", callback_data=f"reject_{message.from_user.id}"))
    bot.send_message(ADMIN_ID, f"💰 **ክፍያ ከ @{message.from_user.username}**", reply_markup=markup)
    bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
    bot.send_message(message.chat.id, "✅ ተልኳል! ከ1 ሰዓት ባልበለጠ ጊዜ ውስጥ ይረጋገጣል።")

def run_broadcast(message):
    if message.text and (message.text.lower() == 'cancel' or message.text == '/cancel'):
        bot.send_message(ADMIN_ID, "❌ ስርጭቱ ተቋርጧል")
        return
    all_users = users_col.find()
    s = 0
    for u in all_users:
        try:
            bot.copy_message(u['user_id'], ADMIN_ID, message.message_id)
            s += 1
        except: pass
    bot.send_message(ADMIN_ID, f"📢 ለ {s} ሰዎች ተልኳል")

if __name__ == "__main__":
    keep_alive()
    # ራስ-ሰር ማስወጫውንThread አስነሳ
    Thread(target=check_expiries, daemon=True).start()
    bot.infinity_polling()            bot.copy_message(u['user_id'], ADMIN_ID, message.message_id)
            s += 1
        except: f += 1
    bot.send_message(ADMIN_ID, f"📢 ስርጭት ተጠናቋል!\n✅ የደረሳቸው: {s}\n❌ የከሸፈባቸው: {f}")

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling()
