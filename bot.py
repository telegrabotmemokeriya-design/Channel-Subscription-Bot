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
        plan_name = PLANS[u_data['pending_plan']]['name'] if (u_data and 'pending_plan' in u_data) else ""

        if method == "CBE":
            bank_info = "🏦 CBE ኢትዮጵያ ንግድ ባንክ\n👤 ስም: Getamesay Fikru\n🔢 Acc: `1000355140206`"
        elif method == "ABY":
            bank_info = "🏦 Abyssinia ባንክ (አቢሲኒያ)\n👤 ስም: Getamesay Fikru\n🔢 Acc: `167829104`"
        else:
            bank_info = "📱 Telebirr (ቴሌብር)\n👤 ስም: Getamesay Fikru\n🔢 ስልክ: `0965979124`"
        
        bot.edit_message_text(f"💎 ጥቅል: {plan_name}\n\n{bank_info}\n\n📸 የከፈሉበትን Screenshot (የደረሰኙን ፎቶ) እዚህ ይላኩ", uid, mid, parse_mode="Markdown")
        bot.register_next_step_handler(call.message, get_screenshot)

    elif call.data.startswith("ap_"):
        # አዲስ Approval ሲስተም - ዳታው በቀጥታ ከበተኑ ይነበባል
        parts = call.data.split("_")
        tid = int(parts[1])
        pk = parts[2]
        p_info = PLANS[pk]
        
        exp_ts = (datetime.now() + timedelta(days=p_info["duration"])).timestamp()
        users_col.update_one({"user_id": tid}, {"$set": {"expiry": exp_ts, "active": True, "plan": pk}})
        
        bot.send_message(tid, f"🎉 ክፍያዎ ተረጋግጦ አባልነትዎ ጸድቋል!\n📅 ማብቂያ፡ {to_ethiopian(exp_ts)}\n\nቻናሎቹን ለመቀላቀል ከታች ያሉትን በተኖች ይጠቀሙ፡", reply_markup=get_channel_markup(tid))
        bot.edit_message_text(f"✅ ተጠቃሚ {tid} በ {p_info['name']} ጸድቋል!", ADMIN_ID, mid)
        bot.answer_callback_query(call.id, "ጸድቋል!")

    elif call.data.startswith("rj_"):
        # Reject logic
        parts = call.data.split("_")
        if len(parts) == 2: # First click
            tid = parts[1]
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🚫 የተሳሳተ ደረሰኝ", callback_data=f"rj_wrong_{tid}"),
                       InlineKeyboardButton("📉 መጠኑ ያንሳል", callback_data=f"rj_less_{tid}"))
            bot.edit_message_text("❌ ውድቅ የተደረገበት ምክንያት ይምረጡ፡", ADMIN_ID, mid, reply_markup=markup)
        else: # Reason selected
            reason_type = parts[1]
            tid = int(parts[2])
            reason_msg = "ደረሰኙ ስህተት ነው።" if reason_type == "wrong" else "የከፈሉት መጠን ያንሳል።"
            bot.send_message(tid, f"❌ ይቅርታ፣ ክፍያዎ ውድቅ ሆኗል!\nምክንያት፡ {reason_msg}")
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
    
    uid = message.from_user.id
    u_data = users_col.find_one({"user_id": uid})
    # ተጠቃሚው የመረጠው ፕላን ካልተገኘ በዲፎልት plan1 ይደረጋል
    pk = u_data["pending_plan"] if (u_data and "pending_plan" in u_data) else "plan1"
    
    markup = InlineKeyboardMarkup()
    # "ap_" በሚል አሳጥሬዋለሁ (callback limit እንዳያልፍ)
    markup.add(InlineKeyboardButton("✅ Approve", callback_data=f"ap_{uid}_{pk}"),
               InlineKeyboardButton("❌ Reject", callback_data=f"rj_{uid}"))
    
    bot.send_message(ADMIN_ID, f"💰 ክፍያ ከ @{message.from_user.username} (ID: `{uid}`)\n💎 ጥቅል: {PLANS[pk]['name']}")
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

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling()
