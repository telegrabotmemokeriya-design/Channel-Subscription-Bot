import os
import telebot
import time
import threading
import logging
from datetime import datetime, timedelta
from flask import Flask
from pymongo import MongoClient
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from ethiopian_date import EthiopianDateConverter

# =========================================================================
# 1. LOGGING & SERVER SETUP (KEEP ALIVE)
# =========================================================================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = Flask('')

@app.route('/')
def home():
    return "<b>Gett VIP Pro Bot is running smoothly!</b>"

def run_web_server():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

def start_keep_alive():
    server_thread = threading.Thread(target=run_web_server, daemon=True)
    server_thread.start()

# =========================================================================
# 2. CONFIGURATION & DATABASE CONNECT
# =========================================================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
MONGO_URI = os.getenv("MONGO_URI")

# Initialize Bot
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# Initialize MongoDB
try:
    client = MongoClient(MONGO_URI)
    db = client["gett_vip_ultimate_db"]
    users_col = db["users"]
    channels_col = db["channels"]
    settings_col = db["settings"]
    logger.info("Connected to MongoDB successfully!")
except Exception as e:
    logger.error(f"MongoDB Connection Error: {e}")

# VIP Subscription Plans
PLANS = {
    "plan1": {"duration": 30, "price": 200, "name": "የ 1 ወር (200 ብር)", "days": 30},
    "plan2": {"duration": 60, "price": 380, "name": "የ 2 ወር (380 ብር)", "days": 60},
    "plan3": {"duration": 90, "price": 550, "name": "የ 3 ወር (550 ብር)", "days": 90},
    "plan5": {"duration": 150, "price": 1050, "name": "የ 5 ወር (1050 ብር)", "days": 150},
    "plan12": {"duration": 365, "price": 2000, "name": "የ 1 አመት (2000 ብር)", "days": 365}
}

TEXTS = {
    "am": {"welcome": "እንኳን ደህና መጡ", "menu": ["💎 VIP ለመመዝገብ", "👤 የእኔ አገልግሎት", "🎬 Addis Film Poster", "📜 VIP Channel ዝርዝር", "🆘 እገዛ (Help)"]},
    "en": {"welcome": "Welcome to Gett VIP", "menu": ["💎 Register VIP", "👤 My Service", "🎬 Addis Film Poster", "📜 VIP Channel List", "🆘 Help"]},
    "or": {"welcome": "Baga nagaan dhuftan", "menu": ["💎 VIP Galmaa'uuf", "👤 Tajaajila Koo", "🎬 Addis Film Poster", "📜 Tarree VIP Channel", "🆘 Gargaarsa"]},
    "tg": {"welcome": "እንቋዕ ብደሓን መጻእኹም", "menu": ["💎 VIP ንምምዝጋብ", "👤 ናተይ ኣገልግሎት", "🎬 Addis Film Poster", "📜 ዝርዝር VIP ቻነል", "🆘 ሓገዝ"]},
    "ar": {"welcome": "أهلاً بك في VIP", "menu": ["💎 الاشتراك في VIP", "👤 خدمتي", "🎬 Addis Film Poster", "📜 قائمة القنوات", "🆘 مساعدة"]}
}

# =========================================================================
# 3. UTILITY FUNCTIONS
# =========================================================================
def to_eth_date(timestamp):
    """Converts Unix timestamp to Ethiopian Date String"""
    try:
        dt = datetime.fromtimestamp(timestamp)
        conv = EthiopianDateConverter.to_ethiopian(dt.year, dt.month, dt.day)
        months = ["", "መስከረም", "ጥቅምት", "ህዳር", "ታህሳስ", "ጥር", "የካቲት", "መጋቢት", "ሚያዝያ", "ግንቦት", "ሰኔ", "ሐምሌ", "ነሐሴ", "ጳጉሜ"]
        return f"{months[conv.month]} {conv.day}፣ {conv.year}"
    except Exception as e:
        logger.error(f"Date conversion error: {e}")
        return "ያልታወቀ ቀን"

def is_restriction_on():
    """Checks if content protection is enabled"""
    data = settings_col.find_one({"type": "config"})
    return data.get("restriction", True) if data else True

def get_user_lang(uid):
    user = users_col.find_one({"user_id": uid})
    return user.get("lang", "am") if user else "am"

def get_channel_status_markup(user_id):
    """Generates a list of channels with join status icons"""
    markup = InlineKeyboardMarkup()
    channels = list(channels_col.find())
    
    if not channels:
        markup.add(InlineKeyboardButton("ምንም ቻናል አልተጨመረም", callback_data="none"))
        return markup

    for ch in channels:
        try:
            member = bot.get_chat_member(ch["id"], user_id)
            if member.status in ['member', 'administrator', 'creator']:
                status_icon = "✅"
            else:
                status_icon = "☑️"
            
            invite = bot.create_chat_invite_link(ch["id"], member_limit=1).invite_link
            markup.add(InlineKeyboardButton(f"{status_icon} {ch['name']}", url=invite))
        except Exception:
            continue
            
    markup.add(InlineKeyboardButton("🔄 ሁሉም ቻናል መግባቶን ያረጋግጡ (Refresh)", callback_data="refresh_service"))
    return markup

# =========================================================================
# 4. BACKGROUND WORKER (AUTO-KICK)
# =========================================================================
def auto_kick_worker():
    """Continuously checks for expired subscriptions and removes users"""
    while True:
        try:
            current_time = datetime.now().timestamp()
            expired_users = users_col.find({"active": True, "expiry": {"$lt": current_time}})
            
            for user in expired_users:
                uid = user["user_id"]
                logger.info(f"Expiring user: {uid}")
                
                for ch in list(channels_col.find()):
                    try:
                        bot.ban_chat_member(ch["id"], uid)
                        bot.unban_chat_member(ch["id"], uid)
                    except Exception as e:
                        logger.error(f"Error kicking {uid} from {ch['id']}: {e}")
                
                users_col.update_one({"user_id": uid}, {"$set": {"active": False}})
                
                try:
                    msg = "<b>⚠️ የአገልግሎት ጊዜዎ አብቅቷል!</b>\n\nከVIP ቻናሎች በራስ-ሰር ተወግደዋል። አገልግሎቱን ለመቀጠል እባክዎ ደግመው ይክፈሉ እና ደረሰኝ ይላኩ።"
                    bot.send_message(uid, msg)
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Auto-kick worker error: {e}")
            
        time.sleep(60)

# =========================================================================
# 5. KEYBOARDS
# =========================================================================
def main_menu_keyboard(uid):
    lang = get_user_lang(uid)
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btns = TEXTS[lang]["menu"]
    markup.add(KeyboardButton(btns[0]), KeyboardButton(btns[1]))
    markup.add(KeyboardButton(btns[2]), KeyboardButton(btns[3]))
    markup.add(KeyboardButton(btns[4]))
    return markup

def admin_panel_keyboard():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📊 የደንበኞች ዝርዝር", callback_data="adm_list"),
        InlineKeyboardButton("📢 ብሮድካስት", callback_data="adm_bc")
    )
    markup.add(
        InlineKeyboardButton("➕ ቻናል ጨምር", callback_data="adm_add_ch"),
        InlineKeyboardButton("➖ ቻናል ቀንስ", callback_data="adm_rem_ch")
    )
    res_text = "🚫 Restriction: ON" if is_restriction_on() else "🔓 Restriction: OFF"
    markup.add(InlineKeyboardButton(res_text, callback_data="adm_toggle_res"))
    markup.add(InlineKeyboardButton("👤 ተጠቃሚ ጨምር (Manual)", callback_data="adm_manual_add"))
    return markup

# =========================================================================
# 6. MESSAGE HANDLERS
# =========================================================================
@bot.message_handler(commands=['start'])
def handle_start(message):
    uid = message.chat.id
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("አማርኛ 🇪🇹", callback_data="lang_am"),
        InlineKeyboardButton("English 🇺🇸", callback_data="lang_en"),
        InlineKeyboardButton("Oromoo 🇪🇹", callback_data="lang_or"),
        InlineKeyboardButton("ትግርኛ 🇪🇹", callback_data="lang_tg"),
        InlineKeyboardButton("العربية 🇸🇦", callback_data="lang_ar")
    )
    bot.send_message(uid, "<b>Gett VIP ⚜️\n\nChoose Language / ቋንቋ ይምረጡ</b>", reply_markup=markup)
    
    if uid == ADMIN_ID:
        bot.send_message(ADMIN_ID, "<b>🛠 Master Admin Panel:</b>", reply_markup=admin_panel_keyboard())

@bot.message_handler(func=lambda m: True)
def handle_all_messages(message):
    uid = message.chat.id
    text = message.text
    
    # Check menu buttons in all languages
    if text in [l["menu"][1] for l in TEXTS.values()]:
        handle_my_service(message)
    elif text in [l["menu"][0] for l in TEXTS.values()]:
        handle_registration(message)
    elif text in [l["menu"][3] for l in TEXTS.values()]:
        handle_channel_list(message)
    elif text == "🎬 Addis Film Poster":
        bot.send_message(uid, "Coming Soon...")

def handle_my_service(message):
    uid = message.chat.id
    user_data = users_col.find_one({"user_id": uid})
    
    if not user_data or not user_data.get("active"):
        bot.send_message(uid, "<b>ሰላም፣ እስካሁን የGett VIP አባል አልሆኑም ወይም ጊዜዎ አልቋል።</b>\n\nአባል ለመሆን ጥቅል ይምረጡ።", reply_markup=main_menu_keyboard(uid))
        return
    
    expiry_str = to_eth_date(user_data["expiry"])
    plan_name = PLANS.get(user_data.get("plan"), {"name": "ያልታወቀ"})["name"]
    
    status_text = (
        f"<b>👤 ስም፦</b> {message.from_user.first_name}\n"
        f"<b>💎 የአባልነት አይነት፦</b> {plan_name}\n"
        f"<b>⏳ የሚያበቃው፦</b> {expiry_str}\n\n"
        f"ሊንኮቹን በመጫን ይቀላቀሉ 👇"
    )
    bot.send_message(uid, status_text, reply_markup=get_channel_status_markup(uid), protect_content=is_restriction_on())

def handle_registration(message):
    markup = InlineKeyboardMarkup()
    for key, val in PLANS.items():
        markup.add(InlineKeyboardButton(f"💳 {val['name']}", callback_data=f"buy_{key}"))
    bot.send_message(message.chat.id, "<b>ለመመዝገብ የሚፈልጉትን ጥቅል ይምረጡ፦</b>", reply_markup=markup)

def handle_channel_list(message):
    channels = list(channels_col.find())
    if not channels:
        bot.send_message(message.chat.id, "<b>❌ እስካሁን ምንም ቻናል አልተመዘገበም።</b>")
        return
    markup = InlineKeyboardMarkup()
    for ch in channels:
        markup.add(InlineKeyboardButton(f"🔹 {ch['name']}", callback_data=f"view_ch_{ch['id']}"))
    bot.send_message(message.chat.id, "<b>📜 የVIP ቻናሎች ዝርዝር፦</b>", reply_markup=markup)

# =========================================================================
# 7. CALLBACK QUERY HANDLER
# =========================================================================
@bot.callback_query_handler(func=lambda call: True)
def handle_all_callbacks(call):
    uid, mid = call.from_user.id, call.message.message_id

    if call.data.startswith("lang_"):
        lcode = call.data.split("_")[1]
        users_col.update_one({"user_id": uid}, {"$set": {"lang": lcode}}, upsert=True)
        bot.delete_message(uid, mid)
        bot.send_message(uid, f"<b>{TEXTS[lcode]['welcome']}!</b>", reply_markup=main_menu_keyboard(uid))
        return
    
    if call.data.startswith("buy_"):
        plan_id = call.data.split("_")[1]
        users_col.update_one({"user_id": uid}, {"$set": {"pending_plan": plan_id}}, upsert=True)
        bank_markup = InlineKeyboardMarkup(row_width=2)
        bank_markup.add(
            InlineKeyboardButton("🏦 CBE (ንግድ ባንክ)", callback_data="pay_cbe"),
            InlineKeyboardButton("🏦 Abyssinia (አቢሲኒያ)", callback_data="pay_aby")
        )
        bank_markup.add(InlineKeyboardButton("📱 Telebirr (ቴሌብር)", callback_data="pay_tele"))
        bot.edit_message_text("<b>ለመክፈል የሚፈልጉትን የባንክ አይነት ይምረጡ፦</b>", uid, mid, reply_markup=bank_markup)

    elif call.data.startswith("pay_"):
        method = call.data.split("_")[1]
        if method == "cbe":
            acc_info = "<b>🏦 የኢትዮጵያ ንግድ ባንክ (CBE)</b>\n👤 ስም: Getamesay Fikru\n🔢 Acc: <code>1000355140206</code>"
        elif method == "aby":
            acc_info = "<b>🏦 አቢሲኒያ ባንክ (Abyssinia)</b>\n👤 ስም: Getamesay Fikru\n🔢 Acc: <code>167829104</code>"
        else:
            acc_info = "<b>📱 ቴሌብር (Telebirr)</b>\n👤 ስም: Getamesay Fikru\n🔢 ስልክ: <code>0965979124</code>"
            
        instruction = f"{acc_info}\n\n<b>📸 ክፍያውን ከፈጸሙ በኋላ የደረሰኙን ፎቶ (Screenshot) እዚህ ይላኩ።</b>"
        bot.edit_message_text(instruction, uid, mid)
        bot.register_next_step_handler(call.message, get_payment_screenshot)

    elif call.data == "adm_list":
        active_users = list(users_col.find({"active": True}))
        if not active_users:
            bot.send_message(ADMIN_ID, "ምንም ገባሪ ደንበኛ የለም።")
            return
        for u in active_users:
            u_id = u["user_id"]
            plan = PLANS.get(u.get("plan"), {"name": "N/A"})["name"]
            exp = to_eth_date(u["expiry"])
            manage_markup = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ አስወግድ", callback_data=f"adm_kick_{u_id}"))
            bot.send_message(ADMIN_ID, f"🆔 ID: {u_id}\n💰 ጥቅል: {plan}\n⏳ ማብቂያ: {exp}", reply_markup=manage_markup)

    elif call.data.startswith("adm_kick_"):
        target_id = int(call.data.split("_")[2])
        users_col.update_one({"user_id": target_id}, {"$set": {"active": False}})
        bot.answer_callback_query(call.id, "ተጠቃሚው ተወግዷል።")

    elif call.data == "adm_add_ch":
        msg = bot.send_message(ADMIN_ID, "እባክዎ መልዕክት ፎርዋርድ ያድርጉልኝ፦")
        bot.register_next_step_handler(msg, process_add_channel)

    elif call.data.startswith("approve_"):
        _, target_id, plan_id = call.data.split("_")
        target_id = int(target_id)
        days = PLANS[plan_id]["days"]
        expiry_ts = (datetime.now() + timedelta(days=days)).timestamp()
        
        users_col.update_one(
            {"user_id": target_id},
            {"$set": {"active": True, "expiry": expiry_ts, "plan": plan_id, "joined_at": time.time()}},
            upsert=True
        )
        
        bot.send_message(target_id, "<b>✅ ክፍያዎ ተረጋግጧል!</b>", reply_markup=main_menu_keyboard(target_id))
        bot.edit_message_text(f"✅ ተጠቃሚ {target_id} ጸድቋል!", ADMIN_ID, mid)

# =========================================================================
# 8. PROCESSES
# =========================================================================
def get_payment_screenshot(message):
    if not message.photo:
        bot.send_message(message.chat.id, "⚠️ ፎቶ ብቻ ይላኩ!")
        bot.register_next_step_handler(message, get_payment_screenshot)
        return
    bot.send_message(message.chat.id, "<b>✅ ደረሰኙን ተቀብያለሁ!</b>\nአሁን ደግሞ ሙሉ ስምዎን ይላኩ፦")
    bot.register_next_step_handler(message, lambda m: collect_name_and_submit(m, message))

def collect_name_and_submit(message, photo_msg):
    uid, name = message.chat.id, message.text
    markup = ReplyKeyboardMarkup(resize_keyboard=True).add("ሁሉንም ነገር ጨርሻለሁ ላክ")
    bot.send_message(uid, f"ተቀብያለሁ {name}! ለመጨረስ ከታች ያለውን ይጫኑ።", reply_markup=markup)
    bot.register_next_step_handler(message, lambda m: finalize_submission(m, photo_msg, name))

def finalize_submission(message, photo_msg, full_name):
    uid = message.chat.id
    user_data = users_col.find_one({"user_id": uid})
    plan_id = user_data.get("pending_plan", "plan1")
    
    approve_markup = InlineKeyboardMarkup().add(
        InlineKeyboardButton("✅ Approve", callback_data=f"approve_{uid}_{plan_id}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"reject_{uid}")
    )
    
    bot.send_message(ADMIN_ID, f"💰 አዲስ ክፍያ ከ {full_name} ({uid})")
    bot.forward_message(ADMIN_ID, uid, photo_msg.message_id)
    bot.send_message(ADMIN_ID, "ያረጋግጡ፦", reply_markup=approve_markup)
    bot.send_message(uid, "✅ ተልኳል። አድሚኑ እስኪያረጋግጥ ይጠብቁ።", reply_markup=main_menu_keyboard(uid))

def process_add_channel(message):
    if not message.forward_from_chat:
        bot.send_message(ADMIN_ID, "❌ ፎርዋርድ ያድርጉ!")
        return
    ch_id, ch_name = message.forward_from_chat.id, message.forward_from_chat.title
    channels_col.update_one({"id": ch_id}, {"$set": {"name": ch_name}}, upsert=True)
    bot.send_message(ADMIN_ID, f"✅ {ch_name} ተጨምሯል።")

# =========================================================================
# 9. RUN BOT
# =========================================================================
if __name__ == "__main__":
    start_keep_alive()
    threading.Thread(target=auto_kick_worker, daemon=True).start()
    bot.infinity_polling()
