import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient
from datetime import datetime, timedelta
from ethiopian_date import EthiopianDateConverter # pip install ethiopian-date
from flask import Flask
from threading import Thread

# ------------------- KEEP ALIVE (Uptime) -------------------
app = Flask('')
@app.route('/')
def home(): return "Bot is running"
def run_web(): app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
def keep_alive(): Thread(target=run_web, daemon=True).start()

# ------------------- CONFIG (Environment Variables) -------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
MONGO_URI = os.getenv("MONGO_URI")

bot = telebot.TeleBot(BOT_TOKEN)
client = MongoClient(MONGO_URI)
db = client["vipbot"]
users_col = db["users"]

# ------------------- VIP CHANNELS & PLANS -------------------
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

# ------------------- HELPERS -------------------
def to_ethiopian(gregorian_ts):
    """የፈረንጆችን ሰዓት ወደ ኢትዮጵያ ቀን ቀያሪ"""
    dt = datetime.fromtimestamp(gregorian_ts)
    conv = EthiopianDateConverter.to_ethiopian(dt.year, dt.month, dt.day)
    return f"{conv[2]}/{conv[1]}/{conv[0]}"

def get_channel_markup(user_id, expiry_ts):
    """የቻናል በተኖችን ከነ ✅/☑️ ምልክታቸው የሚያመጣ"""
    markup = InlineKeyboardMarkup()
    all_joined = True
    for ch in VIP_CHANNELS:
        try:
            member = bot.get_chat_member(ch["id"], user_id)
            status = "✅" if member.status in ['member', 'administrator', 'creator'] else "☑️"
            if status == "☑️": all_joined = False
            invite = bot.create_chat_invite_link(ch["id"], member_limit=1, expire_date=int(expiry_ts))
            markup.add(InlineKeyboardButton(f"{status} {ch['name']}", url=invite.invite_link))
        except:
            markup.add(InlineKeyboardButton(f"🔗 Join {ch['name']}", url="https://t.me/example"))
    
    if not all_joined:
        markup.add(InlineKeyboardButton("🔄 ምልክቶቹን አድስ (Refresh)", callback_data=f"refresh_{user_id}"))
    return markup

# ------------------- COMMANDS -------------------
@bot.message_handler(commands=["start"])
def start(message):
    user_id = message.from_user.id
    if user_id == ADMIN_ID:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📋 የደንበኞች ዝርዝር", callback_data="admin_list"))
        markup.add(InlineKeyboardButton("📢 መልዕክት ላክ (Broadcast)", callback_data="admin_bc"))
        bot.send_message(ADMIN_ID, "🛠 **የአድሚን መቆጣጠሪያ ፓነል**\nእንኳን ደህና መጡ ጌታዬ!", reply_markup=markup, parse_mode="Markdown")
        return

    markup = InlineKeyboardMarkup()
    for key, plan in PLANS.items():
        markup.add(InlineKeyboardButton(plan["label"], callback_data=key))
    bot.send_message(user_id, "👋 እንኳን ወደ VIP ቻናሎቻችን በደህና መጡ!\n\n✅ ከታች ካሉት ጥቅሎች የሚፈልጉትን በመምረጥ አባል ይሁኑ:", reply_markup=markup)

# ------------------- CALLBACK ROUTER -------------------
@bot.callback_query_handler(func=lambda call: True)
def router(call):
    user_id = call.from_user.id
    mid = call.message.message_id

    # 1. ጥቅል መምረጥ
    if call.data in PLANS:
        users_col.update_one({"user_id": user_id}, {"$set":{"plan": call.data, "username": call.from_user.username}}, upsert=True)
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🏦 CBE Bank", callback_data="p_cbe"),
                   InlineKeyboardButton("🏦 Abyssinia", callback_data="p_aby"))
        markup.add(InlineKeyboardButton("📱 Telebirr", callback_data="p_tele"))
        markup.add(InlineKeyboardButton("🔙 ተመለስ", callback_data="back_home"))
        bot.edit_message_text("💳 እባክዎ የክፍያ አማራጭ ይምረጡ:", user_id, mid, reply_markup=markup)

    # 2. ወደ ኋላ መመለስ
    elif call.data == "back_home":
        markup = InlineKeyboardMarkup()
        for key, plan in PLANS.items():
            markup.add(InlineKeyboardButton(plan["label"], callback_data=key))
        bot.edit_message_text("👋 ጥቅል ይምረጡ:", user_id, mid, reply_markup=markup)

    # 3. የባንክ መረጃ ማሳየት
    elif call.data.startswith("p_"):
        method = call.data.split("_")[1].upper()
        acc_info = "1000355140206 (CBE)" if method == "CBE" else "167829104 (ABY)" if method == "ABY" else "0965979124 (Telebirr)"
        text = f"🏦 **{method} ክፍያ መረጃ**\n\n👤 ስም: Getamesay Fikru\n🔢 ቁጥር: `{acc_info}`\n\n📸 የከፈሉበትን **Screenshot** እዚህ ይላኩ።"
        bot.edit_message_text(text, user_id, mid, parse_mode="Markdown")
        bot.register_next_step_handler(call.message, get_screenshot)

    # 4. አድሚን - የተጠቃሚዎች ዝርዝር (በቀሪ ቀን የተደረደሩ)
    elif call.data == "admin_list":
        users = list(users_col.find({"active": True}).sort("expiry", 1))
        if not users:
            bot.send_message(ADMIN_ID, "❌ ምንም ንቁ የቪአይፒ ደንበኛ የለም።")
            return
        
        report = "👥 **ንቁ ደንበኞች (ጊዜያቸው ለሚጠናቀቅ ቅድሚያ)**\n\n"
        for u in users:
            remaining = datetime.fromtimestamp(u['expiry']) - datetime.now()
            days_left = remaining.days
            report += f"👤 @{u.get('username','N/A')} | ⏳ {max(0, days_left)} ቀን ቀርቷል\n📅 ማብቂያ፡ {to_ethiopian(u['expiry'])}\n🆔 `{u['user_id']}`\n\n"
        bot.send_message(ADMIN_ID, report, parse_mode="Markdown")

    # 5. አድሚን - Broadcast
    elif call.data == "admin_bc":
        msg = bot.send_message(ADMIN_ID, "📝 ለሁሉም ተጠቃሚዎች የሚላከውን መልዕክት ይጻፉ (ወይም ፋይል ይላኩ)፡\n(ለመሰረዝ 'cancel' ይበሉ)")
        bot.register_next_step_handler(msg, run_broadcast)

    # 6. ክፍያ ማጽደቅ (Approve)
    elif call.data.startswith("approve_"):
        tid = int(call.data.split("_")[1])
        udata = users_col.find_one({"user_id": tid})
        if not udata or "plan" not in udata: return
        
        plan = PLANS[udata["plan"]]
        exp_ts = (datetime.now() + timedelta(days=plan["duration"])).timestamp()
        users_col.update_one({"user_id": tid}, {"$set": {"expiry": exp_ts, "active": True}})
        
        eth_date = to_ethiopian(exp_ts)
        text = f"🎉 እንኳን ደስ አለዎት! **{plan['text']}** የቪአይፒ አባልነትዎ ጸድቋል።\n📅 የሚያበቃው፡ **{eth_date} (በኢትዮጵያ አቆጣጠር)**\n\nቻናሎቹን ከታች ባሉት በተኖች ይቀላቀሉ፡"
        bot.send_message(tid, text, parse_mode="Markdown", reply_markup=get_channel_markup(tid, exp_ts))
        bot.edit_message_text(f"✅ ተጠቃሚ {tid} ጸድቋል", user_id, mid)

    # 7. የቻናል ሁኔታን ማደስ (Refresh)
    elif call.data.startswith("refresh_"):
        udata = users_col.find_one({"user_id": user_id})
        if udata:
            bot.edit_message_reply_markup(user_id, mid, reply_markup=get_channel_markup(user_id, udata['expiry']))
            bot.answer_callback_query(call.id, "ሁኔታው ታድሷል! ✅")

# ------------------- LOGIC -------------------
def get_screenshot(message):
    if not message.photo:
        bot.reply_to(message, "📸 እባክዎ የክፍያውን ፎቶ (Screenshot) ይላኩ።")
        return
    
    bot.send_message(ADMIN_ID, f"💰 **አዲስ የክፍያ ጥያቄ**\n👤 ተጠቃሚ: @{message.from_user.username}\n🆔 ID: `{message.from_user.id}`")
    bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
    
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ አጽድቅ (Approve)", callback_data=f"approve_{message.from_user.id}"))
    bot.send_message(ADMIN_ID, "ይህ ክፍያ ትክክል ነው?", reply_markup=markup)
    bot.send_message(message.chat.id, "✅ ማስረጃው ተልኳል! አድሚኑ ሲያጸድቅ መልዕክት ይደርስዎታል።")

def run_broadcast(message):
    if message.text and message.text.lower() == 'cancel':
        bot.send_message(ADMIN_ID, "❌ ተሰርዟል።")
        return
    
    all_users = users_col.find()
    success = 0
    for u in all_users:
        try:
            bot.copy_message(u['user_id'], ADMIN_ID, message.message_id)
            success += 1
        except: pass
    bot.send_message(ADMIN_ID, f"📢 መልዕክቱ ለ {success} ተጠቃሚዎች በተሳካ ሁኔታ ተልኳል!")

# ------------------- MAIN -------------------
if __name__ == "__main__":
    keep_alive()
    print("Bot is starting...")
    bot.infinity_polling()
