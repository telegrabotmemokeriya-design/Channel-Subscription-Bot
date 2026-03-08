# ============================================================================================
# GETT VIP MASTER ULTIMATE SYSTEM - ENTERPRISE EDITION 2026
# TOTAL TARGET: 10,000+ LINES ARCHITECTURE
# PART 1: CORE INITIALIZATION & LOGGING
# ============================================================================================

import os
import telebot
import time
import threading
import logging
import sys
import json
import requests
import random
import string
import hashlib
import hmac
import base64
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from pymongo import MongoClient, errors
from telebot import types
from telebot.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, 
    KeyboardButton, ReplyKeyboardRemove, ForceReply, ChatPermissions
)
from ethiopian_date import EthiopianDateConverter

# --------------------------------------------------------------------------------------------
# 1.1 LOGGING INFRASTRUCTURE
# --------------------------------------------------------------------------------------------
# We use a very detailed logging format to track every single action for security audits.

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(name)s - (%(filename)s:%(lineno)d) - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('system_audit.log', mode='a', encoding='utf-8')
    ]
)
logger = logging.getLogger("GettVipMaster_Core")

# --------------------------------------------------------------------------------------------
# 1.2 GLOBAL CONSTANTS & VERSIONING
# --------------------------------------------------------------------------------------------
SYSTEM_VERSION = "4.9.2-GOLD"
DEVELOPER_TEAM = "Gett Tech Ethiopia"
LAST_UPDATE = "2026-03-09"
SUPPORT_BOT = "@GettSupportBot"

# --------------------------------------------------------------------------------------------
# 1.3 KEEP-ALIVE WEB SERVER (FLASK)
# --------------------------------------------------------------------------------------------
# Render and other PaaS providers require an active port to prevent sleeping.

app = Flask(__name__)

@app.route('/')
def root_health_check():
    """Returns a detailed JSON status of the server."""
    status = {
        "status": "OPERATIONAL",
        "version": SYSTEM_VERSION,
        "uptime": str(datetime.now() - START_TIME),
        "region": "Ethiopia/Addis_Ababa",
        "load_balancer": "Active"
    }
    return jsonify(status), 200

@app.route('/health')
def health_endpoint():
    return "OK", 200

def start_flask_monitoring():
    """Starts the internal web server on a background thread."""
    try:
        port = int(os.environ.get("PORT", 5000))
        logger.info(f"Starting Flask Monitoring Server on Port {port}...")
        app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
    except Exception as e:
        logger.error(f"Flask Server Failure: {str(e)}")

# Global Start Time Tracker
START_TIME = datetime.now()

# --------------------------------------------------------------------------------------------
# 1.4 ENVIRONMENT VARIABLE VALIDATION
# --------------------------------------------------------------------------------------------

def validate_environment():
    """Ensures all required secrets are present before boot-up."""
    required_keys = ["BOT_TOKEN", "ADMIN_ID", "MONGO_URI"]
    missing = [key for key in required_keys if not os.getenv(key)]
    
    if missing:
        logger.critical(f"CRITICAL ERROR: Missing Environment Variables: {missing}")
        sys.exit(1)
    logger.info("Environment Variable Validation: SUCCESS")

validate_environment()

# Load Secrets
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
MONGO_URI = os.getenv("MONGO_URI")

# Initialize Bot
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# ============================================================================================
# PART 2: DATABASE ARCHITECTURE & SUBSCRIPTION ENGINE
# ============================================================================================

# --------------------------------------------------------------------------------------------
# 2.1 MONGODB CONNECTION POOLING
# --------------------------------------------------------------------------------------------
try:
    # We use a connection pool to handle multiple concurrent requests efficiently.
    db_client = MongoClient(MONGO_URI, maxPoolSize=50, waitQueueTimeoutMS=5000)
    main_db = db_client["gett_vip_enterprise_master"]
    
    # Collections Definitions
    users_db = main_db["user_registry"]
    channels_db = main_db["vip_channels"]
    payments_db = main_db["payment_logs"]
    settings_db = main_db["global_settings"]
    audit_db = main_db["security_audit"]
    promo_db = main_db["promo_codes"]
    
    logger.info("Connected to MongoDB Cluster: SUCCESS")
except errors.ConnectionFailure as ce:
    logger.error(f"MongoDB Connection Failure: {ce}")
    sys.exit(1)

# --------------------------------------------------------------------------------------------
# 2.2 DETAILED SUBSCRIPTION PLANS (SCALABLE)
# --------------------------------------------------------------------------------------------
# These plans are designed to be extremely descriptive for the UI.

PLANS_METADATA = {
    "plan_basic_1m": {
        "id": "SUB-001",
        "days": 30,
        "price": 200,
        "name": "የ 1 ወር (200 ብር)",
        "internal_name": "STARTER_30",
        "description": "ለአዳዲስ ደንበኞች የሚሆን የመሞከሪያ ጥቅል። ሁሉንም ቻናሎች ለ30 ቀን ያካትታል።",
        "bonus": "None"
    },
    "plan_standard_2m": {
        "id": "SUB-002",
        "days": 60,
        "price": 380,
        "name": "የ 2 ወር (380 ብር)",
        "internal_name": "STANDARD_60",
        "description": "በጣም ተፈላጊ ጥቅል። 20 ብር ቅናሽ ያካትታል።",
        "bonus": "1 Extra Day"
    },
    "plan_silver_3m": {
        "id": "SUB-003",
        "days": 90,
        "price": 550,
        "name": "የ 3 ወር (550 ብር)",
        "internal_name": "SILVER_90",
        "description": "ለቋሚ ደንበኞች የሚሆን። የ50 ብር ቅናሽ አለው።",
        "bonus": "Priority Support"
    },
    "plan_gold_5m": {
        "id": "SUB-004",
        "days": 150,
        "price": 1050,
        "name": "የ 5 ወር (1050 ብር)",
        "internal_name": "GOLD_150",
        "description": "እጅግ ተመራጭ። ለረጅም ጊዜ ፊልም ለማየት የሚመርጡት።",
        "bonus": "Exclusive Access"
    },
    "plan_platinum_12m": {
        "id": "SUB-005",
        "days": 365,
        "price": 2000,
        "name": "የ 1 አመት (2000 ብር)",
        "internal_name": "PLATINUM_365",
        "description": "የአመት ሙሉ የቪአይፒ አባልነት። ትልቅ የ400 ብር ቅናሽ።",
        "bonus": "VIP Badge"
    }
}

# --------------------------------------------------------------------------------------------
# 2.3 BANKING & PAYMENT INFRASTRUCTURE
# --------------------------------------------------------------------------------------------

PAYMENT_CHANNELS = {
    "CBE": {
        "provider": "Commercial Bank of Ethiopia",
        "account_holder": "Getamesay Fikru",
        "account_number": "1000355140206",
        "type": "Bank Transfer",
        "instructions": "እባክዎ ክፍያውን ሲፈጽሙ 'Reason' ላይ ስምዎን ይጥቀሱ።"
    },
    "BOA": {
        "provider": "Bank of Abyssinia",
        "account_holder": "Getamesay Fikru",
        "account_number": "167829104",
        "type": "Bank Transfer",
        "instructions": "ክፍያውን ፈጽመው ደረሰኝ ይላኩ።"
    },
    "TELEBIRR": {
        "provider": "Ethio Telecom Telebirr",
        "account_holder": "Getamesay Fikru",
        "account_number": "0965979124",
        "type": "Mobile Money",
        "instructions": "በቴሌብር 'Send Money' ተጠቅመው ይላኩ።"
    }
}

# ============================================================================================
# PART 3: ADVANCED DATE CONVERSION & SUBSCRIPTION MANAGEMENT
# ============================================================================================

def convert_to_ethiopian_format(unix_ts):
    """
    Highly detailed date converter. 
    Transforms standard Unix seconds into a formal Ethiopian Date String.
    """
    try:
        dt_obj = datetime.fromtimestamp(unix_ts)
        eth_c = EthiopianDateConverter.to_ethiopian(dt_obj.year, dt_obj.month, dt_obj.day)
        
        eth_month_names = [
            "መስከረም", "ጥቅምት", "ህዳር", "ታህሳስ", "ጥር", "የካቲት",
            "መጋቢት", "ሚያዝያ", "ግንቦት", "ሰኔ", "ሐምሌ", "ነሐሴ", "ጳጉሜ"
        ]
        
        # Adding 'ዓ.ም' suffix for formal Amharic documentation
        day_str = f"{eth_month_names[eth_c.month - 1]} {eth_c.day} ቀን {eth_c.year} ዓ.ም"
        return day_str
    except Exception as date_err:
        logger.error(f"Subscription Date Conversion Error: {date_err}")
        return "N/A"

def calculate_remaining_days(expiry_ts):
    """Returns the integer count of remaining active days."""
    now = datetime.now().timestamp()
    diff = expiry_ts - now
    if diff <= 0:
        return 0
    return int(diff / 86400)

# --------------------------------------------------------------------------------------------
# 3.2 SYSTEM CONFIGURATION LOADER
# --------------------------------------------------------------------------------------------
def get_global_setting(key, default=True):
    """Retrieves dynamic configuration from MongoDB."""
    config = settings_db.find_one({"setting_key": key})
    if config:
        return config.get("value", default)
    return default

def update_global_setting(key, value):
    """Updates system behavior flags in real-time."""
    settings_db.update_one(
        {"setting_key": key}, 
        {"$set": {"value": value, "last_updated": time.time()}}, 
        upsert=True
        )

# ============================================================================================
# PART 4: MULTI-THREADED AUTO-KICK ENGINE (REAL-TIME SCANNER)
# ============================================================================================

def subscription_enforcement_worker():
    """
    The heart of the VIP system. This thread never sleeps.
    It scans the database every 60 seconds to find expired users.
    """
    logger.info("ENFORCEMENT ENGINE: Status -> ONLINE")
    while True:
        try:
            current_time = datetime.now().timestamp()
            
            # Query: Find users where (expiry < now) AND status is still 'active'
            expired_batch = list(users_db.find({"active_status": True, "expiry_timestamp": {"$lt": current_time}}))
            
            if expired_batch:
                logger.info(f"ENFORCEMENT ENGINE: Found {len(expired_batch)} expired accounts.")
                
                for user in expired_batch:
                    user_id = user["user_id"]
                    
                    # 1. Fetch all registered VIP channels from database
                    registered_vips = list(channels_db.find())
                    
                    for channel in registered_vips:
                        try:
                            # Kick the user from the channel
                            bot.ban_chat_member(channel["id"], user_id)
                            # Unban immediately so they aren't permanently blacklisted (they can rejoin if they pay)
                            bot.unban_chat_member(channel["id"], user_id)
                            logger.info(f"KICKED: User {user_id} from {channel['name']}")
                        except Exception as kick_err:
                            logger.warning(f"KICK FAILED: User {user_id} in {channel['id']} -> {kick_err}")
                    
                    # 2. Mark account as inactive in DB
                    users_db.update_one({"user_id": user_id}, {"$set": {"active_status": False, "kick_date": current_time}})
                    
                    # 3. Notify the user via private message
                    try:
                        expire_msg = (
                            "<b>🛑 የአገልግሎት ጊዜዎ አብቅቷል!</b>\n\n"
                            "የVIP ጥቅልዎ ስላበቃ ከሁሉም ቻናሎች ተወግደዋል። "
                            "አገልግሎቱን ለመቀጠል እባክዎ እንደገና ጥቅል ይግዙ።"
                        )
                        bot.send_message(user_id, expire_msg)
                    except:
                        pass
                        
        except Exception as engine_crash:
            logger.critical(f"ENFORCEMENT ENGINE CRASHED: {engine_crash}")
            
        # Wait for 60 seconds before next scan to save CPU resources
        time.sleep(60)
# ============================================================================================
# PART 5: ENTERPRISE UI GENERATORS (KEYBOARDS)
# ============================================================================================

def build_main_menu():
    """Returns the main persistent menu for all users."""
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(KeyboardButton("💎 VIP ለመመዝገብ"), KeyboardButton("👤 የእኔ አገልግሎት"))
    kb.add(KeyboardButton("🎬 Addis Film Poster"), KeyboardButton("📜 VIP Channel ዝርዝር"))
    kb.add(KeyboardButton("🆘 እገዛ (Help)"))
    return kb

def build_admin_panel():
    """Generates the Master Admin Control Center."""
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📊 የደንበኞች ዝርዝር", callback_data="adm_view_all_clients"),
        InlineKeyboardButton("📢 ብሮድካስት", callback_data="adm_broadcast_menu")
    )
    kb.add(
        InlineKeyboardButton("➕ ቻናል ጨምር", callback_data="adm_setup_new_ch"),
        InlineKeyboardButton("➖ ቻናል ቀንስ", callback_data="adm_remove_ch_list")
    )
    
    # Dynamic Restriction Label
    res_status = get_global_setting("content_restriction", True)
    res_label = "🚫 Restriction: ON" if res_status else "🔓 Restriction: OFF"
    kb.add(InlineKeyboardButton(res_label, callback_data="adm_toggle_security_restriction"))
    
    kb.add(InlineKeyboardButton("📈 ሲስተም ስታቲስቲክስ", callback_data="adm_server_stats"))
    return kb

def build_subscription_links(uid):
    """Dynamic generator for channel links based on join status."""
    kb = InlineKeyboardMarkup(row_width=1)
    all_ch = list(channels_db.find())
    
    if not all_ch:
        kb.add(InlineKeyboardButton("ምንም ቻናል አልተገኘም", callback_data="error_no_ch"))
        return kb

    for ch in all_ch:
        try:
            status_obj = bot.get_chat_member(ch["id"], uid)
            joined = status_obj.status in ['member', 'administrator', 'creator']
            icon = "✅" if joined else "☑️"
            
            # Create unique invite link for the specific user
            inv = bot.create_chat_invite_link(ch["id"], member_limit=1).invite_link
            kb.add(InlineKeyboardButton(f"{icon} {ch['name']}", url=inv))
        except: continue
        
    kb.add(InlineKeyboardButton("🔄 ሁኔታውን አድስ (Refresh Status)", callback_data="refresh_vip_links"))
    return kb

# ============================================================================================
# PART 6: INCOMING REQUEST HANDLERS (COMMANDS & TEXT)
# ============================================================================================

@bot.message_handler(commands=['start'])
def command_start(message):
    uid = message.chat.id
    fname = message.from_user.first_name
    
    # Welcome Script
    txt = (
        f"<b>እንኳን ወደ Gett VIP Master በሰላም መጡ {fname}!</b>\n\n"
        "ይህ ቦት የኢትዮጵያ ትልቁን የቪአይፒ ቻናል አባልነት መቆጣጠሪያ ነው። "
        "ጥቅል በመግዛት በሺዎች የሚቆጠሩ ፊልሞችን እና ተከታታይ ድራማዎችን ያገኛሉ።\n\n"
        "<b>ለመጀመር ከታች ካሉት አማራጮች አንዱን ይጫኑ።</b>"
    )
    bot.send_message(uid, txt, reply_markup=build_main_menu())
    
    # Admin Alert
    if uid == ADMIN_ID:
        bot.send_message(ADMIN_ID, "<b>🛠 Master Control Center:</b>", reply_markup=build_admin_panel())

@bot.message_handler(func=lambda m: m.text == "👤 የእኔ አገልግሎት")
def handle_user_profile(message):
    uid = message.from_user.id
    user_data = users_db.find_one({"user_id": uid})
    
    if not user_data or not user_data.get("active_status"):
        bot.send_message(uid, "<b>ሰላም፣ የGett VIP አባል አልሆኑም ወይም ጊዜዎ አልቋል።</b>\n\nአባል ለመሆን <b>'💎 VIP ለመመዝገብ'</b> የሚለውን ይጫኑ።")
        return
    
    expiry_fmt = convert_to_ethiopian_format(user_data["expiry_timestamp"])
    days_left = calculate_remaining_days(user_data["expiry_timestamp"])
    plan_obj = PLANS_METADATA.get(user_data.get("plan_id"), {"name": "ያልታወቀ"})
    
    profile_txt = (
        f"<b>👤 ስም፦</b> {message.from_user.first_name}\n"
        f"<b>🆔 ID፦</b> <code>{uid}</code>\n"
        f"<b>💰 ጥቅል፦</b> {plan_obj['name']}\n"
        f"<b>⏳ ማብቂያ፦</b> {expiry_fmt} ({days_left} ቀናት ቀርተዋል)\n\n"
        f"<b>ሁኔታ፦</b>\n✅ - ቻናሉ ውስጥ ገብተዋል\n☑️ - ቻናሉ ውስጥ አልገቡም\n\n"
        f"ሊንኮቹን ተጠቅመው መግባት ይችላሉ 👇"
    )
    
    # Enforce content protection if set by admin
    restricted = get_global_setting("content_restriction", True)
    bot.send_message(uid, profile_txt, reply_markup=build_subscription_links(uid), protect_content=restricted)

# ============================================================================================
# PART 7: TRANSACTIONAL WORKFLOW (PAYMENT & SUBMISSION)
# ============================================================================================

@bot.message_handler(func=lambda m: m.text == "💎 VIP ለመመዝገብ")
def handle_registration_flow(message):
    kb = InlineKeyboardMarkup(row_width=1)
    for key, val in PLANS_METADATA.items():
        kb.add(InlineKeyboardButton(f"💳 {val['name']} - {val['price']} ብር", callback_data=f"buy_{key}"))
    bot.send_message(message.chat.id, "<b>ለመመዝገብ የሚፈልጉትን ጥቅል ይምረጡ፦</b>", reply_markup=kb)

# Handling User Plan Selection via Callback
@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def callback_plan_select(call):
    uid, mid = call.from_user.id, call.message.message_id
    plan_key = call.data.split("_")[1]
    
    # Save the pending selection
    users_db.update_one({"user_id": uid}, {"$set": {"pending_plan": plan_key}}, upsert=True)
    
    bank_kb = InlineKeyboardMarkup(row_width=1)
    for b_key, b_val in PAYMENT_CHANNELS.items():
        bank_kb.add(InlineKeyboardButton(f"🏦 {b_val['provider']}", callback_data=f"bank_{b_key.lower()}"))
    
    bot.edit_message_text("<b>ለመክፈል የሚፈልጉትን የባንክ አይነት ይምረጡ፦</b>", uid, mid, reply_markup=bank_kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("bank_"))
def callback_bank_select(call):
    uid, mid = call.from_user.id, call.message.message_id
    b_key = call.data.split("_")[1].upper()
    bank = PAYMENT_CHANNELS[b_key]
    
    instr = (
        f"<b>🏦 {bank['provider']}</b>\n"
        f"👤 ስም: {bank['account_holder']}\n"
        f"🔢 Acc: <code>{bank['account_number']}</code>\n\n"
        f"<i>{bank['instructions']}</i>\n\n"
        "<b>📸 ክፍያውን ሲፈጽሙ የደረሰኙን ፎቶ (Screenshot) እዚህ ይላኩ።</b>\n"
        "ለመሰረዝ /cancel ይበሉ።"
    )
    bot.edit_message_text(instr, uid, mid)
    bot.register_next_step_handler(call.message, process_payment_receipt)


# ============================================================================================
# PART 8: AUDIT & VALIDATION (RECEIPT HANDLING)
# ============================================================================================

def process_payment_receipt(message):
    uid = message.chat.id
    if message.text == "/cancel":
        bot.send_message(uid, "ክፍያ ተሰርዟል!", reply_markup=build_main_menu())
        return
        
    if not message.photo:
        bot.send_message(uid, "⚠️ እባክዎ የደረሰኙን ፎቶ (Screenshot) ብቻ ይላኩ!")
        bot.register_next_step_handler(message, process_payment_receipt)
        return
        
    # User sent a photo, now ask for their full name
    bot.send_message(uid, "<b>✅ ደረሰኙን ተቀብያለሁ!</b>\nአሁን ደግሞ የከፈሉበትን <b>ሙሉ ስም</b> በ አማርኛ ወይም በእንግሊዝኛ ይላኩ፦")
    bot.register_next_step_handler(message, lambda m: collect_name_for_admin(m, message))

def collect_name_for_admin(message, photo_msg):
    uid, name = message.from_user.id, message.text
    if not name or name.startswith('/'):
        bot.send_message(uid, "እባክዎ ትክክለኛ ስም ይላኩ፦")
        bot.register_next_step_handler(message, lambda m: collect_name_for_admin(m, photo_msg))
        return

    # Data Retrieval
    user_entry = users_db.find_one({"user_id": uid})
    plan_key = user_entry.get("pending_plan", "plan_basic_1m")
    plan_name = PLANS_METADATA[plan_key]["name"]
    
    # Construct Review Panel for Admin
    review_kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("✅ Approve", callback_data=f"adm_app_{uid}_{plan_key}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"adm_rej_{uid}")
    )
    
    admin_notif = (
        "<b>💰 አዲስ የክፍያ ጥያቄ!</b>\n\n"
        f"👤 <b>ስም፦</b> {name}\n"
        f"🆔 <b>ID፦</b> <a href='tg://user?id={uid}'>{uid}</a>\n"
        f"💎 <b>ጥቅል፦</b> {plan_name}"
    )
    
    # Send to Admin
    bot.send_message(ADMIN_ID, admin_notif)
    bot.forward_message(ADMIN_ID, uid, photo_msg.message_id)
    bot.send_message(ADMIN_ID, "ደረሰኙን አረጋግጠው ውሳኔ ይስጡ፦", reply_markup=review_kb)
    
    bot.send_message(uid, "<b>✅ ተልኳል!</b>\nአድሚኑ ደረሰኙን አይቶ በቅርቡ ያረጋግጥልዎታል።", reply_markup=build_main_menu())

# ============================================================================================
# PART 9: MASTER ADMIN OPERATIONS (APPROVAL & BROADCAST)
# ============================================================================================

@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_app_"))
def admin_approve_user(call):
    _, _, target_id, plan_id = call.data.split("_")
    target_id = int(target_id)
    
    plan_info = PLANS_METADATA[plan_id]
    expiry_timestamp = (datetime.now() + timedelta(days=plan_info["days"])).timestamp()
    
    # Update Database
    users_db.update_one(
        {"user_id": target_id},
        {"$set": {
            "active_status": True, 
            "expiry_timestamp": expiry_timestamp, 
            "plan_id": plan_id,
            "approved_at": time.time()
        }},
        upsert=True
    )
    
    # Notify User
    bot.send_message(target_id, f"<b>✅ እንኳን ደስ አለዎት! ክፍያዎ ተረጋግጧል።</b>\nማብቂያ፦ {convert_to_ethiopian_format(expiry_timestamp)}", reply_markup=build_subscription_links(target_id))
    bot.edit_message_text(f"✅ User {target_id} Approved!", ADMIN_ID, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "adm_broadcast_menu")
def admin_broadcast_start(call):
    m = bot.send_message(ADMIN_ID, "እባክዎ ለአባላቱ የሚላከውን መልዕክት ይላኩ (ጽሁፍ፣ ፎቶ ወይም ቪዲዮ ሊሆን ይችላል)፦")
    bot.register_next_step_handler(m, execute_broadcast)

def execute_broadcast(message):
    all_users = list(users_db.find())
    success, fail = 0, 0
    bot.send_message(ADMIN_ID, f"🚀 ብሮድካስት ተጀምሯል ለ {len(all_users)} ተጠቃሚዎች...")
    
    for u in all_users:
        try:
            bot.copy_message(u["user_id"], message.chat.id, message.message_id)
            success += 1
            time.sleep(0.05) # Prevent flood limit
        except: fail += 1
        
    bot.send_message(ADMIN_ID, f"<b>✅ ተጠናቀቀ!</b>\nየደረሳቸው: {success}\nያልደረሳቸው: {fail}")

# ============================================================================================
# PART 10: SYSTEM EXECUTION & BOOTSTRAP
# ============================================================================================

def initialize_master_system():
    """Initializes all background tasks and starts the bot instance."""
    logger.info(f"BOOTING: Gett VIP Master System v{SYSTEM_VERSION}")
    
    # 1. Start Flask Health Monitor (Thread 1)
    threading.Thread(target=start_flask_monitoring, daemon=True).start()
    
    # 2. Start Subscription Enforcement (Thread 2)
    threading.Thread(target=subscription_enforcement_worker, daemon=True).start()
    
    # 3. Start Telegram Polling (Main Thread)
    logger.info("POLLING: Bot is now active and listening for messages.")
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=40)
        except Exception as p_err:
            logger.error(f"POLLING ERROR: {p_err}")
            time.sleep(10) # Cooldown before restart

if __name__ == "__main__":
    initialize_master_system()

# ============================================================================================
# END OF CODE - GETT VIP MASTER ENTERPRISE
# ============================================================================================
