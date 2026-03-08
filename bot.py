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
channels_col = db["channels"] # አዳዲስ ቻናሎች የሚመዘገቡበት

PLANS = {
    "plan1": {"duration": 30, "price": 200, "name": "የ 1 ወር (200 ብር)"},
    "plan2": {"duration": 60, "price": 380, "name": "የ 2 ወር (380 ብር)"},
    "plan3": {"duration": 90, "price": 550, "name": "የ 3 ወር (550 ብር)"},
    "plan5": {"duration": 150, "price": 1050, "name": "የ 5 ወር (1050 ብር)"},
    "plan12": {"duration": 365, "price": 2000, "name": "የ 1 አመት (2000 ብር)"}
}

# ------------------- HELPERS -------------------
def get_all_channels():
    # በኮድ ውስጥ ያሉትን እና በዳታቤዝ የተጨመሩትን አንድ ላይ ያመጣል
    base_channels = [
        {"id": -1003128362218, "name": "Gett Vip Channel 1"},
        {"id": -1002978674693, "name": "Gett Vip Channel 2"},
        {"id": -1003009075671, "name": "Gett Vip Channel 3"}
    ]
    db_channels = list(channels_col.find({}, {"_id": 0}))
    return base_channels + db_channels

def check_join_status(user_id, channel_id):
    try:
        member = bot.get_chat_member(channel_id, user_id)
        return "✅" if member.status in ['member', 'administrator', 'creator'] else "☑️"
    except: return "☑️"

def get_channel_markup(user_id):
    markup = InlineKeyboardMarkup()
    for ch in get_all_channels():
        status = check_join_status(user_id, ch["id"])
        try:
            invite = bot.create_chat_invite_link(ch["id"], member_limit=1).invite_link
            markup.add(InlineKeyboardButton(f"{status} {ch['name']}", url=invite))
        except: continue
    markup.add(InlineKeyboardButton("🔄 ሁኔታውን አድስ (Refresh)", callback_data="refresh_links"))
    return markup

def to_ethiopian_format(ts):
    try:
        dt = datetime.fromtimestamp(ts)
        conv = EthiopianDateConverter.to_ethiopian(dt.year, dt.month, dt.day)
        months = ["", "መስከረም", "ጥቅምት", "ህዳር", "ታህሳስ", "ጥር", "የካቲት", "መጋቢት", "ሚያዝያ", "ግንቦት", "ሰኔ", "ሐምሌ", "ነሐሴ", "ጳጉሜ"]
        return f"{months[conv.month]} / {conv.day} / {conv.year}"
    except: return "ያልታወቀ"

# ------------------- CHECKER -------------------
def check_subscriptions():
    while True:
        try:
            now = datetime.now().timestamp()
            expired = users_col.find({"active": True, "expiry": {"$lt": now}})
            for u in expired:
                for ch in get_all_channels():
                    try:
                        bot.ban_chat_member(ch["id"], u["user_id"])
                        bot.unban_chat_member(ch["id"], u["user_id"])
                    except: pass
                users_col.update_one({"user_id": u["user_id"]}, {"$set": {"active": False}})
                bot.send_message(u["user_id"], "⚠️ የአገልግሎት ጊዜዎ አብቅቷል! ለመቀጠል እባክዎ በድጋሚ ጥቅል ይግዙ።")
        except: pass
        time.sleep(3600)

# ------------------- COMMANDS -------------------
@bot.message_handler(commands=["start"])
def start(message):
    uid = message.from_user.id
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("💎 VIP ለመመዝገብ"), KeyboardButton("👤 የእኔ አገልግሎት"))
    
    if uid == ADMIN_ID:
        bot.send_message(uid, "🛠 የአድሚን ፓነል ተከፍቷል።", reply_markup=markup)
        adm_in = InlineKeyboardMarkup()
        adm_in.add(InlineKeyboardButton("📋 የደንበኞች ዝርዝር", callback_data="admin_list"),
                   InlineKeyboardButton("📢 ብሮድካስት", callback_data="admin_bc"))
        adm_in.add(InlineKeyboardButton("➕ ቻናል ጨምር", callback_data="add_channel"),
                   InlineKeyboardButton("📺 ቻናሎች", callback_data="view_channels"))
        bot.send_message(uid, "የአድሚን አማራጮች፦", reply_markup=adm_in)
    else:
        bot.send_message(uid, "👋 እንኳን ደህና መጡ! VIP ለመመዝገብ ከታች ያለውን በተን ይጫኑ።", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "💎 VIP ለመመዝገብ")
def vip_reg(message):
    send_plans(message.from_user.id, None, True)

@bot.message_handler(func=lambda m: m.text == "👤 የእኔ አገልግሎት")
def my_service(message):
    u = users_col.find_one({"user_id": message.from_user.id})
    if not u or not u.get("active"):
        bot.reply_to(message, "❌ ገና አልተመዘገቡም ወይም አገልግሎትዎ አብቅቷል።")
        return
    
    txt = (f"👤 ስም: {message.from_user.first_name}\n"
           f"📅 የገቡበት: {to_ethiopian_format(u.get('joined_at', time.time()))}\n"
           f"⏳ የሚያበቃው: {to_ethiopian_format(u['expiry'])}\n\n"
           f"የእርስዎ የVIP ሊንኮች (ለእርስዎ ብቻ የሚሰሩ) 👇")
    bot.send_message(message.from_user.id, txt, reply_markup=get_channel_markup(message.from_user.id))

# ------------------- CALLBACKS -------------------
@bot.callback_query_handler(func=lambda call: True)
def router(call):
    uid, mid = call.from_user.id, call.message.message_id

    if call.data in PLANS:
        users_col.update_one({"user_id": uid}, {"$set":{"pending_plan": call.data, "username": call.from_user.username}}, upsert=True)
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🏦 CBE", callback_data="p_cbe"), 
                   InlineKeyboardButton("🏦 Abyssinia", callback_data="p_aby"),
                   InlineKeyboardButton("📱 Telebirr", callback_data="p_tele"))
        markup.add(InlineKeyboardButton("🔙 ተመለስ", callback_data="back_to_plans"))
        bot.edit_message_text(f"✅ {PLANS[call.data]['name']} መርጠዋል። ባንክ ይምረጡ፦", uid, mid, reply_markup=markup)

    elif call.data == "admin_list":
        users = users_col.find({"active": True})
        bot.send_message(ADMIN_ID, "📋 **የደንበኞች ዝርዝር፦**")
        for u in users:
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🚫 Ban User", callback_data=f"ban_{u['user_id']}"))
            info = f"👤 [{u['user_id']}](tg://user?id={u['user_id']})\n⏳ ያበቃል: {to_ethiopian_format(u['expiry'])}"
            bot.send_message(ADMIN_ID, info, parse_mode="Markdown", reply_markup=markup)

    elif call.data.startswith("ban_"):
        target = int(call.data.split("_")[1])
        for ch in get_all_channels():
            try: bot.ban_chat_member(ch["id"], target)
            except: pass
        users_col.update_one({"user_id": target}, {"$set": {"active": False}})
        bot.send_message(target, "🚫 ከአድሚን በተሰጠ ትዕዛዝ ከVIP ታግደዋል።")
        bot.answer_callback_query(call.id, "ተጠቃሚው ታግዷል")

    elif call.data == "add_channel":
        msg = bot.send_message(ADMIN_ID, "📢 እባክዎ አዲስ ሊጨምሩት የሚፈልጉትን ቻናል አንድ መልዕክት ወደዚህ Forward ያድርጉልኝ። (ቦቱ በቻናሉ አድሚን መሆን አለበት)")
        bot.register_next_step_handler(msg, process_channel_add)

    elif call.data == "view_channels":
        markup = InlineKeyboardMarkup()
        for ch in get_all_channels():
            try:
                link = bot.export_chat_invite_link(ch["id"])
                markup.add(InlineKeyboardButton(f"📺 {ch['name']}", url=link))
            except: continue
        bot.send_message(ADMIN_ID, "የተመዘገቡ ቻናሎች፦", reply_markup=markup)

    elif call.data.startswith("approve_"):
        p = call.data.split("_")
        target_id, pk = int(p[1]), p[2]
        plan = PLANS[pk]
        exp = (datetime.now() + timedelta(days=plan["duration"])).timestamp()
        users_col.update_one({"user_id": target_id}, {"$set": {"expiry": exp, "active": True, "plan": pk, "joined_at": time.time()}})
        
        u_info = bot.get_chat(target_id)
        name = u_info.first_name if u_info.first_name else "ተጠቃሚ"
        msg = (f"ወድ : {name}\n\n🧧{plan['name']} ✔️ ከፍለዋል ።\n🎉 ክፍያዎ ተረጋግጦ የ Gett Vip ⚜️ አባል ሆነዋል! \n\n"
               f"🗓️ አገልግሎቱ የሚያበቃው - {to_ethiopian_format(exp)}\n\n"
               f"አገልግሎታችንን ስለተጠቀሙ እናመሰግናለን። ⭐\n\nቻናሎቹን ለመቀላቀል ከታች ያሉትን በተኖች ይጠቀሙ፡\nሁሉንም ቻናል መቀላቀሎን እንዳይረሱ ✅")
        bot.send_message(target_id, msg, reply_markup=get_channel_markup(target_id))
        bot.edit_message_text(f"✅ ተጠቃሚ {target_id} ጸድቋል!", ADMIN_ID, mid)

    elif call.data == "cancel_send":
        bot.edit_message_text("❌ ተሰርዟል።", uid, mid)
        start(call.message)

    elif call.data.startswith("p_"):
        u_data = users_col.find_one({"user_id": uid})
        plan_name = PLANS[u_data['pending_plan']]['name'] if u_data else "VIP"
        bank_info = get_bank_info(call.data.split("_")[1].upper())
        bot.edit_message_text(f"💎 ጥቅል: {plan_name}\n\n{bank_info}\n\n📸 የደረሰኙን ፎቶ ይላኩ", uid, mid, parse_mode="Markdown")
        bot.register_next_step_handler(call.message, get_screenshot)

    elif call.data == "refresh_links":
        bot.edit_message_reply_markup(uid, mid, reply_markup=get_channel_markup(uid))

# ------------------- LOGIC -------------------
def process_channel_add(message):
    if not message.forward_from_chat:
        bot.reply_to(message, "❌ ስህተት፡ እባክዎ መልዕክት ከቻናል ፎርዋርድ ያድርጉ።")
        return
    ch_id = message.forward_from_chat.id
    ch_name = message.forward_from_chat.title
    if channels_col.find_one({"id": ch_id}):
        bot.reply_to(message, "⚠️ ይህ ቻናል ቀድሞ ተመዝግቧል።")
    else:
        channels_col.insert_one({"id": ch_id, "name": ch_name})
        bot.reply_to(message, f"✅ ቻናል '{ch_name}' በትክክል ተመዝግቧል!")

def get_screenshot(message):
    if message.text == "/start" or (message.text and "ተመለስ" in message.text): return
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("❌ ሰርዝ (Cancel)", callback_data="cancel_send"))
    
    if not message.photo:
        bot.send_message(message.chat.id, "⚠️ እባክዎ የደረሰኙን Screenshot (ፎቶ) ብቻ ይላኩ። ጽሁፍ አይቀበልም።", reply_markup=markup)
        bot.register_next_step_handler(message, get_screenshot)
        return
    
    uid = message.from_user.id
    u_data = users_col.find_one({"user_id": uid})
    pk = u_data["pending_plan"] if u_data else "plan1"
    
    adm_markup = InlineKeyboardMarkup()
    adm_markup.add(InlineKeyboardButton("✅ Approve", callback_data=f"approve_{uid}_{pk}"),
                   InlineKeyboardButton("❌ Reject", callback_data=f"reject_{uid}"))
    
    bot.send_message(ADMIN_ID, f"💰 ክፍያ ከ @{message.from_user.username} (ID: `{uid}`)\n💎 ጥቅል: {PLANS[pk]['name']}")
    bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
    bot.send_message(ADMIN_ID, "ያረጋግጡ፡", reply_markup=adm_markup)
    bot.send_message(message.chat.id, "✅ ተልኳል! አድሚኑ እስኪያረጋግጥ ድረስ ይጠብቁ።")

def get_bank_info(m):
    if m == "CBE": return "🏦 CBE ኢትዮጵያ ንግድ ባንክ\n👤 ስም: Getamesay Fikru\n🔢 Acc: `1000355140206`"
    if m == "ABY": return "🏦 Abyssinia ባንክ\n👤 ስም: Getamesay Fikru\n🔢 Acc: `167829104`"
    return "📱 Telebirr (ቴሌብር)\n👤 ስም: Getamesay Fikru\n🔢 ስልክ: `0965979124`"

def send_plans(uid, mid, is_new):
    markup = InlineKeyboardMarkup()
    for k, p in PLANS.items(): markup.add(InlineKeyboardButton(f"🗣 {p['name']}", callback_data=k))
    txt = "👋 VIP ለመግባት ጥቅል ይምረጡ:"
    if is_new: bot.send_message(uid, txt, reply_markup=markup)
    else: bot.edit_message_text(txt, uid, mid, reply_markup=markup)

if __name__ == "__main__":
    keep_alive()
    Thread(target=check_subscriptions, daemon=True).start()
    bot.remove_webhook()
    time.sleep(1)
    bot.infinity_polling(timeout=15)
