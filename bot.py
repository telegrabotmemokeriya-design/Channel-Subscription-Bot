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
def get_welcome_text():
    data = settings_col.find_one({"type": "welcome"})
    if data: return data["text"]
    return "እንኳን ወደ Gett VIP Bot በሰላም መጡ! እዚህ ሁሉንም አይነት ፊልሞች በጥራት እና በትርጉም ያገኛሉ። ከአዳዲስ እስከ ቆዩ የሆሊውድ፣ ቦሊውድ፣ የኮሪያ እና የካና ድራማዎች በሙሉ ተሟልተዋል።"

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
            invite = bot.create_chat_invite_link(ch["id"], member_limit=1).invite_link
            status = "✅" if bot.get_chat_member(ch["id"], user_id).status in ['member', 'administrator', 'creator'] else "☑️"
            markup.add(InlineKeyboardButton(f"{status} {ch['name']}", url=invite))
        except: continue
    markup.add(InlineKeyboardButton("🔄 ሁሉንም ቻናል መግባትህን አረጋግጥ (Refresh)", callback_data="refresh_links"))
    return markup

# ------------------- KEYBOARDS -------------------
def main_keyboard(uid):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton("💎 VIP ለመመዝገብ"))
    markup.add(KeyboardButton("👤 የእኔ አገልግሎት"), KeyboardButton("🎬 Addis Film Poster"))
    markup.add(KeyboardButton("📜 VIP Channel ዝርዝር"), KeyboardButton("🆘 እገዛ (Help)"))
    return markup

# ------------------- COMMANDS -------------------
@bot.message_handler(commands=["start"])
def start(message):
    uid = message.from_user.id
    bot.send_message(uid, get_welcome_text(), reply_markup=main_keyboard(uid))
    if uid == ADMIN_ID:
        adm_in = InlineKeyboardMarkup()
        adm_in.add(InlineKeyboardButton("📋 የደንበኞች ዝርዝር", callback_data="admin_list"),
                   InlineKeyboardButton("📢 ብሮድካስት", callback_data="admin_bc"))
        adm_in.add(InlineKeyboardButton("➕ ቻናል ጨምር", callback_data="add_channel"),
                   InlineKeyboardButton("✍️ Welcome Msg ቀይር", callback_data="edit_welcome"))
        bot.send_message(uid, "🛠 የአድሚን ፓነል፦", reply_markup=adm_in)

@bot.message_handler(func=lambda m: m.text == "💎 VIP ለመመዝገብ")
def vip_reg(message):
    markup = InlineKeyboardMarkup()
    for k, p in PLANS.items(): markup.add(InlineKeyboardButton(f"🗣 {p['name']}", callback_data=k))
    bot.send_message(message.chat.id, "👋 VIP ለመግባት ጥቅል ይምረጡ:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🎬 Addis Film Poster")
def addis_film(message):
    bot.send_message(message.chat.id, "🎬 አዳዲስ የፊልም ፖስተሮችን ለማየት ከታች ያለውን ሊንክ ይጫኑ፦\nhttps://t.me/GettVipCenter")

@bot.message_handler(func=lambda m: m.text == "🆘 እገዛ (Help)")
def help_btn(message):
    bot.send_message(message.chat.id, "ለተጨማሪ ድጋፍ እና እገዛ አድሚኑን ያነጋግሩ፦\n👤 @gygett\n\nወደ ኋላ ለመመለስ 🔙 ይበሉ ወይም /start ይበሉ።")

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
        bot.send_message(message.chat.id, f"ሰላም {message.from_user.first_name}፣ እስካሁን የGett VIP አባል አልሆኑም። እባክዎ መጀመሪያ ይመዝገቡ።")
        return
    msg = (f"👤 ስም: {message.from_user.first_name}\n"
           f"📅 የገቡበት: {to_ethiopian_format(u.get('joined_at', time.time()))}\n"
           f"⏳ የሚያበቃው: {to_ethiopian_format(u['expiry'])}\n\n"
           f"✅ - ቻናል ውስጥ ገብተዋል\n☑️ - ቻናል ውስጥ አልገቡም\n\nሊንኮቹን ለሌላ ሰው ማጋራት አይቻልም 🚫")
    bot.send_message(message.chat.id, msg, reply_markup=get_channel_markup(message.from_user.id), protect_content=True)

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
        msg = bot.send_message(ADMIN_ID, "📢 የሚላከውን መልዕክት ይጻፉ (ለመሰረዝ 'cancel' ይበሉ)፦")
        bot.register_next_step_handler(msg, run_broadcast)

    elif call.data == "edit_welcome":
        msg = bot.send_message(ADMIN_ID, "✍️ አዲሱን የሰላምታ (Welcome) ጽሁፍ ይላኩ፦")
        bot.register_next_step_handler(msg, save_welcome)

    elif call.data == "add_channel":
        msg = bot.send_message(ADMIN_ID, "📢 እባክዎ አዲስ ቻናል ለመጨመር አንድ መልዕክት ከቻናሉ ፎርዋርድ ያድርጉልኝ፦")
        bot.register_next_step_handler(msg, process_channel_add)

    elif call.data == "admin_list":
        users = list(users_col.find({"active": True}).sort("expiry", 1))
        bot.send_message(ADMIN_ID, "📋 **የደንበኞች ዝርዝር (ማብቂያቸው የደረሱ ቅድሚያ)፦**")
        for u in users:
            info = f"👤 [{u['user_id']}](tg://user?id={u['user_id']})\n⏳ ያበቃል: {to_ethiopian_format(u['expiry'])}"
            bot.send_message(ADMIN_ID, info, parse_mode="Markdown")

    elif call.data.startswith("p_"):
        u_data = users_col.find_one({"user_id": uid})
        pk = u_data['pending_plan']
        bank = call.data.split("_")[1].upper()
        info = "🏦 CBE\n👤 ስም: Getamesay Fikru\n🔢 Acc: 1000355140206" if bank == "CBE" else "🏦 Abyssinia\n👤 ስም: Getamesay Fikru\n🔢 Acc: 167829104" if bank == "ABY" else "📱 Telebirr\n👤 ስም: Getamesay Fikru\n🔢 ስልክ: 0965979124"
        bot.edit_message_text(f"💎 ጥቅል: {PLANS[pk]['name']}\n\n{info}\n\n📸 የደረሰኙን ፎቶ ይላኩ (ለመሰረዝ 'cancel' ይበሉ)", uid, mid)
        bot.register_next_step_handler(call.message, get_screenshot)

    elif call.data.startswith("approve_"):
        p = call.data.split("_")
        target_id, pk = int(p[1]), p[2]
        exp = (datetime.now() + timedelta(days=PLANS[pk]["duration"])).timestamp()
        users_col.update_one({"user_id": target_id}, {"$set": {"expiry": exp, "active": True, "plan": pk, "joined_at": time.time()}})
        u_info = bot.get_chat(target_id)
        name = u_info.first_name if u_info.first_name else "ተጠቃሚ"
        msg = (f"ወድ : {name}\n\n🧧{PLANS[pk]['name']} ✔️ ከፍለዋል ።\n🎉 የ Gett Vip ⚜️ አባል ሆነዋል! \n"
               f"🗓️ አገልግሎቱ የሚያበቃው - {to_ethiopian_format(exp)}\n\n"
               f"ቻናሎቹን ለመቀላቀል ከታች ያሉትን በተኖች ይጠቀሙ፡\n✅ - ገብተዋል | ☑️ - አልገቡም")
        bot.send_message(target_id, msg, reply_markup=get_channel_markup(target_id), protect_content=True)
        bot.edit_message_text(f"✅ ተጠቃሚ {target_id} ጸድቋል!", ADMIN_ID, mid)

    elif call.data.startswith("reject_"):
        target_id = call.data.split("_")[1]
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🚫 የተሳሳተ ደረሰኝ", callback_data=f"rj_wrong_{target_id}"),
                   InlineKeyboardButton("📉 መጠኑ ያንሳል", callback_data=f"rj_less_{target_id}"))
        markup.add(InlineKeyboardButton("✍️ የራስህን መልዕክት ጻፍ", callback_data=f"rj_custom_{target_id}"))
        bot.edit_message_text("❌ ውድቅ የተደረገበት ምክንያት ይምረጡ፡", ADMIN_ID, mid, reply_markup=markup)

    elif call.data.startswith("rj_"):
        p = call.data.split("_")
        mode, target_id = p[1], int(p[2])
        if mode == "custom":
            msg = bot.send_message(ADMIN_ID, f"✍️ ለተጠቃሚ {target_id} የሚላከውን ምክንያት ይጻፉ፦")
            bot.register_next_step_handler(msg, lambda m: send_custom_reject(m, target_id))
        else:
            reason = "የላኩት ደረሰኝ ትክክል አይደለም።" if mode == "wrong" else "የከፈሉት መጠን ለጥቅሉ ያንሳል።"
            bot.send_message(target_id, f"❌ ይቅርታ፣ ክፍያዎ ውድቅ ሆኗል!\nምክንያት፦ {reason}")
            bot.edit_message_text(f"🔴 ተጠቃሚ {target_id} ውድቅ ተደርጓል (ምክንያት፡ {mode})", ADMIN_ID, mid)

    elif call.data == "refresh_links":
        bot.edit_message_reply_markup(uid, mid, reply_markup=get_channel_markup(uid))

# ------------------- ADMIN FUNCTIONS -------------------
def send_custom_reject(message, target_id):
    bot.send_message(target_id, f"❌ ይቅርታ፣ ክፍያዎ ውድቅ ሆኗል!\nምክንያት፦ {message.text}")
    bot.send_message(ADMIN_ID, "✅ መልዕክቱ ለተጠቃሚው ተልኳል።")

def save_welcome(message):
    settings_col.update_one({"type": "welcome"}, {"$set": {"text": message.text}}, upsert=True)
    bot.send_message(ADMIN_ID, "✅ የሰላምታ ጽሁፉ ተቀይሯል!")

def run_broadcast(message):
    if message.text.lower() == 'cancel': 
        bot.send_message(ADMIN_ID, "❌ ብሮድካስት ተሰርዟል።")
        return
    users = list(users_col.find())
    success, fail = 0, 0
    for u in users:
        try:
            bot.copy_message(u['user_id'], ADMIN_ID, message.message_id)
            success += 1
        except: fail += 1
    bot.send_message(ADMIN_ID, f"📢 ብሮድካስት ተጠናቋል!\n✅ የተላከላቸው: {success}\n❌ ያልተላከላቸው (Account Deleted/Blocked): {fail}")

def process_channel_add(message):
    if not message.forward_from_chat:
        bot.reply_to(message, "❌ ስህተት፡ እባክዎ መልዕክት ከቻናል ፎርዋርድ ያድርጉ።")
        return
    channels_col.insert_one({"id": message.forward_from_chat.id, "name": message.forward_from_chat.title})
    bot.send_message(ADMIN_ID, f"✅ ቻናል '{message.forward_from_chat.title}' ተመዝግቧል!")

# ------------------- USER LOGIC -------------------
def get_screenshot(message):
    if message.text and message.text.lower() == 'cancel':
        bot.send_message(message.chat.id, "❌ ተሰርዟል።", reply_markup=main_keyboard(message.from_user.id))
        return
    if not message.photo:
        bot.send_message(message.chat.id, "⚠️ እባክዎ የደረሰኙን ፎቶ ብቻ ይላኩ። 'cancel' በማለት መሰረዝ ይችላሉ።")
        bot.register_next_step_handler(message, get_screenshot)
        return
    
    uid = message.from_user.id
    u_data = users_col.find_one({"user_id": uid})
    pk = u_data['pending_plan']
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ Approve", callback_data=f"approve_{uid}_{pk}"),
               InlineKeyboardButton("❌ Reject", callback_data=f"reject_{uid}"))
    
    bot.send_message(ADMIN_ID, f"💰 አዲስ ክፍያ ከ: [{message.from_user.first_name}](tg://user?id={uid})\n💎 ጥቅል: {PLANS[pk]['name']}", parse_mode="Markdown")
    bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
    bot.send_message(ADMIN_ID, "ያረጋግጡ፦", reply_markup=markup)
    bot.send_message(message.chat.id, "✅ ደረሰኝዎ ተልኳል! አድሚኑ እስኪያረጋግጥ በትዕግስት ይጠብቁ።")

# ------------------- EXPIRY CHECKER -------------------
def check_subscriptions():
    while True:
        try:
            now = datetime.now().timestamp()
            expired = users_col.find({"active": True, "expiry": {"$lt": now}})
            for u in expired:
                for ch in list(channels_col.find()):
                    try:
                        bot.ban_chat_member(ch["id"], u["user_id"])
                        bot.unban_chat_member(ch["id"], u["user_id"])
                    except: pass
                users_col.update_one({"user_id": u["user_id"]}, {"$set": {"active": False}})
                bot.send_message(u["user_id"], "⚠️ የ VIP አገልግሎት ጊዜዎ አብቅቷል! ለመቀጠል እባክዎ በድጋሚ ጥቅል ይግዙ።")
        except: pass
        time.sleep(3600)

if __name__ == "__main__":
    keep_alive()
    Thread(target=check_subscriptions, daemon=True).start()
    bot.remove_webhook()
    time.sleep(1)
    bot.infinity_polling(timeout=20)
