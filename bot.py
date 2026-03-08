import os, telebot, time, threading, logging
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from pymongo import MongoClient
from datetime import datetime, timedelta
from ethiopian_date import EthiopianDateConverter
from flask import Flask

# ------------------- LOGGING -------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ------------------- KEEP ALIVE (FOR RENDER/HEROKU) -------------------
app = Flask('')
@app.route('/')
def home(): return "<h1>Gett VIP Master Bot is Running</h1>"
def run_web(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
def keep_alive(): threading.Thread(target=run_web, daemon=True).start()

# ------------------- CONFIGURATION -------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
MONGO_URI = os.getenv("MONGO_URI")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
client = MongoClient(MONGO_URI)
db = client["gett_vip_database"]
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

# ------------------- ETHIOPIAN DATE HELPER -------------------
def get_ethiopian_date(timestamp):
    try:
        dt = datetime.fromtimestamp(timestamp)
        eth = EthiopianDateConverter.to_ethiopian(dt.year, dt.month, dt.day)
        months = ["", "መስከረም", "ጥቅምት", "ህዳር", "ታህሳስ", "ጥር", "የካቲት", "መጋቢት", "ሚያዝያ", "ግንቦት", "ሰኔ", "ሐምሌ", "ነሐሴ", "ጳጉሜ"]
        return f"{months[eth.month]} {eth.day}፣ {eth.year}"
    except: return "ያልታወቀ ቀን"

# ------------------- SETTINGS HELPER -------------------
def is_restricted():
    data = settings_col.find_one({"type": "config"})
    return data.get("restriction", True) if data else True

# ------------------- KEYBOARDS -------------------
def main_menu_kb():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton("💎 VIP ለመመዝገብ"), KeyboardButton("👤 የእኔ አገልግሎት"))
    markup.add(KeyboardButton("🎬 Addis Film Poster"), KeyboardButton("📜 VIP Channel ዝርዝር"))
    markup.add(KeyboardButton("🆘 እገዛ (Help)"))
    return markup

def get_channel_links_kb(user_id):
    markup = InlineKeyboardMarkup()
    for ch in list(channels_col.find()):
        try:
            status = bot.get_chat_member(ch["id"], user_id).status
            icon = "✅" if status in ['member', 'administrator', 'creator'] else "☑️"
            # Create a one-time use link
            invite = bot.create_chat_invite_link(ch["id"], member_limit=1).invite_link
            markup.add(InlineKeyboardButton(f"{icon} {ch['name']}", url=invite))
        except: continue
    markup.add(InlineKeyboardButton("🔄 ሁኔታውን አድስ (Refresh Status)", callback_data="refresh_service"))
    return markup

# ------------------- AUTO-KICK SYSTEM (CORE) -------------------
def expiration_worker():
    while True:
        try:
            now = datetime.now().timestamp()
            expired_users = users_col.find({"active": True, "expiry": {"$lt": now}})
            for user in expired_users:
                uid = user["user_id"]
                for ch in list(channels_col.find()):
                    try:
                        bot.ban_chat_member(ch["id"], uid)
                        bot.unban_chat_member(ch["id"], uid)
                    except: pass
                users_col.update_one({"user_id": uid}, {"$set": {"active": False}})
                try:
                    bot.send_message(uid, "<b>🚨 የአገልግሎት ጊዜዎ አብቅቷል!</b>\nከVIP ቻናሎች ተወግደዋል። እባክዎ ደግመው በመክፈል ይቀላቀሉ።")
                except: pass
        except Exception as e: logger.error(f"Worker Error: {e}")
        time.sleep(60)

# ------------------- USER COMMANDS -------------------
@bot.message_handler(commands=['start'])
def welcome(message):
    uid = message.chat.id
    bot.send_message(uid, "<b>እንኳን ወደ Gett VIP Bot በሰላም መጡ!</b>\nበዚህ ቦት አዳዲስ ፊልሞችን እና ፖስተሮችን የሚያገኙበትን የVIP ቻናል መቀላቀል ይችላሉ።", reply_markup=main_menu_kb())
    if uid == ADMIN_ID:
        adm = InlineKeyboardMarkup(row_width=2)
        adm.add(InlineKeyboardButton("📋 ደንበኞች", callback_data="adm_list"), InlineKeyboardButton("📢 ብሮድካስት", callback_data="adm_bc"))
        adm.add(InlineKeyboardButton("➕ ቻናል ጨምር", callback_data="adm_add_ch"), InlineKeyboardButton("➖ ቻናል ቀንስ", callback_data="adm_rem_ch"))
        res_btn = "🚫 Restriction: ON" if is_restricted() else "🔓 Restriction: OFF"
        adm.add(InlineKeyboardButton(res_btn, callback_data="adm_toggle_res"))
        bot.send_message(ADMIN_ID, "<b>🛠 የአድሚን መቆጣጠሪያ ፓነል፦</b>", reply_markup=adm)

@bot.message_handler(func=lambda m: m.text == "👤 የእኔ አገልግሎት")
def user_status(message):
    uid = message.from_user.id
    user = users_col.find_one({"user_id": uid})
    if not user or not user.get("active"):
        bot.send_message(uid, "<b>ሰላም፣ እስካሁን የGett VIP አባል አልሆኑም!</b>\nለመመዝገብ ከታች ያለውን በተን ይጫኑ።")
        return
    
    txt = (f"<b>👤 ስም፦</b> {message.from_user.first_name}\n"
           f"<b>💰 ጥቅል፦</b> {PLANS.get(user.get('plan'), {'name':'N/A'})['name']}\n"
           f"<b>⏳ ማብቂያ፦</b> {get_ethiopian_date(user['expiry'])}\n\n"
           f"☑️ - ቻናሉ ውስጥ የሉበትም\n✅ - ቻናሉ ውስጥ ገብተዋል")
    bot.send_message(uid, txt, reply_markup=get_channel_links_kb(uid), protect_content=is_restricted())

@bot.message_handler(func=lambda m: m.text == "📜 VIP Channel ዝርዝር")
def channel_list_info(message):
    markup = InlineKeyboardMarkup()
    for ch in list(channels_col.find()):
        try:
            chat_info = bot.get_chat(ch["id"])
            markup.add(InlineKeyboardButton(f"📺 {ch['name']}", callback_data=f"info_{ch['id']}"))
        except: continue
    bot.send_message(message.chat.id, "<b>📌 የVIP ቻናሎቻችን ዝርዝር፦</b>\nስሙን ሲጫኑ መግለጫውን ያሳያል።", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "💎 VIP ለመመዝገብ")
def start_registration(message):
    markup = InlineKeyboardMarkup()
    for key, val in PLANS.items():
        markup.add(InlineKeyboardButton(f"🗣 {val['name']}", callback_data=f"buy_{key}"))
    bot.send_message(message.chat.id, "<b>👋 ለመመዝገብ የሚፈልጉትን ጥቅል ይምረጡ፦</b>", reply_markup=markup)

# ------------------- CALLBACK ROUTER -------------------
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    uid, mid = call.from_user.id, call.message.message_id

    if call.data.startswith("buy_"):
        plan_key = call.data.split("_")[1]
        users_col.update_one({"user_id": uid}, {"$set": {"pending_plan": plan_key}}, upsert=True)
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🏦 CBE (ንግድ ባንክ)", callback_data="bank_cbe"),
                   InlineKeyboardButton("🏦 Abyssinia (አቢሲኒያ)", callback_data="bank_aby"))
        markup.add(InlineKeyboardButton("📱 Telebirr (ቴሌብር)", callback_data="bank_tele"))
        bot.edit_message_text("<b>ባንክ ይምረጡ፦</b>", uid, mid, reply_markup=markup)

    elif call.data.startswith("bank_"):
        bank_type = call.data.split("_")[1].upper()
        if bank_type == "CBE": info = "🏦 የኢትዮጵያ ንግድ ባንክ (CBE)\n👤 ስም: Getamesay Fikru\n🔢 Acc: <code>1000355140206</code>"
        elif bank_type == "ABY": info = "🏦 የአቢሲኒያ ባንክ\n👤 ስም: Getamesay Fikru\n🔢 Acc: <code>167829104</code>"
        else: info = "📱 ቴሌብር (Telebirr)\n👤 ስም: Getamesay Fikru\n🔢 ስልክ: <code>0965979124</code>"
        
        bot.edit_message_text(f"{info}\n\n<b>📸 የከፈሉበትን የደረሰኝ ፎቶ (Screenshot) ይላኩ።</b>\nለመሰረዝ /cancel ይበሉ።", uid, mid)
        bot.register_next_step_handler(call.message, handle_receipt)

    elif call.data == "adm_list":
        active_users = list(users_col.find({"active": True}))
        bot.send_message(ADMIN_ID, f"<b>📋 በአሁኑ ሰዓት {len(active_users)} ደንበኞች አሉ።</b>")
        for u in active_users:
            markup = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ አስወግድ (Remove)", callback_data=f"remove_user_{u['user_id']}"))
            txt = f"👤 <b>ደንበኛ፦</b> <a href='tg://user?id={u['user_id']}'>{u['user_id']}</a>\n⏳ <b>ማብቂያ፦</b> {get_ethiopian_date(u['expiry'])}"
            bot.send_message(ADMIN_ID, txt, reply_markup=markup)

    elif call.data == "adm_add_ch":
        msg = bot.send_message(ADMIN_ID, "📢 እባክዎ መጨመር ከሚፈልጉት ቻናል አንድ መልዕክት ፎርዋርድ ያድርጉልኝ፦")
        bot.register_next_step_handler(msg, add_channel_process)

    elif call.data == "adm_rem_ch":
        markup = InlineKeyboardMarkup()
        for ch in list(channels_col.find()):
            markup.add(InlineKeyboardButton(f"❌ {ch['name']}", callback_data=f"ask_del_{ch['id']}"))
        bot.send_message(ADMIN_ID, "መሰረዝ የሚፈልጉትን ቻናል ይምረጡ፦", reply_markup=markup)

    elif call.data.startswith("ask_del_"):
        chid = call.data.split("_")[2]
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ አዎ፣ ይጥፋ", callback_data=f"do_del_{chid}"), InlineKeyboardButton("🔙 አይ፣ ይቆይ", callback_data="start"))
        bot.edit_message_text("<b>እርግጠኛ ነዎት ይህ ቻናል ከቦቱ ይጥፋ?</b>", ADMIN_ID, mid, reply_markup=markup)

    elif call.data.startswith("do_del_"):
        channels_col.delete_one({"id": int(call.data.split("_")[2])})
        bot.answer_callback_query(call.id, "ቻናሉ ተሰርዟል!")
        welcome(call.message)

    elif call.data.startswith("approve_"):
        _, tid, pk = call.data.split("_")
        tid = int(tid)
        expiry_ts = (datetime.now() + timedelta(days=PLANS[pk]["duration"])).timestamp()
        users_col.update_one({"user_id": tid}, {"$set": {"active": True, "expiry": expiry_ts, "plan": pk, "joined_at": time.time()}})
        bot.send_message(tid, f"<b>✅ እንኳን ደስ አለዎት! ክፍያዎ ተረጋግጧል።</b>\nአገልግሎቱ የሚያበቃው፦ {get_ethiopian_date(expiry_ts)}", reply_markup=get_channel_links_kb(tid))
        bot.edit_message_text(f"✅ ተጠቃሚ {tid} ጸድቋል!", ADMIN_ID, mid)

    elif call.data.startswith("reject_"):
        tid = call.data.split("_")[1]
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🚫 የደረሰኝ ስህተት", callback_data=f"rj_msg_{tid}_wrong_receipt"), 
                   InlineKeyboardButton("📉 ብር አነስተኛ ነው", callback_data=f"rj_msg_{tid}_low_amount"))
        markup.add(InlineKeyboardButton("✍️ የራስህን ጻፍ", callback_data=f"rj_custom_{tid}"))
        bot.edit_message_text("<b>ውድቅ የተደረገበት ምክንያት ይምረጡ፦</b>", ADMIN_ID, mid, reply_markup=markup)

    elif call.data.startswith("rj_msg_"):
        _, _, tid, reason_code = call.data.split("_")
        reason = "የላኩት ደረሰኝ ትክክል አይደለም።" if reason_code == "wrong_receipt" else "የላኩት የገንዘብ መጠን ለጥቅሉ አነስተኛ ነው።"
        bot.send_message(tid, f"<b>❌ ይቅርታ፣ ክፍያዎ ውድቅ ሆኗል።</b>\nምክንያት፦ {reason}")
        bot.edit_message_text(f"🔴 ለተጠቃሚ {tid} ውድቅ መሆኑ ተነግሯል።", ADMIN_ID, mid)

    elif call.data.startswith("info_"):
        chid = int(call.data.split("_")[1])
        try:
            info = bot.get_chat(chid)
            bot.answer_callback_query(call.id, f"📝 መግለጫ፦ {info.description if info.description else 'ምንም መግለጫ የለም'}", show_alert=True)
        except: pass

    elif call.data == "refresh_service":
        bot.edit_message_reply_markup(uid, mid, reply_markup=get_channel_links_kb(uid))

# ------------------- CORE FUNCTIONS -------------------
def handle_receipt(message):
    if message.text == "/cancel":
        bot.send_message(message.chat.id, "❌ ተሰርዟል።", reply_markup=main_menu_kb())
        return
    if not message.photo:
        bot.send_message(message.chat.id, "⚠️ እባክዎ የደረሰኙን ፎቶ ብቻ ይላኩ!")
        bot.register_next_step_handler(message, handle_receipt)
        return
    bot.send_message(message.chat.id, "<b>✅ ደረሰኙ ተቀብያለሁ!</b>\nአሁን ደግሞ የከፈሉበትን ሙሉ ስም በ አማርኛ ወይም በእንግሊዝኛ ይላኩ፦")
    bot.register_next_step_handler(message, lambda m: collect_name(m, message))

def collect_name(message, photo_msg):
    uid, name = message.from_user.id, message.text
    markup = ReplyKeyboardMarkup(resize_keyboard=True).add("ሁሉንም ነገር ጨርሻለሁ ላክ")
    bot.send_message(uid, f"ተቀብያለሁ <b>{name}</b>! አሁን ሂደቱን ለመጨረስ ከታች ያለውን ቁልፍ ይጫኑ።", reply_markup=markup)
    bot.register_next_step_handler(message, lambda m: final_submission(m, photo_msg, name))

def final_submission(message, photo_msg, full_name):
    uid = message.from_user.id
    user_data = users_col.find_one({"user_id": uid})
    plan_key = user_data['pending_plan'] if user_data else "plan1"
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ Approve", callback_data=f"approve_{uid}_{plan_key}"), 
               InlineKeyboardButton("❌ Reject", callback_data=f"reject_{uid}"))
    
    bot.send_message(ADMIN_ID, f"<b>💰 አዲስ የክፍያ ጥያቄ!</b>\n\n👤 <b>ስም፦</b> {full_name}\n🆔 <b>ID፦</b> <a href='tg://user?id={uid}'>{uid}</a>\n💎 <b>ጥቅል፦</b> {PLANS[plan_key]['name']}", reply_markup=markup)
    bot.forward_message(ADMIN_ID, uid, photo_msg.message_id)
    bot.send_message(uid, "<b>✅ በስኬት ተልኳል!</b>\nአድሚኑ ደረሰኙን አይቶ በ 1 ሰዓት ውስጥ ቻናሉን ያስገባዎታል።", reply_markup=main_menu_kb())

def add_channel_process(message):
    if not message.forward_from_chat:
        bot.send_message(ADMIN_ID, "❌ ስህተት! እባክዎ መልዕክቱን ከቻናሉ ፎርዋርድ ያድርጉት።")
        return
    channels_col.insert_one({"id": message.forward_from_chat.id, "name": message.forward_from_chat.title})
    bot.send_message(ADMIN_ID, f"✅ ቻናል <b>{message.forward_from_chat.title}</b> በስኬት ተመዝግቧል!")

@bot.message_handler(func=lambda m: m.chat.id == ADMIN_ID and m.text == "/cancel")
def cancel_all(message):
    bot.send_message(ADMIN_ID, "❌ ሁሉም ሂደቶች ተሰርዘዋል።", reply_markup=main_menu_kb())

# ------------------- START BOT -------------------
if __name__ == "__main__":
    keep_alive()
    # Start expiration checker in background
    threading.Thread(target=expiration_worker, daemon=True).start()
    logger.info("Bot is starting...")
    bot.infinity_polling(timeout=20, long_polling_timeout=10)    markup = InlineKeyboardMarkup()
    for ch in list(channels_col.find()):
        try:
            info = bot.get_chat(ch["id"])
            desc = info.description if info.description else "ምንም መግለጫ የለም"
            markup.add(InlineKeyboardButton(f"📺 {ch['name']}", callback_data=f"view_desc_{ch['id']}"))
        except: continue
    bot.send_message(message.chat.id, "📌 የቪአይፒ ቻናሎች (ሲነኩት መግለጫ ያሳያሉ)፦", reply_markup=markup)

# ------------------- ADMIN LOGIC -------------------
@bot.callback_query_handler(func=lambda call: True)
def router(call):
    uid, mid = call.from_user.id, call.message.message_id
    
    if call.data == "ad_list":
        users = list(users_col.find({"active": True}))
        bot.send_message(ADMIN_ID, "📋 **የደንበኞች ዝርዝር፦**")
        for u in users:
            txt = f"👤 [ሊንክ](tg://user?id={u['user_id']}) | ID: `{u['user_id']}`\n💰 {PLANS.get(u.get('plan'), {'name':'N/A'})['name']}\n⏳ {to_eth(u['expiry'])}"
            bot.send_message(ADMIN_ID, txt, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Remove User", callback_data=f"ban_{u['user_id']}")))

    elif call.data == "ad_add_ch":
        msg = bot.send_message(ADMIN_ID, "እባክዎ መጨመር ከሚፈልጉት ቻናል አንድ መልዕክት ፎርዋርድ ያድርጉልኝ፦")
        bot.register_next_step_handler(msg, process_add_ch)

    elif call.data == "ad_rem_ch":
        markup = InlineKeyboardMarkup()
        for ch in list(channels_col.find()): markup.add(InlineKeyboardButton(f"❌ {ch['name']}", callback_data=f"ask_rem_{ch['id']}"))
        bot.send_message(ADMIN_ID, "መሰረዝ የሚፈልጉትን ቻናል ይምረጡ፡", reply_markup=markup)

    elif call.data.startswith("ask_rem_"):
        chid = call.data.split("_")[2]
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("Yes, Remove", callback_data=f"do_rem_{chid}"), InlineKeyboardButton("No, Cancel", callback_data="start"))
        bot.edit_message_text("Are you sure you want to remove this channel?", ADMIN_ID, mid, reply_markup=markup)

    elif call.data.startswith("do_rem_"):
        channels_col.delete_one({"id": int(call.data.split("_")[2])})
        bot.answer_callback_query(call.id, "ቻናሉ ተሰርዟል!")

    elif call.data == "ad_bc":
        msg = bot.send_message(ADMIN_ID, "📢 መልዕክትዎን ይላኩ (Photo/Video/Text)። ለመሰረዝ /cancel ይበሉ፦")
        bot.register_next_step_handler(msg, run_bc)

    elif call.data == "toggle_res":
        cur = get_setting("restriction")
        settings_col.update_one({"type": "config"}, {"$set": {"restriction": not cur}}, upsert=True)
        bot.answer_callback_query(call.id, "Restriction ተቀይሯል!")
        start(call.message)

    elif call.data.startswith("view_desc_"):
        chid = int(call.data.split("_")[2])
        try:
            info = bot.get_chat(chid)
            bot.answer_callback_query(call.id, f"📝 {info.description if info.description else 'ምንም መግለጫ የለም'}", show_alert=True)
        except: pass

    # --- Payment Logic ---
    elif call.data in PLANS:
        users_col.update_one({"user_id": uid}, {"$set": {"pending_plan": call.data}}, upsert=True)
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🏦 CBE", callback_data="p_cbe"), InlineKeyboardButton("🏦 Abyssinia", callback_data="p_aby"), InlineKeyboardButton("📱 Telebirr", callback_data="p_tele"))
        bot.edit_message_text("ባንክ ይምረጡ፦", uid, mid, reply_markup=markup)

    elif call.data.startswith("p_"):
        bank = call.data.split("_")[1].upper()
        if bank == "CBE": info = "🏦 የኢትዮጵያ ንግድ ባንክ (CBE)\n👤 ስም: Getamesay Fikru\n🔢 Acc: `1000355140206`"
        elif bank == "ABY": info = "🏦 አቢሲኒያ ባንክ (Abyssinia)\n👤 ስም: Getamesay Fikru\n🔢 Acc: `167829104`"
        else: info = "📱 Telebirr (ቴሌብር)\n👤 ስም: Getamesay Fikru\n🔢 ስልክ: `0965979124`"
        bot.edit_message_text(f"{info}\n\n📸 የደረሰኙን ፎቶ (Screenshot) ይላኩ።\nለመሰረዝ /cancel ይበሉ።", uid, mid, parse_mode="Markdown")
        bot.register_next_step_handler(call.message, get_receipt)

    elif call.data.startswith("approve_"):
        tid, pk = int(call.data.split("_")[1]), call.data.split("_")[2]
        exp = (datetime.now() + timedelta(days=PLANS[pk]["duration"])).timestamp()
        users_col.update_one({"user_id": tid}, {"$set": {"active": True, "expiry": exp, "plan": pk, "joined_at": time.time()}})
        bot.send_message(tid, f"✅ ክፍያዎ ተረጋግጧል! አገልግሎቱ የሚያበቃው፡ {to_eth(exp)}", reply_markup=get_channel_markup(tid))
        bot.edit_message_text(f"✅ ተጠቃሚ {tid} ጸድቋል!", ADMIN_ID, mid)

    elif call.data.startswith("reject_"):
        tid = call.data.split("_")[1]
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🚫 የተሳሳተ ብር", callback_data=f"rj_mon_{tid}"), InlineKeyboardButton("📄 የተሳሳተ ደረሰኝ", callback_data=f"rj_rec_{tid}"))
        markup.add(InlineKeyboardButton("✍️ የራስህን ጻፍ", callback_data=f"rj_cus_{tid}"), InlineKeyboardButton("🔙 Back", callback_data="start"))
        bot.edit_message_text("ለምን ውድቅ ሆነ?", ADMIN_ID, mid, reply_markup=markup)

    elif call.data == "refresh_links":
        bot.edit_message_reply_markup(uid, mid, reply_markup=get_channel_markup(uid))

# ------------------- CORE FUNCTIONS -------------------
def process_add_ch(message):
    if not message.forward_from_chat:
        bot.send_message(ADMIN_ID, "❌ እባክዎ ከቻናል ፎርዋርድ ያድርጉ!")
        return
    channels_col.insert_one({"id": message.forward_from_chat.id, "name": message.forward_from_chat.title})
    bot.send_message(ADMIN_ID, f"✅ ቻናል '{message.forward_from_chat.title}' ተጨምሯል!")

def run_bc(message):
    if message.text == "/cancel": return
    for u in list(users_col.find()):
        try: bot.copy_message(u['user_id'], ADMIN_ID, message.message_id)
        except: pass
    bot.send_message(ADMIN_ID, "📢 ብሮድካስት ተጠናቋል!")

def get_receipt(message):
    if message.text == "/cancel":
        bot.send_message(message.chat.id, "❌ ተሰርዟል", reply_markup=main_kb())
        return
    if not message.photo:
        bot.send_message(message.chat.id, "⚠️ እባክዎ የደረሰኝ ፎቶ ይላኩ!")
        bot.register_next_step_handler(message, get_receipt)
        return
    bot.send_message(message.chat.id, "✅ ደረሰኝ ተቀብያለሁ! አሁን ሙሉ ስምዎን በ አማርኛ ወይም በ እንግሊዝኛ ይላኩ።")
    bot.register_next_step_handler(message, lambda m: get_name(m, message))

def get_name(message, photo_msg):
    uid, name = message.from_user.id, message.text
    markup = ReplyKeyboardMarkup(resize_keyboard=True).add("ሁሉንም ነገር ጨርሻለሁ ላክ")
    bot.send_message(uid, f"ተቀብያለሁ {name}! ለመጨረስ 'ሁሉንም ነገር ጨርሻለሁ ላክ' የሚለውን ይጫኑ።", reply_markup=markup)
    bot.register_next_step_handler(message, lambda m: final_submit(m, photo_msg, name))

def final_submit(message, photo_msg, full_name):
    uid = message.from_user.id
    u_data = users_col.find_one({"user_id": uid})
    pk = u_data['pending_plan'] if u_data else "plan1"
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ Approve", callback_data=f"approve_{uid}_{pk}"), InlineKeyboardButton("❌ Reject", callback_data=f"reject_{uid}"))
    bot.send_message(ADMIN_ID, f"💰 አዲስ ክፍያ!\n👤 ስም: {full_name}\n🆔 ID: [{uid}](tg://user?id={uid})\n💎 ጥቅል: {PLANS[pk]['name']}", parse_mode="Markdown")
    bot.forward_message(ADMIN_ID, uid, photo_msg.message_id)
    bot.send_message(ADMIN_ID, "ያረጋግጡ፡", reply_markup=markup)
    bot.send_message(uid, "✅ ደረሰኝዎ ተልኳል! በ 1 ሰዓት ውስጥ ይመለስልዎታል።", reply_markup=main_kb())

# ------------------- RUN -------------------
if __name__ == "__main__":
    keep_alive()
    threading.Thread(target=auto_kick_loop, daemon=True).start()
    bot.infinity_polling()
