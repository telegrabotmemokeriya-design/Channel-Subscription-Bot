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
    "plan1": {"duration": 30, "price": 200, "name": "የ 1 ወር (200 ብር)"},
    "plan2": {"duration": 60, "price": 380, "name": "የ 2 ወር (380 ብር)"},
    "plan3": {"duration": 90, "price": 550, "name": "የ 3 ወር (550 ብር)"},
    "plan5": {"duration": 150, "price": 1050, "name": "የ 5 ወር (1050 ብር)"},
    "plan12": {"duration": 365, "price": 2000, "name": "የ 1 አመት (2000 ብር)"}
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
    markup.add(InlineKeyboardButton("🔄 ሁኔታውን አድስ (Refresh Status)", callback_data="refresh_links"))
    return markup

def to_ethiopian(ts):
    dt = datetime.fromtimestamp(ts)
    conv = EthiopianDateConverter.to_ethiopian(dt.year, dt.month, dt.day)
    return f"{conv[2]}/{conv[1]}/{conv[0]}"

# ------------------- COMMANDS -------------------
@bot.message_handler(commands=["start"])
def start(message):
    uid = message.from_user.id
    if uid == ADMIN_ID:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📋 የደንበኞች ዝርዝር", callback_data="admin_list"))
        markup.add(InlineKeyboardButton("📢 መልዕክት ላክ (Broadcast)", callback_data="admin_bc"))
        bot.send_message(ADMIN_ID, "🛠 **የአድሚን ፓነል**", reply_markup=markup)
        return
    
    send_plans(uid, message.message_id, is_new=True)

def send_plans(uid, mid, is_new=False):
    markup = InlineKeyboardMarkup()
    for key, plan in PLANS.items():
        markup.add(InlineKeyboardButton(f"🗣 {plan['name']}", callback_data=key))
    
    text = "👋 እንኳን ደህና መጡ! VIP ለመግባት ጥቅል ይምረጡ:"
    if is_new:
        bot.send_message(uid, text, reply_markup=markup)
    else:
        bot.edit_message_text(text, uid, mid, reply_markup=markup)

# ------------------- CALLBACKS -------------------
@bot.callback_query_handler(func=lambda call: True)
def router(call):
    uid = call.from_user.id
    mid = call.message.message_id

    if call.data in PLANS:
        plan = PLANS[call.data]
        users_col.update_one({"user_id": uid}, {"$set":{"pending_plan": call.data, "username": call.from_user.username}}, upsert=True)
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🏦 CBE", callback_data="p_cbe"), 
                   InlineKeyboardButton("🏦 Abyssinia", callback_data="p_aby"),
                   InlineKeyboardButton("📱 Telebirr", callback_data="p_tele"))
        markup.add(InlineKeyboardButton("🔙 ተመለስ (Back)", callback_data="back_to_plans"))
        
        bot.edit_message_text(f"✅ {plan['name']} ጥቅል መርጠዋል።\n\nእባክዎ ክፍያ የሚፈጽሙበትን ባንክ ይምረጡ፦", uid, mid, reply_markup=markup)

    elif call.data == "back_to_plans":
        send_plans(uid, mid)

    elif call.data.startswith("p_"):
        method = call.data.split("_")[1].upper()
        u_data = users_col.find_one({"user_id": uid})
        plan_name = PLANS[u_data['pending_plan']]['name'] if u_data else ""

        if method == "CBE":
            bank_info = "🏦 CBE ኢትዮጵያ ንግድ ባንክ\n👤 ስም: Getamesay Fikru\n🔢 Acc: `1000355140206`"
        elif method == "ABY":
            bank_info = "🏦 Abyssinia ባንክ (አቢሲኒያ)\n👤 ስም: Getamesay Fikru\n🔢 Acc: `167829104`"
        else:
            bank_info = "📱 Telebirr (ቴሌብር)\n👤 ስም: Getamesay Fikru\n🔢 ስልክ: `0965979124`"
        
        # የተጠቃሚውን ጥያቄ መሰረት ያደረገ ማስተካከያ
        bot.edit_message_text(f"💎 ጥቅል: {plan_name}\n\n{bank_info}\n\n📸 የከፈሉበትን Screenshot (የደረሰኙን ፎቶ) እዚህ ይላኩ", uid, mid, parse_mode="Markdown")
        bot.register_next_step_handler(call.message, get_screenshot)

    elif call.data.startswith("approve_"):
        tid = int(call.data.split("_")[1])
        u_data = users_col.find_one({"user_id": tid})
        if u_data:
            plan = PLANS[u_data["pending_plan"]]
            exp_ts = (datetime.now() + timedelta(days=plan["duration"])).timestamp()
            users_col.update_one({"user_id": tid}, {"$set": {"expiry": exp_ts, "active": True}})
            bot.send_message(tid, f"🎉 ክፍያዎ ተረጋግጦ አባልነትዎ ጸድቋል!\n📅 ማብቂያ፡ {to_ethiopian(exp_ts)}\n\nቻናሎቹን ለመቀላቀል ከታች ያሉትን በተኖች ይጠቀሙ፡", reply_markup=get_channel_markup(tid))
            bot.edit_message_text(f"✅ ተጠቃሚ {tid} ጸድቋል!", ADMIN_ID, mid)

    elif call.data.startswith("reject_"):
        tid = call.data.split("_")[1]
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🚫 የተሳሳተ ደረሰኝ", callback_data=f"rj_wrong_{tid}"),
                   InlineKeyboardButton("📉 መጠኑ ያንሳል", callback_data=f"rj_less_{tid}"))
        bot.edit_message_text("❌ ውድቅ የተደረገበት ምክንያት ይምረጡ፡", ADMIN_ID, mid, reply_markup=markup)

    elif call.data.startswith("rj_"):
        _, r, tid = call.data.split("_")
        reason = "ደረሰኙ ስህተት ነው።" if r == "wrong" else "የከፈሉት መጠን ያንሳል።"
        bot.send_message(int(tid), f"❌ ይቅርታ፣ ክፍያዎ ውድቅ ሆኗል!\nምክንያት፡ {reason}")
        bot.edit_message_text(f"🔴 ተጠቃሚ {tid} ውድቅ ተደርጓል", ADMIN_ID, mid)

    elif call.data == "refresh_links":
        bot.edit_message_reply_markup(uid, mid, reply_markup=get_channel_markup(uid))
        bot.answer_callback_query(call.id, "ሁኔታው ታድሷል!")

    elif call.data == "admin_bc":
        msg = bot.send_message(ADMIN_ID, "📝 መልዕክት ይጻፉ (ለመሰረዝ /cancel):")
        bot.register_next_step_handler(msg, run_broadcast)

# ------------------- LOGIC -------------------
def get_screenshot(message):
    if not message.photo:
        bot.reply_to(message, "📸 እባክዎ Screenshot (ፎቶ) ይላኩ።")
        bot.register_next_step_handler(message, get_screenshot)
        return
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ Approve", callback_data=f"approve_{message.from_user.id}"),
               InlineKeyboardButton("❌ Reject", callback_data=f"reject_{message.from_user.id}"))
    
    bot.send_message(ADMIN_ID, f"💰 ክፍያ ከ @{message.from_user.username} (ID: `{message.from_user.id}`)")
    bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
    bot.send_message(ADMIN_ID, "ያረጋግጡ፡", reply_markup=markup)
    bot.send_message(message.chat.id, "✅ ተልኳል! አድሚኑ እስኪያረጋግጥ ድረስ በትዕግስት ይጠብቁ።")

def run_broadcast(message):
    if message.text == "/cancel":
        bot.send_message(ADMIN_ID, "❌ ስርጭቱ ተቋርጧል።")
        return
    users = users_col.find()
    count = 0
    for u in users:
        try:
            bot.copy_message(u['user_id'], ADMIN_ID, message.message_id)
            count += 1
        except: pass
    bot.send_message(ADMIN_ID, f"📢 ለ {count} ተጠቃሚዎች ተልኳል።")

def check_expiries():
    while True:
        try:
            now = datetime.now().timestamp()
            expired = users_col.find({"expiry": {"$lt": now}, "active": True})
            for u in expired:
                uid = u["user_id"]
                for ch in VIP_CHANNELS:
                    try: bot.ban_chat_member(ch["id"], uid); bot.unban_chat_member(ch["id"], uid)
                    except: pass
                users_col.update_one({"user_id": uid}, {"$set": {"active": False}})
                bot.send_message(uid, "⚠️ የቪአይፒ ጊዜዎ ስላለቀ ከቻናል ተወግደዋል።")
        except: pass
        time.sleep(3600)

if __name__ == "__main__":
    keep_alive()
    Thread(target=check_expiries, daemon=True).start()
    bot.infinity_polling()    user = users_col.find_one({"user_id": user_id})
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
