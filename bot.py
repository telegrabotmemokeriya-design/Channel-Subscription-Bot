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
def get_setting(key, default=True):
    data = settings_col.find_one({"type": "config"})
    if data and key in data: return data[key]
    return default

def to_ethiopian_format(ts):
    try:
        dt = datetime.fromtimestamp(ts)
        conv = EthiopianDateConverter.to_ethiopian(dt.year, dt.month, dt.day)
        months = ["", "መስከረም", "ጥቅምት", "ህዳር", "ታህሳስ", "ጥር", "የካቲት", "መጋቢት", "ሚያዝያ", "ግንቦት", "ሰኔ", "ሐምሌ", "ነሐሴ", "ጳጉሜ"]
        return f"{months[conv.month]} / {conv.day} / {conv.year}"
    except: return "ያልታወቀ"

def get_channel_markup(user_id):
    markup = InlineKeyboardMarkup()
    channels = list(channels_col.find())
    for ch in channels:
        try:
            member = bot.get_chat_member(ch["id"], user_id)
            status = "✅" if member.status in ['member', 'administrator', 'creator'] else "☑️"
            # ለእያንዳንዱ ሰው ብቻ የሚሰራ One-time link
            invite = bot.create_chat_invite_link(ch["id"], member_limit=1).invite_link
            markup.add(InlineKeyboardButton(f"{status} {ch['name']}", url=invite))
        except: continue
    markup.add(InlineKeyboardButton("🔄 ሁኔታውን አድስ (Refresh)", callback_data="refresh_links"))
    return markup

# ------------------- KEYBOARDS -------------------
def main_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton("💎 VIP ለመመዝገብ"))
    markup.add(KeyboardButton("👤 የእኔ አገልግሎት"), KeyboardButton("🎬 Addis Film Poster"))
    markup.add(KeyboardButton("📜 VIP Channel ዝርዝር"), KeyboardButton("🆘 እገዛ (Help)"))
    return markup

# ------------------- COMMANDS -------------------
@bot.message_handler(commands=["start"])
def start(message):
    uid = message.from_user.id
    welcome_data = settings_col.find_one({"type": "welcome"})
    welcome_text = welcome_data["text"] if welcome_data else "እንኳን ወደ Gett VIP Bot በሰላም መጡ!"
    bot.send_message(uid, welcome_text, reply_markup=main_keyboard())
    
    if uid == ADMIN_ID:
        adm = InlineKeyboardMarkup()
        adm.add(InlineKeyboardButton("📋 የደንበኞች ዝርዝር", callback_data="admin_list"), 
                InlineKeyboardButton("📢 ብሮድካስት", callback_data="admin_bc"))
        adm.add(InlineKeyboardButton("➕ ቻናል ጨምር", callback_data="add_channel"), 
                InlineKeyboardButton("➖ ቻናል ቀንስ", callback_data="remove_ch_list"))
        rest_val = get_setting("restriction")
        adm.add(InlineKeyboardButton(f"🚫 Restriction: {'ON' if rest_val else 'OFF'}", callback_data="toggle_restrict"),
                InlineKeyboardButton("✍️ Welcome Msg", callback_data="edit_welcome"))
        bot.send_message(uid, "🛠 የአድሚን ፓነል፦", reply_markup=adm)

@bot.message_handler(func=lambda m: m.text == "🎬 Addis Film Poster")
def addis_film(message):
    bot.send_message(message.chat.id, "🎬 አዳዲስ የፊልም ፖስተሮችን ለማየት ሊንኩን ይጫኑ፦\nhttps://t.me/GettVipCenter")

@bot.message_handler(func=lambda m: m.text == "🆘 እገዛ (Help)")
def help_btn(message):
    bot.send_message(message.chat.id, "ለተጨማሪ ድጋፍ እና እገዛ አድሚኑን ያነጋግሩ፦\n👤 @gygett\n📞 +251951753306")

@bot.message_handler(func=lambda m: m.text == "📜 VIP Channel ዝርዝር")
def ch_list(message):
    channels = list(channels_col.find())
    if not channels:
        bot.send_message(message.chat.id, "በአሁኑ ሰዓት ምንም የተመዘገበ ቻናል የለም።")
        return
    txt = "📌 የVIP ቻናሎች ዝርዝር፦\n\n"
    for ch in channels: txt += f"🔹 {ch['name']}\n"
    bot.send_message(message.chat.id, txt)

@bot.message_handler(func=lambda m: m.text == "👤 የእኔ አገልግሎት")
def my_service(message):
    u = users_col.find_one({"user_id": message.from_user.id})
    if not u or not u.get("active"):
        bot.send_message(message.chat.id, f"ሰላም {message.from_user.first_name}፣ እስካሁን የGett VIP አባል አልሆኑም።")
        return
    txt = (f"👤 ስም: {message.from_user.first_name}\n"
           f"📅 የገቡበት: {to_ethiopian_format(u.get('joined_at', 0))}\n"
           f"⏳ የሚያበቃው: {to_ethiopian_format(u['expiry'])}\n\n"
           f"✅ Channel ገብታችኋል ማለት ነው\n☑️ Channel ውስጥ አልገባችሁም ማለት ነው")
    # Restriction በሊንኮች ላይ ብቻ እንዲሆን
    bot.send_message(message.chat.id, txt, reply_markup=get_channel_markup(message.from_user.id), protect_content=get_setting("restriction"))

@bot.message_handler(func=lambda m: m.text == "💎 VIP ለመመዝገብ")
def vip_reg(message):
    markup = InlineKeyboardMarkup()
    for k, p in PLANS.items(): markup.add(InlineKeyboardButton(f"🗣 {p['name']}", callback_data=k))
    bot.send_message(message.chat.id, "👋 VIP ለመግባት ጥቅል ይምረጡ:", reply_markup=markup)

# ------------------- CALLBACKS -------------------
@bot.callback_query_handler(func=lambda call: True)
def router(call):
    uid, mid = call.from_user.id, call.message.message_id

    if call.data in PLANS:
        users_col.update_one({"user_id": uid}, {"$set":{"pending_plan": call.data}}, upsert=True)
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🏦 CBE", callback_data="p_cbe"), 
                   InlineKeyboardButton("🏦 Abyssinia", callback_data="p_aby"), 
                   InlineKeyboardButton("📱 Telebirr", callback_data="p_tele"))
        bot.edit_message_text(f"✅ {PLANS[call.data]['name']} መርጠዋል። ባንክ ይምረጡ፦", uid, mid, reply_markup=markup)

    elif call.data == "admin_bc":
        msg = bot.send_message(ADMIN_ID, "📢 የሚላከውን መልዕክት ይላኩ። ለመሰረዝ /cancel ይበሉ፦")
        bot.register_next_step_handler(msg, run_broadcast)

    elif call.data == "add_channel":
        msg = bot.send_message(ADMIN_ID, "📢 እባክዎ አዲስ ቻናል ለመጨመር አንድ መልዕክት ከቻናሉ ፎርዋርድ ያድርጉልኝ፦")
        bot.register_next_step_handler(msg, process_channel_add)

    elif call.data == "remove_ch_list":
        markup = InlineKeyboardMarkup()
        for ch in list(channels_col.find()):
            markup.add(InlineKeyboardButton(f"❌ {ch['name']}", callback_data=f"delch_{ch['id']}"))
        bot.send_message(ADMIN_ID, "መቀነስ የሚፈልጉትን ቻናል ይምረጡ፦", reply_markup=markup)

    elif call.data.startswith("delch_"):
        chid = int(call.data.split("_")[1])
        channels_col.delete_one({"id": chid})
        bot.answer_callback_query(call.id, "ቻናሉ ተሰርዟል!")
        bot.delete_message(ADMIN_ID, mid)

    elif call.data == "toggle_restrict":
        current = get_setting("restriction")
        settings_col.update_one({"type": "config"}, {"$set": {"restriction": not current}}, upsert=True)
        bot.answer_callback_query(call.id, "Restriction ተቀይሯል!")
        start(call.message)

    elif call.data == "admin_list":
        users = list(users_col.find({"active": True}).sort("expiry", 1))
        bot.send_message(ADMIN_ID, "📋 **የደንበኞች ዝርዝር፦**")
        for u in users:
            markup = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Remove User", callback_data=f"ban_{u['user_id']}"))
            txt = f"👤 {u['user_id']}\n⏳ ያበቃል: {to_ethiopian_format(u['expiry'])}"
            bot.send_message(ADMIN_ID, txt, reply_markup=markup)

    elif call.data.startswith("p_"):
        bank = call.data.split("_")[1].upper()
        u_doc = users_col.find_one({"user_id": uid})
        pk = u_doc['pending_plan'] if u_doc else "plan1"
        info = ""
        if bank == "CBE": info = "🏦 የኢትዮጵያ ንግድ ባንክ (CBE)\n👤 ስም: Getamesay Fikru\n🔢 Acc: 1000355140206"
        elif bank == "ABY": info = "🏦 አቢሲኒያ ባንክ (Abyssinia)\n👤 ስም: Getamesay Fikru\n🔢 Acc: 167829104"
        else: info = "📱 Telebirr (ቴሌብር)\n👤 ስም: Getamesay Fikru\n🔢 ስልክ: 0965979124"
        bot.edit_message_text(f"💎 ጥቅል: {PLANS[pk]['name']}\n\n{info}\n\n📸 የደረሰኙን ፎቶ ይላኩ (ለመሰረዝ /cancel ይበሉ)", uid, mid)
        bot.register_next_step_handler(call.message, get_screenshot)

    elif call.data.startswith("approve_"):
        p = call.data.split("_")
        tid, pk = int(p[1]), p[2]
        exp = (datetime.now() + timedelta(days=PLANS[pk]["duration"])).timestamp()
        users_col.update_one({"user_id": tid}, {"$set": {"expiry": exp, "active": True, "plan": pk, "joined_at": time.time()}})
        bot.send_message(tid, "✅ ክፍያዎ ተረጋግጧል! የአገልግሎት ማብቂያ፡ " + to_ethiopian_format(exp), reply_markup=get_channel_markup(tid))
        bot.delete_message(ADMIN_ID, mid)

    elif call.data.startswith("reject_"):
        tid = int(call.data.split("_")[1])
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🚫 የተሳሳተ ደረሰኝ", callback_data=f"rj_wrong_{tid}"), InlineKeyboardButton("📉 መጠኑ ያንሳል", callback_data=f"rj_less_{tid}"))
        bot.edit_message_text("❌ ውድቅ የተደረገበት ምክንያት ይምረጡ፡", ADMIN_ID, mid, reply_markup=markup)

    elif call.data.startswith("rj_"):
        p = call.data.split("_")
        mode, tid = p[1], int(p[2])
        reason = "የላኩት ደረሰኝ ትክክል አይደለም።" if mode == "wrong" else "የከፈሉት መጠን ለጥቅሉ ያንሳል።"
        bot.send_message(tid, f"❌ ይቅርታ፣ ክፍያዎ ውድቅ ሆኗል!\nምክንያት፦ {reason}")
        bot.edit_message_text(f"🔴 ተጠቃሚ {tid} ውድቅ ተደርጓል", ADMIN_ID, mid)

    elif call.data == "refresh_links":
        bot.edit_message_reply_markup(uid, mid, reply_markup=get_channel_markup(uid))

# ------------------- FUNCTIONS -------------------
def get_screenshot(message):
    if message.text == "/cancel":
        bot.send_message(message.chat.id, "❌ ተሰርዟል።", reply_markup=main_keyboard())
        return
    if not message.photo:
        bot.send_message(message.chat.id, "⚠️ እባክዎ የደረሰኙን ፎቶ ይላኩ። መሰረዝ ከፈለጉ /cancel ይበሉ።")
        bot.register_next_step_handler(message, get_screenshot)
        return
    uid = message.from_user.id
    pk = users_col.find_one({"user_id": uid})['pending_plan']
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ Approve", callback_data=f"approve_{uid}_{pk}"), InlineKeyboardButton("❌ Reject", callback_data=f"reject_{uid}"))
    bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
    bot.send_message(ADMIN_ID, f"💰 ክፍያ ከ: {message.from_user.first_name}", reply_markup=markup)
    bot.send_message(message.chat.id, "✅ የከፈሉት ደረሰኝ በ 1 ሰዓት ውስጥ ተረጋግጦ መልስ ያገኛሉ።")

def run_broadcast(message):
    if message.text == "/cancel": return
    for u in list(users_col.find()):
        try: bot.copy_message(u['user_id'], ADMIN_ID, message.message_id)
        except: pass
    bot.send_message(ADMIN_ID, "📢 ብሮድካስት ተጠናቋል!")

def process_channel_add(message):
    if not message.forward_from_chat:
        bot.send_message(ADMIN_ID, "❌ እባክዎ ከቻናል መልዕክት ፎርዋርድ ያድርጉ።")
        return
    channels_col.insert_one({"id": message.forward_from_chat.id, "name": message.forward_from_chat.title})
    bot.send_message(ADMIN_ID, f"✅ ቻናል '{message.forward_from_chat.title}' ተመዝግቧል!")

@bot.message_handler(func=lambda m: True)
def filter_bad_clicks(message):
    # ኪቦርድ በተኖች ስህተት እንዳይሰጡ መከላከል
    valid_texts = ["💎 VIP ለመመዝገብ", "👤 የእኔ አገልግሎት", "🎬 Addis Film Poster", "📜 VIP Channel ዝርዝር", "🆘 እገዛ (Help)"]
    if message.text not in valid_texts:
        bot.reply_to(message, f"ሰላም {message.from_user.first_name}፣ የተሳሳተ ቁልፍ ነክተዋል። እባክዎ /start ይበሉ።")

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling(timeout=20)
