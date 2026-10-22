import telebot
import json
import requests
import time
import re
import html
import os
import threading
from flask import Flask

# ==========================================
#         CONFIG & SETUP
# ==========================================
BOT_TOKEN = "8932245478:AAFsXFzGvxOMv2fJYFqiCAFa_woyVRQNMqo"
MASTER_ADMIN = 8519288398 
FIREBASE_URL = "https://ghost-services-improve-default-rtdb.firebaseio.com/"

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
BOT_USERNAME = bot.get_me().username 

# --- FLASK WEB SERVER FOR RENDER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running perfectly on Render!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# ==========================================
#         FIREBASE HELPER FUNCTIONS
# ==========================================
def db_get(path):
    try:
        req = requests.get(f"{FIREBASE_URL}{path}.json")
        if req.status_code == 200: return req.json()
    except Exception: pass
    return None

def db_set(path, data): requests.put(f"{FIREBASE_URL}{path}.json", json=data)
def db_update(path, data): requests.patch(f"{FIREBASE_URL}{path}.json", json=data)
def db_delete(path): requests.delete(f"{FIREBASE_URL}{path}.json")

def safe_float(path, default=2.0):
    try: return float(db_get(path))
    except: return default

def safe_int(path, default=0):
    try: return int(db_get(path))
    except: return default

def is_admin(user_id):
    if user_id == MASTER_ADMIN: return True
    return user_id in (db_get("settings/admins") or [])

def is_banned(user_id):
    u = db_get(f"users/{user_id}")
    return u and u.get("status") == "Banned"

def get_unjoined_channels(user_id):
    force_channels = db_get("settings/force_channels") or {}
    unjoined = []
    for cid, cdata in force_channels.items():
        try:
            status = bot.get_chat_member(cid, user_id).status
            if status not in ['member', 'administrator', 'creator']: unjoined.append(cid)
        except: unjoined.append(cid)
    return unjoined

def is_vip(user_id):
    u = db_get(f"users/{user_id}") or {}
    return u.get("vip_until", 0) > time.time()

def normalize_dict(data):
    if isinstance(data, dict): return data
    if isinstance(data, list): return {str(i): v for i, v in enumerate(data) if v is not None}
    return {}

def get_stock_list(sdata):
    stk = sdata.get('stock', [])
    if isinstance(stk, dict):
        return [v for k, v in sorted(stk.items(), key=lambda item: int(item[0]))]
    return stk or []

def htmlescape(text):
    return html.escape(str(text))

# Advanced Edit Msg to prevent silent hang errors!
def edit_msg(call, text, kb=None):
    try: bot.answer_callback_query(call.id)
    except: pass
    try:
        if call.message.content_type == 'photo':
            bot.edit_message_caption(caption=text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=kb, parse_mode="HTML")
        else:
            bot.edit_message_text(text=text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=kb, parse_mode="HTML")
    except Exception as e:
        if "message is not modified" not in str(e).lower():
            bot.answer_callback_query(call.id, f"⚠️ UI Eʀʀᴏʀ: {str(e)[:100]}", show_alert=True)

# ==========================================
#          KEYBOARD BUILDERS 
# ==========================================
def permanent_main_menu():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(telebot.types.KeyboardButton("🏠 Mᴀɪɴ Mᴇɴᴜ"))
    return markup

def main_menu_keyboard(uid):
    vip_text = "✧ VIP Aᴄᴛɪᴠᴇ" if is_vip(uid) else "✧ VIP Mᴇᴍʙᴇʀꜱʜɪᴘ"
    return json.dumps({
        "inline_keyboard": [
            [{"text": "❖ Sᴇʀᴠɪᴄᴇꜱ ❖", "callback_data": "menu_cats", "style": "primary"}],
            [
                {"text": "⚚ Pʀᴏꜰɪʟᴇ", "callback_data": "menu_profile", "style": "primary"},
                {"text": "◈ Bᴜʏ Pᴏɪɴᴛꜱ", "callback_data": "menu_buy_points", "style": "success"}
            ],
            [
                {"text": "⟡ Rᴇꜰᴇʀ & Eᴀʀɴ", "callback_data": "menu_refer", "style": "success"},
                {"text": "⍟ Mɪʟᴇꜱᴛᴏɴᴇꜱ", "callback_data": "menu_milestones", "style": "primary"}
            ],
            [
                {"text": "ꗃ Mʏ Pᴜʀᴄʜᴀꜱᴇꜱ", "callback_data": "menu_purchases", "style": "primary"},
                {"text": vip_text, "callback_data": "menu_vip", "style": "success"}
            ],
            [{"text": "⎚ Rᴇᴅᴇᴇᴍ Cᴏᴅᴇ", "callback_data": "menu_redeem", "style": "primary"}],
            [{"text": "⚝ Oꜰꜰɪᴄɪᴀʟ Cʜᴀɴɴᴇʟ", "url": "https://t.me/GhostServicess", "style": "danger"}]
        ]
    })

def back_keyboard(callback="main_menu"):
    return json.dumps({"inline_keyboard": [[{"text": "↫ Bᴀᴄᴋ", "callback_data": callback, "style": "danger"}]]})

def join_channels_keyboard():
    kb = {"inline_keyboard": []}
    f_chans = db_get("settings/force_channels") or {}
    nf_chans = db_get("settings/non_force_channels") or {}
    for cid, cdata in f_chans.items():
        url = cdata.get("url", "")
        name = cdata.get("name", "📢 Jᴏɪɴ Cʜᴀɴɴᴇʟ")
        if url: kb["inline_keyboard"].append([{"text": f"📢 {name}", "url": url, "style": "primary"}])
    for nid, ndata in nf_chans.items():
        kb["inline_keyboard"].append([{"text": f"🔗 {ndata['name']}", "url": ndata['url'], "style": "primary"}])
    kb["inline_keyboard"].append([{"text": "✅ I Hᴀᴠᴇ Jᴏɪɴᴇᴅ", "callback_data": "check_join", "style": "success"}])
    return json.dumps(kb)

def admin_menu_keyboard():
    return json.dumps({
        "inline_keyboard": [
            [
                {"text": "❖ Nᴏʀᴍᴀʟ Sᴇʀᴠɪᴄᴇꜱ", "callback_data": "admin_cats", "style": "primary"},
                {"text": "📦 Sᴛᴏᴄᴋ Sᴇʀᴠɪᴄᴇꜱ", "callback_data": "admin_stock_cats", "style": "success"}
            ],
            [
                {"text": "⟡ Mᴀɴᴀɢᴇ Bᴀʟᴀɴᴄᴇ", "callback_data": "admin_balance", "style": "primary"},
                {"text": "📊 Aɴᴀʟʏᴛɪᴄꜱ", "callback_data": "admin_analytics", "style": "primary"}
            ],
            [
                {"text": "⎚ Rᴇᴅᴇᴇᴍ Cᴏᴅᴇꜱ", "callback_data": "admin_redeem", "style": "success"},
                {"text": "🎟️ Pʀᴏᴍᴏ Cᴏᴅᴇꜱ", "callback_data": "admin_promos", "style": "primary"}
            ],
            [
                {"text": "🎁 Rᴇꜰᴇʀ Bᴏɴᴜꜱ", "callback_data": "admin_ref_amt", "style": "primary"},
                {"text": "🎯 Mɪʟᴇꜱᴛᴏɴᴇꜱ", "callback_data": "admin_milestones", "style": "success"}
            ],
            [
                {"text": "💸 Cᴏᴍᴍɪꜱꜱɪᴏɴ %", "callback_data": "admin_comm", "style": "primary"},
                {"text": "💎 VIP Sᴇᴛᴛɪɴɢꜱ", "callback_data": "admin_vip_set", "style": "primary"}
            ],
            [
                {"text": "◈ Pᴏɪɴᴛꜱ Pʀɪᴄɪɴɢ", "callback_data": "admin_points", "style": "success"},
                {"text": "⚖️ Dᴇᴘ Lɪᴍɪᴛꜱ", "callback_data": "admin_dep_limits", "style": "primary"}
            ],
            [
                {"text": "🏆 Lᴇᴀᴅᴇʀʙᴏᴀʀᴅ", "callback_data": "admin_leaderboard", "style": "primary"},
                {"text": "⚝ Cʜᴀɴɴᴇʟꜱ Sᴇᴛᴜᴘ", "callback_data": "admin_channels", "style": "success"}
            ],
            [
                {"text": "⍟ Lᴏɢ Cʜᴀɴɴᴇʟ", "callback_data": "admin_log_channel", "style": "primary"},
                {"text": "📝 Wᴇʟᴄᴏᴍᴇ Mᴇɴᴜ", "callback_data": "admin_welcome", "style": "success"}
            ],
            [
                {"text": "🚧 Mᴀɪɴᴛᴇɴᴀɴᴄᴇ", "callback_data": "admin_maint", "style": "danger"},
                {"text": "💳 Pᴀʏᴍᴇɴᴛ UPI", "callback_data": "admin_upi", "style": "primary"}
            ],
            [
                {"text": "⚚ Aᴅᴍɪɴꜱ", "callback_data": "admin_staff", "style": "primary"},
                {"text": "ꗃ Bʀᴏᴀᴅᴄᴀꜱᴛ", "callback_data": "admin_broadcast", "style": "danger"}
            ],
            [
                {"text": "💾 Bᴀᴄᴋᴜᴘ Dᴀᴛᴀ", "callback_data": "admin_backup", "style": "success"},
                {"text": "⛔ Bᴀɴ / Uɴʙᴀɴ", "callback_data": "admin_ban", "style": "danger"}
            ],
            [{"text": "↫ Cʟᴏꜱᴇ Pᴀɴᴇʟ", "callback_data": "close_admin", "style": "danger"}]
        ]
    })

# ==========================================
#              COMMAND HANDLERS
# ==========================================
@bot.message_handler(commands=['start'])
@bot.message_handler(func=lambda message: message.text == "🏠 Mᴀɪɴ Mᴇɴᴜ")
def cmd_start(message):
    user_id = str(message.from_user.id)
    if is_banned(user_id): return bot.send_message(message.chat.id, "❖ <b>Yᴏᴜ Aʀᴇ Bᴀɴɴᴇᴅ Fʀᴏᴍ Uꜱɪɴɢ Tʜɪꜱ Bᴏᴛ!</b>", parse_mode="HTML")

    if db_get("settings/maintenance") and not is_admin(int(user_id)):
        return bot.send_message(message.chat.id, "❖ <b>Tʜᴇ Bᴏᴛ Iꜱ Cᴜʀʀᴇɴᴛʟʏ Uɴᴅᴇʀ Mᴀɪɴᴛᴇɴᴀɴᴄᴇ Fᴏʀ Uᴘɢʀᴀᴅᴇꜱ. Pʟᴇᴀꜱᴇ Cᴏᴍᴇ Bᴀᴄᴋ Lᴀᴛᴇʀ!</b>", parse_mode="HTML")

    first_name = htmlescape(message.from_user.first_name)
    args = message.text.split()
    
    user = db_get(f"users/{user_id}")
    if not user:
        user_data = {"name": first_name, "points": 0, "referrals": 0, "status": "Aᴄᴛɪᴠᴇ", "rewarded": False, "deposits_count": 0}
        if len(args) > 1 and args[1] != user_id: user_data["referred_by"] = args[1]
        db_set(f"users/{user_id}", user_data)
        user = user_data

    unjoined = get_unjoined_channels(user_id)
    if unjoined: return bot.send_message(message.chat.id, "❖ <b>Yᴏᴜ Mᴜꜱᴛ Jᴏɪɴ Aʟʟ Cʜᴀɴɴᴇʟꜱ Tᴏ Uꜱᴇ Tʜɪꜱ Pᴀɴᴇʟ!</b>", reply_markup=join_channels_keyboard(), parse_mode="HTML")

    if user.get("referred_by") and not user.get("rewarded", False):
        ref_id = user["referred_by"]
        ref_user = db_get(f"users/{ref_id}")
        if ref_user:
            ref_bonus = safe_int("settings/ref_bonus", 10)
            db_update(f"users/{ref_id}", {"points": ref_user.get("points",0) + ref_bonus, "referrals": ref_user.get("referrals",0) + 1})
            try: bot.send_message(ref_id, f"⟡ <b>Nᴇᴡ Rᴇꜰᴇʀʀᴀʟ Sᴜᴄᴄᴇꜱꜱꜰᴜʟ!</b>\n{first_name} Jᴏɪɴᴇᴅ Aɴᴅ Vᴇʀɪꜰɪᴇᴅ. <b>{ref_bonus} Pᴏɪɴᴛꜱ</b> Hᴀᴠᴇ Bᴇᴇɴ Aᴅᴅᴇᴅ Tᴏ Yᴏᴜʀ Aᴄᴄᴏᴜɴᴛ!", parse_mode="HTML")
            except: pass
        db_update(f"users/{user_id}", {"rewarded": True})

    welcome_data = db_get("settings/welcome")
    p = user.get('points', 0)
    tag = " [✧ VIP]" if is_vip(user_id) else ""
    text = f"❖ <b>Wᴇʟᴄᴏᴍᴇ Tᴏ Tʜᴇ Gᴏᴅ-Lᴇᴠᴇʟ Sᴇʀᴠɪᴄᴇ Pᴀɴᴇʟ</b> ❖\n\n✦ Hᴇʟʟᴏ <a href='tg://user?id={user_id}'>{first_name}</a>{tag}!\n⊛ <b>Yᴏᴜʀ Cᴜʀʀᴇɴᴛ Bᴀʟᴀɴᴄᴇ:</b> <code>{p} Pᴏɪɴᴛꜱ</code>\n\n<i>Sᴇʟᴇᴄᴛ Aɴ Oᴘᴛɪᴏɴ Fʀᴏᴍ Tʜᴇ Mᴇɴᴜ Bᴇʟᴏᴡ Tᴏ Pʀᴏᴄᴇᴇᴅ:</i>"
    
    if welcome_data and welcome_data.get("text"): 
        text = welcome_data.get("text").replace("{name}", first_name).replace("{points}", str(p))
    
    try:
        ghost = bot.send_message(message.chat.id, "❖", reply_markup=permanent_main_menu())
        bot.delete_message(message.chat.id, ghost.message_id)
    except Exception: pass
    
    if welcome_data and welcome_data.get("photo"):
        bot.send_photo(message.chat.id, welcome_data["photo"], caption=text, reply_markup=main_menu_keyboard(user_id), parse_mode="HTML")
    else:
        bot.send_message(message.chat.id, text, reply_markup=main_menu_keyboard(user_id), parse_mode="HTML")

@bot.message_handler(commands=['admin'])
def cmd_admin(message):
    if not is_admin(message.from_user.id): return 
    bot.send_message(message.chat.id, "⚒ <b>Aᴅᴍɪɴ Cᴏɴᴛʀᴏʟ Pᴀɴᴇʟ</b> ⚒\n\n⊛ <b>Sᴛᴀᴛᴜꜱ:</b> <code>Oɴʟɪɴᴇ & Sᴇᴄᴜʀᴇ</code>", reply_markup=admin_menu_keyboard(), parse_mode="HTML")

# ==========================================
#            GLOBAL ERROR WRAPPER
# ==========================================
@bot.callback_query_handler(func=lambda call: True)
def handle_query_wrapper(call):
    try:
        handle_query(call)
    except Exception as e:
        bot.answer_callback_query(call.id, f"⚠️ Sʏꜱᴛᴇᴍ Eʀʀᴏʀ: {str(e)[:150]}", show_alert=True)

# ==========================================
#            MAIN CALLBACK LOGIC
# ==========================================
def handle_query(call):
    user_id = str(call.from_user.id)
    d = call.data
    
    if is_banned(user_id) and not is_admin(int(user_id)):
        return bot.answer_callback_query(call.id, "❖ Yᴏᴜ Aʀᴇ Bᴀɴɴᴇᴅ Fʀᴏᴍ Tʜɪꜱ Pᴀɴᴇʟ!", show_alert=True)

    if db_get("settings/maintenance") and not is_admin(int(user_id)):
        return bot.answer_callback_query(call.id, "❖ Pᴀɴᴇʟ Iꜱ Cᴜʀʀᴇɴᴛʟʏ Uɴᴅᴇʀ Mᴀɪɴᴛᴇɴᴀɴᴄᴇ!", show_alert=True)

    if d == "check_join":
        unjoined = get_unjoined_channels(user_id)
        if unjoined: return bot.answer_callback_query(call.id, "❖ Yᴏᴜ Hᴀᴠᴇɴ'ᴛ Jᴏɪɴᴇᴅ Aʟʟ Rᴇqᴜɪʀᴇᴅ Cʜᴀɴɴᴇʟꜱ Yᴇᴛ!", show_alert=True)
        bot.delete_message(call.message.chat.id, call.message.message_id)
        call.message.text = "/start"
        call.message.from_user = call.from_user
        return cmd_start(call.message)

    user_data = db_get(f"users/{user_id}") or {"points": 0, "referrals": 0, "status": "Aᴄᴛɪᴠᴇ"}
    points = user_data.get("points", 0)

    # --- ADMIN SECURITY CHECK ---
    admin_prefixes = ["admin_", "add_cat", "acat_", "delcat_", "addsrv_", "asrv_", "delsrv_", "edprc_", "ednm_", "edtxt_", "eddel_", "viewcode_", "delcode_", "dep_", "mng_chans", "add_fch", "add_nfch", "delfch_", "delnfch_", "stcat_", "delstcat_", "adds_srv_", "ast_srv_", "dels_srv_", "eds_prc_", "eds_nm_", "eds_txt_", "add_stock_", "vprom_", "delprom_", "view_ms_", "del_ms_", "set_lb_", "brdcolor_", "brd_addbtn_", "brd_sendnow_"]
    admin_exacts = ["close_admin", "back_to_admin", "view_admin_lb", "admin_create_code", "add_stcat", "admin_backup", "add_prom", "add_ms", "tog_ms", "admin_redeem", "admin_channels", "mng_chans"]
    
    is_admin_call = any(d.startswith(p) for p in admin_prefixes) or (d in admin_exacts)
    if is_admin_call and not is_admin(int(user_id)):
        return bot.answer_callback_query(call.id, "❖ Aᴄᴄᴇꜱꜱ Dᴇɴɪᴇᴅ: Aᴅᴍɪɴ Oɴʟʏ!", show_alert=True)

    # ================== FLAT ROUTING ==================
    if d == "close_admin": bot.delete_message(call.message.chat.id, call.message.message_id)
    elif d == "back_to_admin": edit_msg(call, "⚒ <b>Aᴅᴍɪɴ Cᴏɴᴛʀᴏʟ Pᴀɴᴇʟ</b> ⚒\n\n⊛ <b>Sᴛᴀᴛᴜꜱ:</b> <code>Oɴʟɪɴᴇ & Sᴇᴄᴜʀᴇ</code>", json.dumps(json.loads(admin_menu_keyboard())))
    
    elif d == "admin_backup":
        bot.answer_callback_query(call.id, "⏳ Gᴇɴᴇʀᴀᴛɪɴɢ Sᴇᴄᴜʀᴇ Dᴀᴛᴀʙᴀꜱᴇ Bᴀᴄᴋᴜᴘ...")
        data = db_get("")
        with open("database.json", "w") as f: json.dump(data, f, indent=4)
        bot.send_document(call.message.chat.id, open("database.json", "rb"), caption="💾 <b>Cᴏᴍᴘʟᴇᴛᴇ Dᴀᴛᴀʙᴀꜱᴇ Bᴀᴄᴋᴜᴘ Fɪʟᴇ Rᴇᴀᴅʏ!</b>", parse_mode="HTML")

    elif d == "admin_maint":
        curr = db_get("settings/maintenance")
        db_update("settings", {"maintenance": not curr})
        bot.answer_callback_query(call.id, f"✅ Mᴀɪɴᴛᴇɴᴀɴᴄᴇ Mᴏᴅᴇ: {'ENABLED' if not curr else 'DISABLED'}", show_alert=True)

    elif d == "admin_welcome":
        msg = bot.send_message(call.message.chat.id, "📝 <b>Eᴅɪᴛ Wᴇʟᴄᴏᴍᴇ Mᴇɴᴜ Bᴀɴɴᴇʀ & Tᴇxᴛ</b>\n\n✦ Sᴇɴᴅ A Pʜᴏᴛᴏ ᴡɪᴛʜ Cᴀᴘᴛɪᴏɴ (Oʀ ᴊᴜꜱᴛ Tᴇxᴛ):\n<i>Uꜱᴇ {name} ꜰᴏʀ Uꜱᴇʀ Nᴀᴍᴇ, {points} ꜰᴏʀ Uꜱᴇʀ Bᴀʟᴀɴᴄᴇ.</i>\n\n<i>(Sᴇɴᴅ /cancel ᴛᴏ ꜱᴛᴏᴘ ᴏʀ 'off' ᴛᴏ ʀᴇꜱᴇᴛ ᴅᴇꜰᴀᴜʟᴛ)</i>", parse_mode="HTML")
        bot.register_next_step_handler(msg, step_welcome)

    # --- ADMIN: REDEEM CODES MANAGER ---
    elif d == "admin_redeem":
        codes = db_get("codes") or {}
        kb = {"inline_keyboard": []}
        for c_name, c_data in codes.items():
            kb["inline_keyboard"].append([{"text": f"🎫 {c_name} (Lᴇꜰᴛ: {c_data.get('uses',0)})", "callback_data": f"viewcode_{c_name}", "style": "primary"}])
        kb["inline_keyboard"].append([{"text": "➕ Cʀᴇᴀᴛᴇ Nᴇᴡ Rᴇᴅᴇᴇᴍ Cᴏᴅᴇ", "callback_data": "admin_create_code", "style": "success"}])
        kb["inline_keyboard"].append([{"text": "↫ Bᴀᴄᴋ Tᴏ Pᴀɴᴇʟ", "callback_data": "back_to_admin", "style": "danger"}])
        edit_msg(call, "⎚ <b>Mᴀɴᴀɢᴇ Rᴇᴅᴇᴇᴍ Cᴏᴅᴇꜱ & Vᴏᴜᴄʜᴇꜱ</b>", json.dumps(kb))

    elif d == "admin_create_code":
        msg = bot.send_message(call.message.chat.id, "⎚ <b>Cʀᴇᴀᴛᴇ Nᴇᴡ Rᴇᴅᴇᴇᴍ Cᴏᴅᴇ</b>\n✦ Sᴇɴᴅ Nᴇᴡ Cᴏᴅᴇ Nᴀᴍᴇ (e.g. GHOST50):\n<i>(Sᴇɴᴅ /cancel ᴛᴏ ꜱᴛᴏᴘ)</i>", parse_mode="HTML")
        bot.register_next_step_handler(msg, step_code_name)

    elif d.startswith("viewcode_"):
        code = d.split("_")[1]
        c_data = db_get(f"codes/{code}")
        if not c_data: return bot.answer_callback_query(call.id, "⚠️ Cᴏᴅᴇ Nᴏᴛ Fᴏᴜɴᴅ!", show_alert=True)
        text = f"🎫 <b>Rᴇᴅᴇᴇᴍ Cᴏᴅᴇ Sᴛᴀᴛᴜꜱ</b> 🎫\n\n✦ <b>Cᴏᴅᴇ Nᴀᴍᴇ:</b> <code>{code}</code>\n✦ <b>Rᴇᴡᴀʀᴅ Pᴏɪɴᴛꜱ:</b> <code>{c_data.get('amount')}</code>\n✦ <b>Rᴇᴍᴀɪɴɪɴɢ Uꜱᴇꜱ:</b> <code>{c_data.get('uses')}</code>"
        kb = {"inline_keyboard": [[{"text": "❌ Dᴇʟᴇᴛᴇ Tʜɪꜱ Cᴏᴅᴇ", "callback_data": f"delcode_{code}", "style": "danger"}], [{"text": "↫ Bᴀᴄᴋ", "callback_data": "admin_redeem", "style": "primary"}]]}
        edit_msg(call, text, json.dumps(kb))

    elif d.startswith("delcode_"):
        code = d.split("_")[1]
        db_delete(f"codes/{code}")
        bot.answer_callback_query(call.id, "✅ Rᴇᴅᴇᴇᴍ Cᴏᴅᴇ Sᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ Dᴇʟᴇᴛᴇᴅ!", show_alert=True)
        call.data = "admin_redeem"
        handle_query(call)

    # --- ADMIN: CHANNELS SETUP ---
    elif d == "admin_channels":
        kb = {"inline_keyboard": [
            [{"text": "➕ Aᴅᴅ Fᴏʀᴄᴇ Sᴜʙꜱᴄʀɪᴘᴛɪᴏɴ Cʜᴀɴɴᴇʟ", "callback_data": "add_fch", "style": "success"}],
            [{"text": "➕ Aᴅᴅ Exᴛᴇʀɴᴀʟ Nᴏɴ-Fᴏʀᴄᴇ Lɪɴᴋ", "callback_data": "add_nfch", "style": "primary"}],
            [{"text": "⚙️ Mᴀɴᴀɢᴇ / Rᴇᴍᴏᴠᴇ Cʜᴀɴɴᴇʟꜱ", "callback_data": "mng_chans", "style": "primary"}],
            [{"text": "↫ Bᴀᴄᴋ", "callback_data": "back_to_admin", "style": "danger"}]
        ]}
        edit_msg(call, "⚝ <b>Cʜᴀɴɴᴇʟꜱ & Fᴏʀᴄᴇ Sᴜʙꜱᴄʀɪᴘᴛɪᴏɴ Sᴇᴛᴜᴘ</b>", json.dumps(kb))

    elif d == "mng_chans":
        kb = {"inline_keyboard": []}
        f_chans = db_get("settings/force_channels") or {}
        nf_chans = db_get("settings/non_force_channels") or {}
        for cid, cdata in f_chans.items():
            kb["inline_keyboard"].append([{"text": f"❌ Fᴏʀᴄᴇ: {cdata.get('name')}", "callback_data": f"delfch_{cid}", "style": "danger"}])
        for nid, ndata in nf_chans.items():
            kb["inline_keyboard"].append([{"text": f"❌ Lɪɴᴋ: {ndata.get('name')}", "callback_data": f"delnfch_{nid}", "style": "danger"}])
        kb["inline_keyboard"].append([{"text": "↫ Bᴀᴄᴋ", "callback_data": "admin_channels", "style": "primary"}])
        edit_msg(call, "⚙️ <b>Mᴀɴᴀɢᴇ Cʜᴀɴɴᴇʟꜱ & Lɪɴᴋꜱ</b>\n<i>Cʟɪᴄᴋ Oɴ Any Cʜᴀɴɴᴇʟ Bᴇʟᴏᴡ Tᴏ Pᴇʀᴍᴀɴᴇɴᴛʟʏ Rᴇᴍᴏᴠᴇ Iᴛ:</i>", json.dumps(kb))

    elif d.startswith("delfch_"):
        cid = d.split("_")[1]
        db_delete(f"settings/force_channels/{cid}")
        bot.answer_callback_query(call.id, "✅ Fᴏʀᴄᴇ Sᴜʙ Cʜᴀɴɴᴇʟ Rᴇᴍᴏᴠᴇᴅ!", show_alert=True)
        call.data = "mng_chans"
        handle_query(call)
        return

    elif d.startswith("delnfch_"):
        nid = d.split("_")[1]
        db_delete(f"settings/non_force_channels/{nid}")
        bot.answer_callback_query(call.id, "✅ Nᴏɴ-Fᴏʀᴄᴇ Lɪɴᴋ Rᴇᴍᴏᴠᴇᴅ!", show_alert=True)
        call.data = "mng_chans"
        handle_query(call)
        return

    elif d == "add_fch":
        msg = bot.send_message(call.message.chat.id, "➕ <b>Aᴅᴅ Fᴏʀᴄᴇ Sᴜʙꜱᴄʀɪᴘᴛɪᴏɴ Cʜᴀɴɴᴇʟ</b>\n\n<i>1. Mᴀᴋᴇ ᴛʜᴇ ʙᴏᴛ Aᴅᴍɪɴ ɪɴ ʏᴏᴜʀ ᴄʜᴀɴɴᴇʟ ᴡɪᴛʜ 'Iɴᴠɪᴛᴇ ᴠɪᴀ Lɪɴᴋ' ᴘᴇʀᴍɪꜱꜱɪᴏɴ.\n2. Sᴇɴᴅ Tʜᴇ Cʜᴀɴɴᴇʟ ID, Uꜱᴇʀɴᴀᴍᴇ, Oʀ Fᴏʀᴡᴀʀᴅ ᴀ Pᴏꜱᴛ ꜰʀᴏᴍ ɪᴛ ʜᴇʀᴇ:</i>\n\n<i>(Sᴇɴᴅ /cancel ᴛᴏ ꜱᴛᴏᴘ)</i>", parse_mode="HTML")
        bot.register_next_step_handler(msg, step_add_force_ch)

    elif d == "add_nfch":
        msg = bot.send_message(call.message.chat.id, "➕ <b>Aᴅᴅ Exᴛᴇʀɴᴀʟ Nᴏɴ-Fᴏʀᴄᴇ Lɪɴᴋ</b>\n✦ Sᴇɴᴅ Tʜᴇ Display Nᴀᴍᴇ Fᴏʀ Tʜɪꜱ Bᴜᴛᴛᴏɴ:\n<i>(Sᴇɴᴅ /cancel ᴛᴏ ꜱᴛᴏᴘ)</i>", parse_mode="HTML")
        bot.register_next_step_handler(msg, step_add_nf_name)

    # --- USER: MAIN MENU NAVIGATION ---
    elif d == "main_menu":
        welcome_data = db_get("settings/welcome")
        tag = " [✧ VIP]" if is_vip(user_id) else ""
        first_name = htmlescape(call.from_user.first_name)
        text = f"❖ <b>Wᴇʟᴄᴏᴍᴇ Tᴏ Tʜᴇ Gᴏᴅ-Lᴇᴠᴇʟ Sᴇʀᴠɪᴄᴇ Pᴀɴᴇʟ</b> ❖\n\n✦ Hᴇʟʟᴏ <a href='tg://user?id={user_id}'>{first_name}</a>{tag}!\n⊛ <b>Yᴏᴜʀ Cᴜʀʀᴇɴᴛ Bᴀʟᴀɴᴄᴇ:</b> <code>{points} Pᴏɪɴᴛꜱ</code>\n\n<i>Sᴇʟᴇᴄᴛ Aɴ Oᴘᴛɪᴏɴ Fʀᴏᴍ Tʜᴇ Mᴇɴᴜ Bᴇʟᴏᴡ Tᴏ Pʀᴏᴄᴇᴇᴅ:</i>"
        if welcome_data and welcome_data.get("text"): 
            text = welcome_data.get("text").replace("{name}", first_name).replace("{points}", str(points))
        edit_msg(call, text, main_menu_keyboard(user_id))

    elif d == "menu_profile":
        tag = " [✧ VIP]" if is_vip(user_id) else ""
        text = f"⚚ <b>Yᴏᴜʀ Aᴄᴄᴏᴜɴᴛ Pʀᴏꜰɪʟᴇ</b> ⚚\n\n✦ <b>Tᴇʟᴇɢʀᴀᴍ ID:</b> <code>{user_id}</code>\n✦ <b>Aᴄᴄᴏᴜɴᴛ Nᴀᴍᴇ:</b> {htmlescape(call.from_user.first_name)}{tag}\n✦ <b>Aᴠᴀɪʟᴀʙʟᴇ Bᴀʟᴀɴᴄᴇ:</b> <code>{points} Pᴏɪɴᴛꜱ</code>\n✦ <b>Aᴄᴄᴏᴜɴᴛ Sᴛᴀᴛᴜꜱ:</b> <code>{user_data.get('status', 'Aᴄᴛɪᴠᴇ')}</code>"
        if is_vip(user_id): text += f"\n✦ <b>VIP Mᴇᴍʙᴇʀꜱʜɪᴘ Expiry:</b> {time.strftime('%Y-%m-%d %H:%M', time.localtime(user_data['vip_until']))}"
        edit_msg(call, text, back_keyboard())
        
    elif d == "menu_refer":
        referral_link = f"https://t.me/{bot.get_me().username}?start={user_id}"
        ref_bonus = safe_int("settings/ref_bonus", 10)
        c1, c2 = safe_int("settings/first_dep_comm", 0), safe_int("settings/reg_dep_comm", 0)
        
        text = f"⟡ <b>Rᴇꜰᴇʀ & Eᴀʀɴ Pᴀꜱꜱɪᴠᴇ Iɴᴄᴏᴍᴇ</b> ⟡\n\nSʜᴀʀᴇ ʏᴏᴜʀ ᴜɴɪǫᴜᴇ ʟɪɴᴋ ᴀɴᴅ ᴇᴀʀɴ <b>{ref_bonus} Pᴏɪɴᴛꜱ</b> ɪɴꜱᴛᴀɴᴛʟʏ ᴘᴇʀ ᴠᴇʀɪꜰɪᴇᴅ ᴜꜱᴇʀ!\n\n"
        if c1 > 0 or c2 > 0: text += f"💸 <b>Aꜰꜰɪʟɪᴀᴛᴇ Dᴇᴘᴏꜱɪᴛ Cᴏᴍᴍɪꜱꜱɪᴏɴꜱ:</b>\n✦ {c1}% ᴄᴏᴍᴍɪꜱꜱɪᴏɴ ᴏɴ ᴛʜᴇɪʀ 1ꜱᴛ Dᴇᴘᴏꜱɪᴛ\n✦ {c2}% ᴄᴏᴍᴍɪꜱꜱɪᴏɴ ᴏɴ Aʟʟ Oᴛʜᴇʀ Dᴇᴘᴏꜱɪᴛꜱ\n\n"
        text += f"⎘ <b>Yᴏᴜʀ Pᴇʀꜱᴏɴᴀʟ Rᴇꜰᴇʀʀᴀʟ Lɪɴᴋ:</b>\n<code>{referral_link}</code>\n\n⊛ <b>Tᴏᴛᴀʟ Rᴇꜰᴇʀʀᴀʟꜱ Mᴀᴅᴇ:</b> <code>{user_data.get('referrals', 0)}</code>"
        kb = {"inline_keyboard": [[{"text": "⍟ Vɪᴇᴡ Tᴏᴘ Lᴇᴀᴅᴇʀʙᴏᴀʀᴅ", "callback_data": "user_leaderboard", "style": "primary"}], [{"text": "↫ Bᴀᴄᴋ", "callback_data": "main_menu", "style": "danger"}]]}
        edit_msg(call, text, json.dumps(kb))

    elif d == "user_leaderboard":
        users = db_get("users") or {}
        size = safe_int("settings/lb_size", 10)
        lb_text = db_get("settings/lb_text") or "❖ <b>Tᴏᴘ Rᴇꜰᴇʀʀᴀʟ Cʜᴀᴍᴘɪᴏɴꜱ Lᴇᴀᴅᴇʀʙᴏᴀʀᴅ</b> ❖"
        sorted_users = sorted(users.items(), key=lambda x: x[1].get('referrals', 0), reverse=True)[:size]
        text = f"{htmlescape(lb_text)}\n\n"
        for i, (uid, udata) in enumerate(sorted_users, 1):
            if udata.get('referrals',0) > 0: text += f"{i}. <b>{htmlescape(udata.get('name','User'))}</b> — <b>{udata.get('referrals',0)}</b> Rᴇꜰᴇʀʀᴀʟꜱ\n"
        kb = {"inline_keyboard": [[{"text": "↫ Bᴀᴄᴋ", "callback_data": "menu_refer", "style": "danger"}]]}
        edit_msg(call, text, json.dumps(kb))

    elif d == "menu_vip":
        if is_vip(user_id): return bot.answer_callback_query(call.id, "✧ Yᴏᴜ ᴀʀᴇ ᴀʟʀᴇᴀᴅʏ ᴀɴ ᴇxᴄʟᴜꜱɪᴠᴇ VIP Mᴇᴍʙᴇʀ!", show_alert=True)
        vprice = safe_int("settings/vip_price", 500)
        vdays = safe_int("settings/vip_days", 30)
        vdisc = safe_int("settings/vip_discount", 10)
        text = f"✧ <b>Exᴄʟᴜꜱɪᴠᴇ VIP Mᴇᴍʙᴇʀꜱʜɪᴘ Pᴀꜱꜱ</b> ✧\n\n✦ <b>Mᴇᴍʙᴇʀꜱʜɪᴘ Pʀɪᴄᴇ:</b> <code>{vprice} Pᴏɪɴᴛꜱ</code>\n✦ <b>Tᴏᴛᴀʟ Vᴀʟɪᴅɪᴛʏ:</b> {vdays} Cᴀʟᴇɴᴅᴀʀ Dᴀʏꜱ\n\n<b>Pʀᴇᴍɪᴜᴍ Bᴇɴᴇꜰɪᴛꜱ Uɴʟᴏᴄᴋᴇᴅ:</b>\n⊛ Gᴇᴛ {vdisc}% Aᴜᴛᴏ-Dɪꜱᴄᴏᴜɴᴛ Oɴ Aʟʟ Sᴇʀᴠɪᴄᴇꜱ Iɴ Tʜᴇ Pᴀɴᴇʟ!\n⊛ Pᴇʀᴍᴀɴᴇɴᴛ Gʟᴏᴡɪɴɢ [✧ VIP] Pʀᴏꜰɪʟᴇ Bᴀᴅɢᴇ!"
        kb = {"inline_keyboard": [[{"text": f"⟡ Pᴜʀᴄʜᴀꜱᴇ VIP Pᴀꜱꜱ ({vprice} Pᴛꜱ)", "callback_data": f"buyvip_{vprice}_{vdays}", "style": "success"}], [{"text": "↫ Bᴀᴄᴋ", "callback_data": "main_menu", "style": "danger"}]]}
        edit_msg(call, text, json.dumps(kb))

    elif d.startswith("buyvip_"):
        parts = d.split("_")
        price, days = int(parts[1]), int(parts[2])
        if points < price: return bot.answer_callback_query(call.id, "❖ Iɴꜱᴜꜰꜰɪᴄɪᴇɴᴛ Bᴀʟᴀɴᴄᴇ Tᴏ Bᴜʏ VIP Pᴀꜱꜱ!", show_alert=True)
        vip_ts = int(time.time()) + (days * 86400)
        db_update(f"users/{user_id}", {"points": points - price, "vip_until": vip_ts})
        edit_msg(call, "✧ <b>Cᴏɴɢʀᴀᴛᴜʟᴀᴛɪᴏɴꜱ! Yᴏᴜ Aʀᴇ Nᴏᴡ A Vᴇʀɪꜰɪᴇᴅ VIP Mᴇᴍʙᴇʀ!</b>\n<i>Aʟʟ ꜱᴇʀᴠɪᴄᴇꜱ ɴᴏᴡ ᴄᴀʀʀʏ ᴀɴ ᴀᴜᴛᴏᴍᴀᴛɪᴄ ᴅɪꜱᴄᴏᴜɴᴛ ꜰᴏʀ ʏᴏᴜ.</i>", back_keyboard())
        
        log_ch = db_get("settings/log_channel")
        if log_ch:
            try: bot.send_message(log_ch, f"✧ <b>Nᴇᴡ VIP Mᴇᴍʙᴇʀꜱʜɪᴘ Pᴜʀᴄʜᴀꜱᴇᴅ!</b>\n✦ Uꜱᴇʀ: <a href='tg://user?id={user_id}'>{htmlescape(call.from_user.first_name)}</a>\n✦ Aᴄǫᴜɪʀᴇᴅ {days} Dᴀʏꜱ VIP Sᴛᴀᴛᴜꜱ", parse_mode="HTML")
            except: pass

    elif d == "menu_milestones":
        if not safe_int("settings/ms_status", 1): return edit_msg(call, "❖ <b>Rᴇꜰᴇʀʀᴀʟ Mɪʟᴇꜱᴛᴏɴᴇ Sʏꜱᴛᴇᴍ Iꜱ Cᴜʀʀᴇɴᴛʟʏ Uɴᴀᴠᴀɪʟᴀʙʟᴇ.</b>", back_keyboard())
        ms_dict = db_get("milestones") or {}
        user_refs = user_data.get('referrals', 0)
        claimed = user_data.get('claimed_ms', {})
        kb = {"inline_keyboard": []}
        
        for ms_id, mdata in sorted(ms_dict.items(), key=lambda x: int(x[1]['reach'])):
            reach, reward = int(mdata['reach']), mdata['reward']
            if ms_id in claimed: kb["inline_keyboard"].append([{"text": f"⊛ {reach} Rᴇꜰꜱ -> {reward} Pᴛꜱ (Aʟʀᴇᴀᴅʏ Cʟᴀɪᴍᴇᴅ)", "callback_data": "ignore", "style": "primary"}])
            elif user_refs >= reach: kb["inline_keyboard"].append([{"text": f"⍟ Cʟᴀɪᴍ {reward} Pᴛꜱ Rᴇᴡᴀʀᴅ ({reach} Rᴇꜰꜱ)", "callback_data": f"claim_ms_{ms_id}", "style": "success"}])
            else: kb["inline_keyboard"].append([{"text": f"❖ Lᴏᴄᴋᴇᴅ: {reach} Rᴇꜰꜱ -> {reward} Pᴛꜱ", "callback_data": "ignore", "style": "danger"}])
                
        kb["inline_keyboard"].append([{"text": "↫ Bᴀᴄᴋ", "callback_data": "main_menu", "style": "danger"}])
        edit_msg(call, f"⍟ <b>Exᴄʟᴜꜱɪᴠᴇ Rᴇꜰᴇʀʀᴀʟ Mɪʟᴇꜱᴛᴏɴᴇꜱ</b>\n\n✦ <b>Yᴏᴜʀ Tᴏᴛᴀʟ Rᴇꜰᴇʀʀᴀʟꜱ:</b> {user_refs}\n<i>Cʟɪᴄᴋ ᴀɴʏ ᴜɴʟᴏᴄᴋᴇᴅ ᴍɪʟᴇꜱᴛᴏɴᴇ ʙᴇʟᴏᴡ ᴛᴏ ɪɴꜱᴛᴀɴᴛʟʏ ᴄʟᴀɪᴍ ʏᴏᴜʀ ʙᴏɴᴜꜱ ᴘᴏɪɴᴛꜱ!</i>", json.dumps(kb))

    elif d.startswith("claim_ms_"):
        ms_id = d.split("_")[2]
        mdata = db_get(f"milestones/{ms_id}")
        if not mdata: return bot.answer_callback_query(call.id, "❖ Mɪʟᴇꜱᴛᴏɴᴇ Nᴏᴛ Fᴏᴜɴᴅ!")
        user_refs = user_data.get('referrals', 0)
        if user_refs >= int(mdata['reach']):
            reward = int(mdata['reward'])
            db_update(f"users/{user_id}", {"points": points + reward})
            db_update(f"users/{user_id}/claimed_ms", {ms_id: True})
            bot.answer_callback_query(call.id, f"⍟ Sᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ Claimed {reward} Bonus Points!", show_alert=True)
            call.data = "menu_milestones"
            handle_query(call)

    elif d == "menu_redeem":
        msg = bot.send_message(call.message.chat.id, "⎚ <b>Rᴇᴅᴇᴇᴍ Gɪꜰᴛ / Pʀᴏᴍᴏ Cᴏᴅᴇ</b>\n\n✦ Pʟᴇᴀꜱᴇ Sᴇɴᴅ Yᴏᴜʀ Vᴀʟɪᴅ Rᴇᴅᴇᴇᴍ Cᴏᴅᴇ Bᴇʟᴏᴡ:\n<i>(Sᴇɴᴅ /cancel ᴛᴏ ꜱᴛᴏᴘ ᴛʜɪꜱ ᴘʀᴏᴄᴇꜱꜱ)</i>", parse_mode="HTML")
        bot.register_next_step_handler(msg, step_user_redeem_code)

    elif d == "menu_purchases":
        purchases = db_get(f"users/{user_id}/purchases")
        text = "ꗃ <b>Yᴏᴜʀ Cᴏᴍᴘʟᴇᴛᴇ Pᴜʀᴄʜᴀꜱᴇ Hɪꜱᴛᴏʀʏ</b> ꗃ\n\n"
        if purchases:
            for p_id, p_name in purchases.items(): text += f"✦ <code>{htmlescape(p_name)}</code>\n"
        else: text += "<i>Yᴏᴜ Hᴀᴠᴇ Nᴏᴛ Pᴜʀᴄʜᴀꜱᴇᴅ Aɴʏ Sᴇʀᴠɪᴄᴇꜱ Fʀᴏᴍ Tʜɪꜱ Pᴀɴᴇʟ Yᴇᴛ.</i>"
        edit_msg(call, text, back_keyboard())

    elif d == "menu_buy_points":
        upi = db_get("settings/upi")
        if not upi: return edit_msg(call, "❖ <b>Pᴀʏᴍᴇɴᴛ Mᴇᴛʜᴏᴅ Hᴀꜱ Nᴏᴛ Bᴇᴇɴ Sᴇᴛ Bʏ Aᴅᴍɪɴ Yᴇᴛ!</b>", back_keyboard())
        rate = safe_float("settings/point_rate", 2.0)
        min_dep, max_dep = safe_int("settings/min_dep", 100), safe_int("settings/max_dep", 10000)
        
        text = f"◈ <b>Bᴜʏ Sᴇʀᴠɪᴄᴇ Pᴏɪɴᴛꜱ</b> ◈\n\n✦ <b>Cᴜʀʀᴇɴᴛ Exᴄʜᴀɴɢᴇ Rᴀᴛᴇ:</b> ₹1 = {rate} Pᴏɪɴᴛꜱ\n✦ <b>Dᴇᴘᴏꜱɪᴛ Lɪᴍɪᴛꜱ:</b> Mɪɴ {min_dep} Pᴛꜱ | Mᴀx {max_dep} Pᴛꜱ\n\n⊛ <b>Sᴇɴᴅ Tʜᴇ Exact Nᴜᴍʙᴇʀ Oꜰ Pᴏɪɴᴛꜱ Yᴏᴜ Wᴀɴᴛ Tᴏ Pᴜʀᴄʜᴀꜱᴇ:</b>\n<i>(Sᴇɴᴅ /cancel ᴛᴏ ꜱᴛᴏᴘ)</i>"
        bot.delete_message(call.message.chat.id, call.message.message_id)
        msg = bot.send_message(call.message.chat.id, text, parse_mode="HTML")
        bot.register_next_step_handler(msg, step_buy_points_amount)

    elif d.startswith("sub_proof_"):
        parts = d.split("_")
        pts_wanted = parts[2]
        msg = bot.send_message(call.message.chat.id, f"✦ Pʟᴇᴀꜱᴇ Sᴇɴᴅ Yᴏᴜʀ <b>Pᴀʏᴍᴇɴᴛ Sᴄʀᴇᴇɴꜱʜᴏᴛ</b> Fᴏʀ {pts_wanted} Pᴏɪɴᴛꜱ (Wɪᴛʜ Exᴀᴄᴛ 12-Dɪɢɪᴛ UTR Rᴇꜰ Nᴜᴍʙᴇʀ Iɴ Cᴀᴘᴛɪᴏɴ):\n<i>(Sᴇɴᴅ /cancel ᴛᴏ ꜱᴛᴏᴘ)</i>", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_payment_proof, pts_wanted)

    # --- UNIFIED USER CATEGORIES (BACKWARD COMPATIBLE) ---
    elif d == "menu_cats":
        cats = normalize_dict(db_get("categories"))
        scats = normalize_dict(db_get("stock_categories"))
        if not cats and not scats: return edit_msg(call, "<i>❖ Nᴏ Sᴇʀᴠɪᴄᴇꜱ Aᴠᴀɪʟᴀʙʟᴇ Iɴ Tʜᴇ Pᴀɴᴇʟ Rɪɢʜᴛ Nᴏᴡ.</i>", back_keyboard())
        kb = {"inline_keyboard": []}
        
        for cid, cdata in cats.items(): kb["inline_keyboard"].append([{"text": f"❖ {cdata['name']}", "callback_data": f"ucat_n_{cid}", "style": "primary"}])
        for cid, cdata in scats.items(): kb["inline_keyboard"].append([{"text": f"❖ {cdata['name']}", "callback_data": f"ucat_s_{cid}", "style": "primary"}])
            
        kb["inline_keyboard"].append([{"text": "↫ Bᴀᴄᴋ", "callback_data": "main_menu", "style": "danger"}])
        edit_msg(call, "❖ <b>Sᴇʟᴇᴄᴛ A Sᴇʀᴠɪᴄᴇ Cᴀᴛᴇɢᴏʀʏ</b> ❖", json.dumps(kb))

    elif d.startswith("ucat_"):
        parts = d.split("_")
        if len(parts) == 2: type_s, cid = "n", parts[1]
        else: type_s, cid = parts[1], parts[2]
        
        path = "categories" if type_s == "n" else "stock_categories"
        cdata = db_get(f"{path}/{cid}")
        if not cdata: return bot.answer_callback_query(call.id, "❖ Cᴀᴛᴇɢᴏʀʏ Nᴏᴛ Fᴏᴜɴᴅ!", show_alert=True)
        services = normalize_dict(cdata.get("services"))
        kb = {"inline_keyboard": []}
        
        for sid, sdata in services.items():
            mark = f"{sdata['price']} Pts"
            if type_s == "s" and len(get_stock_list(sdata)) == 0: mark = "Oᴜᴛ Oꜰ Sᴛᴏᴄᴋ"
            kb["inline_keyboard"].append([{"text": f"✦ {sdata['name']} — {mark}", "callback_data": f"usrv_{type_s}_{cid}_{sid}_none", "style": "primary"}])
            
        kb["inline_keyboard"].append([{"text": "↫ Bᴀᴄᴋ", "callback_data": "menu_cats", "style": "danger"}])
        edit_msg(call, f"❖ <b>{htmlescape(cdata['name'])} Sᴇʀᴠɪᴄᴇꜱ</b>", json.dumps(kb))

    elif d.startswith("usrv_"):
        parts = d.split("_")
        if len(parts) == 3: type_s, cid, sid, promo = "n", parts[1], parts[2], "none"
        else: type_s, cid, sid, promo = parts[1], parts[2], parts[3], parts[4]
        
        path = "categories" if type_s == "n" else "stock_categories"
        sdata = db_get(f"{path}/{cid}/services/{sid}")
        if not sdata: return bot.answer_callback_query(call.id, "❖ Sᴇʀᴠɪᴄᴇ Nᴏᴛ Fᴏᴜɴᴅ!", show_alert=True)
        price = int(sdata['price'])
        
        disc_text = ""
        if is_vip(user_id):
            vp = safe_int("settings/vip_discount", 10)
            price = int(price - (price * vp / 100))
            disc_text += f"\n✧ <b>VIP Mᴇᴍʙᴇʀ Dɪꜱᴄᴏᴜɴᴛ:</b> -{vp}% Applied"
            
        if promo != "none":
            pdata = db_get(f"promos/{promo}")
            if pdata:
                price = int(price - (price * pdata['discount'] / 100))
                disc_text += f"\n⎚ <b>Pʀᴏᴍᴏ Cᴏᴅᴇ Dɪꜱᴄᴏᴜɴᴛ:</b> -{pdata['discount']}% Applied"

        kb = {"inline_keyboard": []}
        if type_s == "s" and len(get_stock_list(sdata)) == 0:
            kb["inline_keyboard"].append([{"text": "⊘ Sᴇʀᴠɪᴄᴇ Cᴜʀʀᴇɴᴛʟʏ Oᴜᴛ Oꜰ Sᴛᴏᴄᴋ", "callback_data": "ignore", "style": "danger"}])
        else:
            kb["inline_keyboard"].append([{"text": f"⟡ Pᴜʀᴄʜᴀꜱᴇ Nᴏᴡ ({price} Pᴛꜱ)", "callback_data": f"buy_{type_s}_{cid}_{sid}_{promo}", "style": "success"}])
            if promo == "none": kb["inline_keyboard"].append([{"text": "⎚ Aᴘᴘʟʏ Pʀᴏᴍᴏ Cᴏᴅᴇ", "callback_data": f"applyprom_{type_s}_{cid}_{sid}", "style": "primary"}])
                
        kb["inline_keyboard"].append([{"text": "↫ Bᴀᴄᴋ", "callback_data": f"ucat_{type_s}_{cid}", "style": "danger"}])
        
        s_name = htmlescape(sdata['name'])
        s_desc = htmlescape(sdata.get('desc','No additional details provided.'))
        edit_msg(call, f"❖ <b>{s_name}</b>\n\n✦ <b>Fɪɴᴀʟ Pʀɪᴄᴇ:</b> {price} Pᴏɪɴᴛꜱ{disc_text}\n⊛ <b>Sᴇʀᴠɪᴄᴇ Dᴇᴛᴀɪʟꜱ:</b>\n{s_desc}", json.dumps(kb))

    elif d.startswith("applyprom_"):
        parts = d.split("_")
        msg = bot.send_message(call.message.chat.id, "⎚ <b>Aᴘᴘʟʏ Pʀᴏᴍᴏ Cᴏᴅᴇ</b>\n✦ Pʟᴇᴀꜱᴇ Sᴇɴᴅ Yᴏᴜʀ Vᴀʟɪᴅ Pʀᴏᴍᴏ Cᴏᴅᴇ Bᴇʟᴏᴡ:\n<i>(Sᴇɴᴅ /cancel ᴛᴏ ꜱᴛᴏᴘ)</i>", parse_mode="HTML")
        bot.register_next_step_handler(msg, step_apply_promo, parts[1], parts[2], parts[3], call.message.message_id)

    elif d.startswith("buy_"):
        parts = d.split("_")
        if len(parts) == 3: type_s, cid, sid, promo = "n", parts[1], parts[2], "none"
        else: type_s, cid, sid, promo = parts[1], parts[2], parts[3], parts[4]
        
        path = "categories" if type_s == "n" else "stock_categories"
        sdata = db_get(f"{path}/{cid}/services/{sid}")
        if not sdata: return bot.answer_callback_query(call.id, "❖ Sᴇʀᴠɪᴄᴇ Nᴏᴛ Fᴏᴜɴᴅ!", show_alert=True)
        
        price = int(sdata['price'])
        if is_vip(user_id):
            vp = safe_int("settings/vip_discount", 10)
            price = int(price - (price * vp / 100))
            
        if promo != "none":
            pdata = db_get(f"promos/{promo}")
            if pdata:
                price = int(price - (price * pdata['discount'] / 100))
                db_update(f"promos/{promo}", {"used": pdata.get('used',0) + 1})

        if points < price: return bot.answer_callback_query(call.id, "❖ Iɴꜱᴜꜰꜰɪᴄɪᴇɴᴛ Pᴏɪɴᴛꜱ Bᴀʟᴀɴᴄᴇ Tᴏ Cᴏᴍᴘʟᴇᴛᴇ Pᴜʀᴄʜᴀꜱᴇ!", show_alert=True)
        
        if type_s == "s":
            stock_list = get_stock_list(sdata)
            if len(stock_list) == 0: return bot.answer_callback_query(call.id, "⊘ Oᴜᴛ Oꜰ Sᴛᴏᴄᴋ!", show_alert=True)
            item = stock_list.pop(0)
            db_update(f"{path}/{cid}/services/{sid}", {"stock": stock_list, "sold": sdata.get('sold',0) + 1})
            if item['type'] == 'text': bot.send_message(user_id, f"❖ <b>Yᴏᴜʀ Sᴛᴏᴄᴋ Dᴇʟɪᴠᴇʀʏ:</b>\n\n<code>{htmlescape(item['data'])}</code>", parse_mode="HTML")
            else: bot.copy_message(chat_id=user_id, from_chat_id=MASTER_ADMIN, message_id=int(item['data']))
        else:
            delivery = sdata.get('delivery')
            db_update(f"{path}/{cid}/services/{sid}", {"sales": sdata.get('sales',0) + 1})
            if delivery:
                try: bot.copy_message(chat_id=user_id, from_chat_id=delivery['chat_id'], message_id=delivery['message_id'])
                except: bot.send_message(user_id, "❖ <i>Eʀʀᴏʀ Dᴇʟɪᴠᴇʀɪɴɢ Pʀᴏᴅᴜᴄᴛ! Pʟᴇᴀꜱᴇ Cᴏɴᴛᴀᴄᴛ Aᴅᴍɪɴ.</i>", parse_mode="HTML")
            else:
                bot.send_message(user_id, f"❖ <b>Yᴏᴜʀ Oʀᴅᴇʀ Fᴏʀ {htmlescape(sdata['name'])} Iꜱ Pʟᴀᴄᴇᴅ!</b>\n<i>(Pʟᴇᴀꜱᴇ ᴡᴀɪᴛ ᴡʜɪʟᴇ ᴀᴅᴍɪɴ ᴘʀᴏᴄᴇꜱꜱᴇꜱ ɪᴛ)</i>", parse_mode="HTML")

        db_update(f"users/{user_id}", {"points": points - price})
        db_update(f"users/{user_id}/purchases", {str(int(time.time())): sdata['name']})
        edit_msg(call, f"❖ <b>Pᴜʀᴄʜᴀꜱᴇ Sᴜᴄᴄᴇꜱꜰᴜʟ!</b>\n✦ <b>Sᴇʀᴠɪᴄᴇ Nᴀᴍᴇ:</b> {htmlescape(sdata['name'])}\n✦ <b>Deducted Balance:</b> {price} Pᴏɪɴᴛꜱ", back_keyboard())
        
        # FIX 1: 64-BYTE LIMIT ON VOUCH BUTTONS
        s_short = str(sdata['name'])[:25]
        vkb = {"inline_keyboard": [
            [{"text": "⍟ ⭐1", "callback_data": f"vouch_1_{s_short}", "style": "danger"}, 
             {"text": "⍟ ⭐2", "callback_data": f"vouch_2_{s_short}", "style": "danger"}, 
             {"text": "⍟ ⭐3", "callback_data": f"vouch_3_{s_short}", "style": "primary"}, 
             {"text": "⍟ ⭐4", "callback_data": f"vouch_4_{s_short}", "style": "success"}, 
             {"text": "⍟ ⭐5", "callback_data": f"vouch_5_{s_short}", "style": "success"}]
        ]}
        bot.send_message(user_id, "⊛ <b>Pʟᴇᴀꜱᴇ Rᴀᴛᴇ Yᴏᴜʀ Pᴜʀᴄʜᴀꜱᴇ Exᴘᴇʀɪᴇɴᴄᴇ Bᴇʟᴏᴡ:</b>", reply_markup=json.dumps(vkb), parse_mode="HTML")

        log_channel = db_get("settings/log_channel")
        if log_channel:
            try: bot.send_message(log_channel, f"❖ <b>Nᴇᴡ Sᴇʀᴠɪᴄᴇ Pᴜʀᴄʜᴀꜱᴇ Mᴀᴅᴇ!</b>\n\n✦ <b>Bᴜʏᴇʀ Uꜱᴇʀ:</b> <a href='tg://user?id={user_id}'>{htmlescape(call.from_user.first_name)}</a>\n✦ <b>Bᴏᴜɢʜᴛ Sᴇʀᴠɪᴄᴇ:</b> {htmlescape(sdata['name'])}\n✦ <b>Pʀɪᴄᴇ Pᴀɪᴅ:</b> <code>{price} Pᴏɪɴᴛꜱ</code>", parse_mode="HTML")
            except: pass

    elif d.startswith("vouch_"):
        parts = d.split("_", 2)
        rate, s_name = parts[1], parts[2]
        edit_msg(call, "❖ <b>Tʜᴀɴᴋ Yᴏᴜ Fᴏʀ Yᴏᴜʀ Vᴀʟᴜᴀʙʟᴇ Fᴇᴇᴅʙᴀᴄᴋ!</b>")
        if int(rate) >= 4:
            log_ch = db_get("settings/log_channel")
            if log_ch:
                try: bot.send_message(log_ch, f"⍟ <b>Nᴇᴡ Verified 5-Sᴛᴀʀ Vᴏᴜᴄʜ!</b> ⍟\n\n✦ <b>Uꜱᴇʀ Nᴀᴍᴇ:</b> {htmlescape(call.from_user.first_name)}\n✦ <b>Sᴇʀᴠɪᴄᴇ:</b> {htmlescape(s_name)}\n⊛ <b>Rᴀᴛɪɴɢ Sᴄᴏʀᴇ:</b> {rate}/5 Stars\n\n❖ <i>Aᴜᴛᴏ-Aᴘᴘʀᴏᴠᴇᴅ & Vᴇʀɪꜰɪᴇᴅ Bʏ @{BOT_USERNAME}</i>", parse_mode="HTML")
                except: pass

    # --- FULL ADMIN MODULE ---
    elif d == "admin_cats":
        cats = normalize_dict(db_get("categories"))
        kb = {"inline_keyboard": []}
        for cid, cdata in cats.items(): kb["inline_keyboard"].append([{"text": f"❖ {cdata['name']}", "callback_data": f"acat_{cid}", "style": "primary"}])
        kb["inline_keyboard"].append([{"text": "➕ Aᴅᴅ Nᴇᴡ Cᴀᴛᴇɢᴏʀʏ", "callback_data": "add_cat", "style": "success"}])
        kb["inline_keyboard"].append([{"text": "↫ Bᴀᴄᴋ", "callback_data": "back_to_admin", "style": "danger"}])
        edit_msg(call, "❖ <b>Nᴏʀᴍᴀʟ Sᴇʀᴠɪᴄᴇ Mᴀɴᴀɢᴇᴍᴇɴᴛ Pᴀɴᴇʟ</b>", json.dumps(kb))

    elif d == "add_cat":
        msg = bot.send_message(call.message.chat.id, "➕ <b>Aᴅᴅ Nᴇᴡ Cᴀᴛᴇɢᴏʀʏ</b>\n✦ Sᴇɴᴅ Tʜᴇ Nᴇᴡ Cᴀᴛᴇɢᴏʀʏ Nᴀᴍᴇ Bᴇʟᴏᴡ:\n<i>(Sᴇɴᴅ /cancel ᴛᴏ ꜱᴛᴏᴘ)</i>", parse_mode="HTML")
        bot.register_next_step_handler(msg, step_add_cat)

    elif d.startswith("acat_"):
        cid = d.split("_")[1]
        cdata = db_get(f"categories/{cid}")
        if not cdata: return bot.answer_callback_query(call.id, "❖ Cᴀᴛᴇɢᴏʀʏ Nᴏᴛ Fᴏᴜɴᴅ", show_alert=True)
        kb = {"inline_keyboard": [[{"text": f"❌ Dᴇʟᴇᴛᴇ Eɴᴛɪʀᴇ '{cdata['name']}'", "callback_data": f"delcat_{cid}", "style": "danger"}]]}
        services = normalize_dict(cdata.get("services"))
        for sid, sdata in services.items(): kb["inline_keyboard"].append([{"text": f"✦ {sdata['name']} ({sdata['price']} Pts)", "callback_data": f"asrv_{cid}_{sid}", "style": "primary"}])
        kb["inline_keyboard"].append([{"text": "➕ Aᴅᴅ Nᴇᴡ Sᴇʀᴠɪᴄᴇ", "callback_data": f"addsrv_{cid}", "style": "success"}])
        kb["inline_keyboard"].append([{"text": "↫ Bᴀᴄᴋ", "callback_data": "admin_cats", "style": "danger"}])
        edit_msg(call, f"📁 <b>Cᴀᴛᴇɢᴏʀʏ: {htmlescape(cdata['name'])}</b>", json.dumps(kb))

    elif d.startswith("delcat_"):
        db_delete(f"categories/{d.split('_')[1]}")
        bot.answer_callback_query(call.id, "✅ Cᴀᴛᴇɢᴏʀʏ Sᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ Dᴇʟᴇᴛᴇᴅ!", show_alert=True)
        call.data = "admin_cats"
        handle_query(call)

    elif d.startswith("addsrv_"):
        msg = bot.send_message(call.message.chat.id, "➕ <b>Aᴅᴅ Nᴇᴡ Sᴇʀᴠɪᴄᴇ Nᴀᴍᴇ</b>\n✦ Sᴇɴᴅ Sᴇʀᴠɪᴄᴇ Nᴀᴍᴇ:\n<i>(Sᴇɴᴅ /cancel ᴛᴏ ꜱᴛᴏᴘ)</i>", parse_mode="HTML")
        bot.register_next_step_handler(msg, step_add_srv_name, d.split("_")[1])

    elif d.startswith("asrv_"):
        parts = d.split("_")
        cid, sid = parts[1], parts[2]
        sdata = db_get(f"categories/{cid}/services/{sid}")
        if not sdata: return bot.answer_callback_query(call.id, "❖ Sᴇʀᴠɪᴄᴇ Nᴏᴛ Fᴏᴜɴᴅ!", show_alert=True)
        kb = {"inline_keyboard": [
            [{"text": "❌ Dᴇʟᴇᴛᴇ Sᴇʀᴠɪᴄᴇ", "callback_data": f"delsrv_{cid}_{sid}", "style": "danger"}, {"text": "📝 Eᴅɪᴛ Pʀɪᴄᴇ", "callback_data": f"edprc_{cid}_{sid}", "style": "success"}],
            [{"text": "📝 Eᴅɪᴛ Nᴀᴍᴇ", "callback_data": f"ednm_{cid}_{sid}", "style": "success"}, {"text": "📝 Eᴅɪᴛ Dᴇꜱᴄʀɪᴘᴛɪᴏɴ", "callback_data": f"edtxt_{cid}_{sid}", "style": "success"}],
            [{"text": "📝 Eᴅɪᴛ Dᴇʟɪᴠᴇʀʏ Mᴇꜱꜱᴀɢᴇ", "callback_data": f"eddel_{cid}_{sid}", "style": "primary"}],
            [{"text": "↫ Bᴀᴄᴋ", "callback_data": f"acat_{cid}", "style": "danger"}]
        ]}
        s_name = htmlescape(sdata['name'])
        s_desc = htmlescape(sdata.get('desc','None'))
        edit_msg(call, f"⚙️ <b>Mᴀɴᴀɢᴇ Sᴇʀᴠɪᴄᴇ: {s_name}</b>\n✦ Pʀɪᴄᴇ: {sdata['price']} Pts\n✦ Sᴀʟᴇꜱ: {sdata.get('sales',0)}\n✦ Dᴇꜱᴄ: {s_desc}", json.dumps(kb))

    elif d.startswith("delsrv_"):
        parts = d.split("_")
        db_delete(f"categories/{parts[1]}/services/{parts[2]}")
        bot.answer_callback_query(call.id, "✅ Sᴇʀᴠɪᴄᴇ Dᴇʟᴇᴛᴇᴅ!", show_alert=True)
        call.data = f"acat_{parts[1]}"
        handle_query(call)

    elif d.startswith("edprc_") or d.startswith("ednm_") or d.startswith("edtxt_"):
        parts = d.split("_")
        action, cid, sid = parts[0], parts[1], parts[2]
        field = "price" if action=="edprc" else "name" if action=="ednm" else "desc"
        msg = bot.send_message(call.message.chat.id, f"📝 Sᴇɴᴅ Nᴇᴡ {field.upper()} ꜰᴏʀ Tʜɪꜱ Sᴇʀᴠɪᴄᴇ:\n<i>(Sᴇɴᴅ /cancel ᴛᴏ ꜱᴛᴏᴘ)</i>", parse_mode="HTML")
        bot.register_next_step_handler(msg, step_edit_srv, cid, sid, field)
        
    elif d.startswith("eddel_"):
        parts = d.split("_")
        cid, sid = parts[1], parts[2]
        msg = bot.send_message(call.message.chat.id, f"📝 Sᴇɴᴅ Nᴇᴡ Dᴇʟɪᴠᴇʀᴀʙʟᴇ Mᴇꜱꜱᴀɢᴇ/Mᴇᴅɪᴀ ꜰᴏʀ Tʜɪꜱ Sᴇʀᴠɪᴄᴇ:\n<i>(Sᴇɴᴅ /cancel ᴛᴏ ꜱᴛᴏᴘ)</i>", parse_mode="HTML")
        bot.register_next_step_handler(msg, step_edit_srv_delivery, cid, sid)

    elif d == "admin_promos":
        promos = db_get("promos") or {}
        kb = {"inline_keyboard": []}
        for code, data in promos.items(): kb["inline_keyboard"].append([{"text": f"🎟️ {code} ({data.get('discount')}%)", "callback_data": f"vprom_{code}", "style": "primary"}])
        kb["inline_keyboard"].append([{"text": "➕ Cʀᴇᴀᴛᴇ Pʀᴏᴍᴏ Cᴏᴅᴇ", "callback_data": "add_prom", "style": "success"}])
        kb["inline_keyboard"].append([{"text": "↫ Bᴀᴄᴋ", "callback_data": "back_to_admin", "style": "danger"}])
        edit_msg(call, "🎟️ <b>Mᴀɴᴀɢᴇ Pʀᴏᴍᴏ Cᴏᴅᴇꜱ</b>", json.dumps(kb))

    elif d == "add_prom":
        msg = bot.send_message(call.message.chat.id, "➕ Sᴇɴᴅ Nᴇᴡ Pʀᴏᴍᴏ Cᴏᴅᴇ Nᴀᴍᴇ (e.g. DIWALI50):")
        bot.register_next_step_handler(msg, step_prom_name)

    elif d.startswith("vprom_"):
        code = d.split("_")[1]
        data = db_get(f"promos/{code}")
        if not data: return bot.answer_callback_query(call.id, "⚠️ Pʀᴏᴍᴏ Nᴏᴛ Fᴏᴜɴᴅ!")
        rem = data['limit'] - data.get('used', 0)
        exp_time = time.strftime('%Y-%m-%d %H:%M', time.localtime(data['expiry'])) if data['expiry'] > 0 else "Nᴇᴠᴇʀ"
        kb = {"inline_keyboard": [[{"text": "❌ Dᴇʟᴇᴛᴇ Pʀᴏᴍᴏ", "callback_data": f"delprom_{code}", "style": "danger"}], [{"text": "↫ Bᴀᴄᴋ", "callback_data": "admin_promos", "style": "primary"}]]}
        edit_msg(call, f"🎟️ <b>Pʀᴏᴍᴏ Cᴏᴅᴇ:</b> <code>{code}</code>\n\n✦ <b>Dɪꜱᴄᴏᴜɴᴛ:</b> {data['discount']}%\n✦ <b>Aᴘᴘʟɪᴇᴅ Bʏ:</b> {data.get('used',0)} Uꜱᴇʀꜱ\n✦ <b>Rᴇᴍᴀɪɴɪɴɢ Uꜱᴇꜱ:</b> {rem}\n✦ <b>Exᴘɪʀᴇꜱ Oɴ:</b> {exp_time}", json.dumps(kb))

    elif d.startswith("delprom_"):
        db_delete(f"promos/{d.split('_')[1]}")
        bot.answer_callback_query(call.id, "✅ Pʀᴏᴍᴏ Cᴏᴅᴇ Sᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ Dᴇʟᴇᴛᴇᴅ!")
        call.data = "admin_promos"
        handle_query(call)

    elif d == "admin_stock_cats":
        scats = normalize_dict(db_get("stock_categories"))
        kb = {"inline_keyboard": []}
        for cid, cdata in scats.items(): kb["inline_keyboard"].append([{"text": f"📁 {cdata['name']}", "callback_data": f"stcat_{cid}", "style": "primary"}])
        kb["inline_keyboard"].append([{"text": "➕ Aᴅᴅ Sᴛᴏᴄᴋ Cᴀᴛᴇɢᴏʀʏ", "callback_data": "add_stcat", "style": "success"}])
        kb["inline_keyboard"].append([{"text": "↫ Bᴀᴄᴋ", "callback_data": "back_to_admin", "style": "danger"}])
        edit_msg(call, "📦 <b>Sᴛᴏᴄᴋ Sᴇʀᴠɪᴄᴇꜱ Mᴀɴᴀɢᴇᴍᴇɴᴛ</b>", json.dumps(kb))

    elif d == "add_stcat":
        msg = bot.send_message(call.message.chat.id, "➕ <b>Aᴅᴅ Sᴛᴏᴄᴋ Cᴀᴛᴇɢᴏʀʏ</b>\n✦ Sᴇɴᴅ Nᴀᴍᴇ:", parse_mode="HTML")
        bot.register_next_step_handler(msg, step_add_stcat)

    elif d.startswith("stcat_"):
        cid = d.split("_")[1]
        cdata = db_get(f"stock_categories/{cid}")
        if not cdata: return bot.answer_callback_query(call.id, "❖ Cᴀᴛᴇɢᴏʀʏ Nᴏᴛ Fᴏᴜɴᴅ", show_alert=True)
        kb = {"inline_keyboard": [[{"text": f"❌ Dᴇʟᴇᴛᴇ '{cdata['name']}'", "callback_data": f"delstcat_{cid}", "style": "danger"}]]}
        services = normalize_dict(cdata.get("services"))
        for sid, sdata in services.items(): kb["inline_keyboard"].append([{"text": f"✦ {sdata['name']} (Lᴇꜰᴛ: {len(get_stock_list(sdata))} | Sᴏʟᴅ: {sdata.get('sold', 0)})", "callback_data": f"ast_srv_{cid}_{sid}", "style": "primary"}])
        kb["inline_keyboard"].append([{"text": "➕ Aᴅᴅ Sᴛᴏᴄᴋ Sᴇʀᴠɪᴄᴇ", "callback_data": f"adds_srv_{cid}", "style": "success"}])
        kb["inline_keyboard"].append([{"text": "↫ Bᴀᴄᴋ", "callback_data": "admin_stock_cats", "style": "danger"}])
        edit_msg(call, f"📁 <b>Sᴛᴏᴄᴋ Cᴀᴛᴇɢᴏʀʏ: {htmlescape(cdata['name'])}</b>", json.dumps(kb))

    elif d.startswith("delstcat_"):
        db_delete(f"stock_categories/{d.split('_')[1]}")
        bot.answer_callback_query(call.id, "✅ Sᴛᴏᴄᴋ Cᴀᴛᴇɢᴏʀʏ Dᴇʟᴇᴛᴇᴅ!", show_alert=True)
        call.data = "admin_stock_cats"
        handle_query(call)

    elif d.startswith("adds_srv_"):
        msg = bot.send_message(call.message.chat.id, "➕ Sᴇɴᴅ Sᴛᴏᴄᴋ Sᴇʀᴠɪᴄᴇ Nᴀᴍᴇ:\n<i>(Sᴇɴᴅ /cancel ᴛᴏ ꜱᴛᴏᴘ)</i>", parse_mode="HTML")
        bot.register_next_step_handler(msg, step_adds_name, d.split("_")[2])

    elif d.startswith("ast_srv_"):
        parts = d.split("_")
        cid, sid = parts[2], parts[3]
        sdata = db_get(f"stock_categories/{cid}/services/{sid}")
        if not sdata: return bot.answer_callback_query(call.id, "❖ Sᴇʀᴠɪᴄᴇ Nᴏᴛ Fᴏᴜɴᴅ!", show_alert=True)
        kb = {"inline_keyboard": [
            [{"text": "➕ Aᴅᴅ Mᴏʀᴇ Sᴛᴏᴄᴋ", "callback_data": f"add_stock_{cid}_{sid}", "style": "success"}],
            [{"text": "❌ Dᴇʟᴇᴛᴇ", "callback_data": f"dels_srv_{cid}_{sid}", "style": "danger"}, {"text": "📝 Eᴅɪᴛ Pʀɪᴄᴇ", "callback_data": f"eds_prc_{cid}_{sid}", "style": "success"}],
            [{"text": "📝 Eᴅɪᴛ Nᴀᴍᴇ", "callback_data": f"eds_nm_{cid}_{sid}", "style": "success"}, {"text": "📝 Eᴅɪᴛ Dᴇꜱᴄ", "callback_data": f"eds_txt_{cid}_{sid}", "style": "success"}],
            [{"text": "↫ Bᴀᴄᴋ", "callback_data": f"stcat_{cid}", "style": "danger"}]
        ]}
        s_name = htmlescape(sdata['name'])
        s_desc = htmlescape(sdata.get('desc','None'))
        edit_msg(call, f"⚙️ <b>Mᴀɴᴀɢᴇ Sᴛᴏᴄᴋ: {s_name}</b>\n✦ Pʀɪᴄᴇ: {sdata['price']} Pts\n✦ Sᴛᴏᴄᴋ Lᴇꜰᴛ: <b>{len(get_stock_list(sdata))}</b>\n✦ Tᴏᴛᴀʟ Sᴏʟᴅ: <b>{sdata.get('sold',0)}</b>\n✦ Dᴇꜱᴄ: {s_desc}", json.dumps(kb))

    elif d.startswith("dels_srv_"):
        parts = d.split("_")
        db_delete(f"stock_categories/{parts[2]}/services/{parts[3]}")
        bot.answer_callback_query(call.id, "✅ Sᴛᴏᴄᴋ Sᴇʀᴠɪᴄᴇ Dᴇʟᴇᴛᴇᴅ!", show_alert=True)
        call.data = f"stcat_{parts[2]}"
        handle_query(call)

    elif d.startswith("eds_prc_") or d.startswith("eds_nm_") or d.startswith("eds_txt_"):
        parts = d.split("_")
        action = parts[0] + "_" + parts[1]
        cid, sid = parts[2], parts[3]
        field = "price" if "prc" in action else "name" if "nm" in action else "desc"
        msg = bot.send_message(call.message.chat.id, f"📝 Sᴇɴᴅ Nᴇᴡ {field.upper()}:\n<i>(Sᴇɴᴅ /cancel ᴛᴏ ꜱᴛᴏᴘ)</i>", parse_mode="HTML")
        bot.register_next_step_handler(msg, step_edit_stsrv, cid, sid, field)

    elif d.startswith("add_stock_"):
        parts = d.split("_")
        cid, sid = parts[2], parts[3]
        kb = {"inline_keyboard": [[{"text": "✅ Dᴏɴᴇ (Sᴛᴏᴘ Sᴛᴏᴄᴋ Lᴏᴏᴘ)", "callback_data": f"ast_srv_{cid}_{sid}", "style": "danger"}]]}
        msg = bot.send_message(call.message.chat.id, "📦 <b>Sᴇɴᴅ Tʜᴇ Fɪʀꜱᴛ Sᴛᴏᴄᴋ Iᴛᴇᴍ (Tᴇxᴛ ᴏʀ Fɪʟᴇ):</b>\n<i>I ᴡɪʟʟ ᴋᴇᴇᴘ ᴀꜱᴋɪɴɢ ꜰᴏʀ ᴍᴏʀᴇ ᴜɴᴛɪʟ ʏᴏᴜ ᴄʟɪᴄᴋ Dᴏɴᴇ!</i>", reply_markup=json.dumps(kb), parse_mode="HTML")
        bot.register_next_step_handler(msg, step_stock_loop, cid, sid, msg.message_id)

    elif d == "admin_vip_set":
        msg = bot.send_message(call.message.chat.id, "💎 <b>VIP Mᴇᴍʙᴇʀꜱʜɪᴘ Sᴇᴛᴛɪɴɢꜱ</b>\n✦ Sᴇɴᴅ VIP Pʀɪᴄᴇ Iɴ Pᴏɪɴᴛꜱ:\n<i>(Sᴇɴᴅ /cancel ᴛᴏ ꜱᴛᴏᴘ)</i>", parse_mode="HTML")
        bot.register_next_step_handler(msg, step_vip_price)

    elif d == "admin_comm":
        msg = bot.send_message(call.message.chat.id, "💸 <b>Mᴜʟᴛɪ-Tɪᴇʀ Rᴇꜰᴇʀʀᴀʟ Cᴏᴍᴍɪꜱꜱɪᴏɴ %</b>\n✦ Sᴇɴᴅ Cᴏᴍᴍɪꜱꜱɪᴏɴ % Fᴏʀ <b>1ꜱᴛ Rᴇꜰᴇʀʀᴀʟ'ꜱ 1ꜱᴛ Dᴇᴘᴏꜱɪᴛ</b>:\n<i>(Sᴇɴᴅ 0 ᴛᴏ ᴅɪꜱᴀʙʟᴇ)</i>", parse_mode="HTML")
        bot.register_next_step_handler(msg, step_comm_first)

    elif d == "admin_milestones":
        ms_dict = db_get("milestones") or {}
        kb = {"inline_keyboard": []}
        for ms_id, mdata in sorted(ms_dict.items(), key=lambda x: int(x[1]['reach'])): kb["inline_keyboard"].append([{"text": f"🎯 {mdata['reach']} Rᴇꜰꜱ -> {mdata['reward']} Pᴛꜱ", "callback_data": f"view_ms_{ms_id}", "style": "primary"}])
        kb["inline_keyboard"].append([{"text": "➕ Aᴅᴅ Mɪʟᴇꜱᴛᴏɴᴇ", "callback_data": "add_ms", "style": "success"}])
        st = safe_int("settings/ms_status", 1)
        kb["inline_keyboard"].append([{"text": "🟢 Mɪʟᴇꜱᴛᴏɴᴇꜱ: ON" if st else "🔴 Mɪʟᴇꜱᴛᴏɴᴇꜱ: OFF", "callback_data": "tog_ms", "style": "primary"}])
        kb["inline_keyboard"].append([{"text": "↫ Bᴀᴄᴋ", "callback_data": "back_to_admin", "style": "danger"}])
        edit_msg(call, "🎁 <b>Mᴀɴᴀɢᴇ Rᴇꜰᴇʀ Mɪʟᴇꜱᴛᴏɴᴇꜱ</b>", json.dumps(kb))

    elif d == "tog_ms":
        db_update("settings", {"ms_status": 0 if safe_int("settings/ms_status", 1) else 1})
        call.data = "admin_milestones"
        handle_query(call)

    elif d == "add_ms":
        msg = bot.send_message(call.message.chat.id, "➕ Sᴇɴᴅ Tᴀʀɢᴇᴛ Rᴇꜰᴇʀꜱ Cᴏᴜɴᴛ (e.g. 10):")
        bot.register_next_step_handler(msg, step_ms_reach)

    elif d.startswith("view_ms_"):
        ms_id = d.split("_")[2]
        mdata = db_get(f"milestones/{ms_id}")
        if not mdata: return bot.answer_callback_query(call.id, "⚠️ Mɪʟᴇꜱᴛᴏɴᴇ Nᴏᴛ Fᴏᴜɴᴅ!")
        kb = {"inline_keyboard": [[{"text": "❌ Dᴇʟᴇᴛᴇ", "callback_data": f"del_ms_{ms_id}", "style": "danger"}], [{"text": "↫ Bᴀᴄᴋ", "callback_data": "admin_milestones", "style": "primary"}]]}
        edit_msg(call, f"🎯 <b>Mɪʟᴇꜱᴛᴏɴᴇ:</b> {mdata['reach']} Rᴇꜰꜱ\n✦ <b>Rᴇᴡᴀʀᴅ:</b> {mdata['reward']} Pᴏɪɴᴛꜱ", json.dumps(kb))

    elif d.startswith("del_ms_"):
        db_delete(f"milestones/{d.split('_')[2]}")
        bot.answer_callback_query(call.id, "✅ Mɪʟᴇꜱᴛᴏɴᴇ Dᴇʟᴇᴛᴇᴅ!")
        call.data = "admin_milestones"
        handle_query(call)
        
    elif d == "admin_analytics":
        bot.answer_callback_query(call.id, "⏳ Fᴇᴛᴄʜɪɴɢ Aɴᴀʟʏᴛɪᴄꜱ...")
        users = db_get("users") or {}
        cats = db_get("categories") or {}
        scats = db_get("stock_categories") or {}
        tot_points = sum(u.get("points", 0) for u in users.values())
        tot_sales = sum(s.get("sales", 0) for c in cats.values() for s in c.get("services", {}).values())
        tot_sales += sum(s.get("sold", 0) for c in scats.values() for s in c.get("services", {}).values())
        text = f"📊 <b>Aᴅᴠᴀɴᴄᴇᴅ Sʏꜱᴛᴇᴍ Aɴᴀʟʏᴛɪᴄꜱ</b>\n\n👥 Tᴏᴛᴀʟ Rᴇɢɪꜱᴛᴇʀᴇᴅ Uꜱᴇʀꜱ: {len(users)}\n💰 Tᴏᴛᴀʟ Pᴏɪɴᴛꜱ Iɴ Mᴀʀᴋᴇᴛ: {tot_points}\n🛍️ Tᴏᴛᴀʟ Sᴇʀᴠɪᴄᴇꜱ Sᴏʟᴅ: {tot_sales}"
        kb = {"inline_keyboard": [[{"text": "↫ Bᴀᴄᴋ", "callback_data": "back_to_admin", "style": "danger"}]]}
        edit_msg(call, text, json.dumps(kb))

    elif d == "admin_leaderboard":
        kb = {"inline_keyboard": [
            [{"text": "🔢 Sᴇᴛ Lᴇᴀᴅᴇʀʙᴏᴀʀᴅ Sɪᴢᴇ", "callback_data": "set_lb_size", "style": "primary"}],
            [{"text": "📝 Sᴇᴛ Lᴇᴀᴅᴇʀʙᴏᴀʀᴅ Tᴇxᴛ", "callback_data": "set_lb_text", "style": "primary"}],
            [{"text": "🏆 Vɪᴇᴡ Lᴇᴀᴅᴇʀʙᴏᴀʀᴅ (Aᴅᴍɪɴ)", "callback_data": "view_admin_lb", "style": "success"}],
            [{"text": "↫ Bᴀᴄᴋ", "callback_data": "back_to_admin", "style": "danger"}]
        ]}
        edit_msg(call, "🏆 <b>Lᴇᴀᴅᴇʀʙᴏᴀʀᴅ Cᴏɴꜰɪɢᴜʀᴀᴛɪᴏɴꜱ</b>", json.dumps(kb))

    elif d == "set_lb_size":
        msg = bot.send_message(call.message.chat.id, "🔢 <b>Sᴇᴛ Lᴇᴀᴅᴇʀʙᴏᴀʀᴅ Sɪᴢᴇ</b>\n✦ Sᴇɴᴅ Nᴜᴍʙᴇʀ (e.g. 5 ᴏʀ 10):", parse_mode="HTML")
        bot.register_next_step_handler(msg, step_lb_size)
    elif d == "set_lb_text":
        msg = bot.send_message(call.message.chat.id, "📝 <b>Sᴇᴛ Lᴇᴀᴅᴇʀʙᴏᴀʀᴅ Hᴇᴀᴅᴇʀ Tᴇxᴛ</b>\n✦ Sᴇɴᴅ Tᴇxᴛ:", parse_mode="HTML")
        bot.register_next_step_handler(msg, step_lb_text)
    elif d == "view_admin_lb":
        users = db_get("users") or {}
        size = safe_int("settings/lb_size", 10)
        sorted_users = sorted(users.items(), key=lambda x: x[1].get('referrals', 0), reverse=True)[:size]
        text = f"🏆 <b>Aᴅᴍɪɴ Vɪᴇᴡ: Tᴏᴘ Rᴇꜰᴇʀʀᴀʟꜱ (Tᴏᴘ {size})</b>\n\n"
        for i, (uid, udata) in enumerate(sorted_users, 1):
            if udata.get('referrals',0) > 0: text += f"{i}. <b>{htmlescape(udata.get('name','User'))}</b> (<code>{uid}</code>) — <b>{udata.get('referrals',0)}</b> Refs\n"
        kb = {"inline_keyboard": [[{"text": "↫ Bᴀᴄᴋ", "callback_data": "admin_leaderboard", "style": "danger"}]]}
        edit_msg(call, text, json.dumps(kb))

    elif d == "admin_balance":
        msg = bot.send_message(call.message.chat.id, "⟡ <b>Mᴀɴᴀɢᴇ Uꜱᴇʀ Bᴀʟᴀɴᴄᴇ</b>\n✦ Sᴇɴᴅ Tᴀʀɢᴇᴛ Uꜱᴇʀ ID:\n<i>(Sᴇɴᴅ /cancel ᴛᴏ ꜱᴛᴏᴘ)</i>", parse_mode="HTML")
        bot.register_next_step_handler(msg, step_balance_id)
        
    elif d == "admin_upi":
        msg = bot.send_message(call.message.chat.id, "💳 <b>Pᴀʏᴍᴇɴᴛ UPI Sᴇᴛᴜᴘ</b>\n✦ Sᴇɴᴅ Nᴇᴡ UPI ID:\n<i>(Sᴇɴᴅ /cancel ᴛᴏ ꜱᴛᴏᴘ)</i>", parse_mode="HTML")
        bot.register_next_step_handler(msg, step_set_upi)
        
    elif d == "admin_points":
        msg = bot.send_message(call.message.chat.id, "◈ <b>Pᴏɪɴᴛꜱ Exᴄʜᴀɴɢᴇ Pʀɪᴄɪɴɢ</b>\n✦ Sᴇɴᴅ Oɴʟʏ A Nᴜᴍʙᴇʀ (e.g. 2):\n<i>(Sᴇɴᴅ /cancel ᴛᴏ ꜱᴛᴏᴘ)</i>", parse_mode="HTML")
        bot.register_next_step_handler(msg, step_set_points)
        
    elif d == "admin_log_channel":
        msg = bot.send_message(call.message.chat.id, "⍟ <b>Pᴜʀᴄʜᴀꜱᴇ & Vᴏᴜᴄʜ Lᴏɢ Cʜᴀɴɴᴇʟ</b>\n✦ Sᴇɴᴅ Cʜᴀɴɴᴇʟ ID (ᴏʀ 'off'):\n<i>(Sᴇɴᴅ /cancel ᴛᴏ ꜱᴛᴏᴘ)</i>", parse_mode="HTML")
        bot.register_next_step_handler(msg, step_log_channel)
        
    elif d == "admin_staff":
        msg = bot.send_message(call.message.chat.id, "⚚ <b>Mᴀɴᴀɢᴇ Sᴛᴀꜰꜰ Aᴅᴍɪɴꜱ</b>\n✦ Sᴇɴᴅ Tᴇʟᴇɢʀᴀᴍ User ID:\n<i>(Sᴇɴᴅ /cancel ᴛᴏ ꜱᴛᴏᴘ)</i>", parse_mode="HTML")
        bot.register_next_step_handler(msg, step_staff)
        
    elif d == "admin_ban":
        msg = bot.send_message(call.message.chat.id, "⛔ <b>Bᴀɴ / Uɴʙᴀɴ Uꜱᴇʀ</b>\n✦ Sᴇɴᴅ Uꜱᴇʀ ID Tᴏ Tᴏɢɢʟᴇ Bᴀɴ Sᴛᴀᴛᴜꜱ:\n<i>(Sᴇɴᴅ /cancel ᴛᴏ ꜱᴛᴏᴘ)</i>", parse_mode="HTML")
        bot.register_next_step_handler(msg, step_ban_user)

    elif d == "admin_dep_limits":
        msg = bot.send_message(call.message.chat.id, "⚖️ <b>Sᴇᴛ Dᴇᴘᴏꜱɪᴛ Lɪᴍɪᴛꜱ</b>\n✦ Sᴇɴᴅ <b>Mɪɴɪᴍᴜᴍ</b> Dᴇᴘᴏꜱɪᴛ Iɴ Pᴏɪɴᴛꜱ:\n<i>(Sᴇɴᴅ /cancel ᴛᴏ ꜱᴛᴏᴘ)</i>", parse_mode="HTML")
        bot.register_next_step_handler(msg, step_min_dep)

    elif d == "admin_ref_amt":
        msg = bot.send_message(call.message.chat.id, "🎁 <b>Sᴇᴛ Rᴇꜰᴇʀʀᴀʟ Rᴇᴡᴀʀᴅ</b>\n✦ Sᴇɴᴅ Nᴜᴍʙᴇʀ Oꜰ Pᴏɪɴᴛꜱ Pᴇʀ Rᴇꜰᴇʀ:\n<i>(Sᴇɴᴅ /cancel ᴛᴏ ꜱᴛᴏᴘ)</i>", parse_mode="HTML")
        bot.register_next_step_handler(msg, step_ref_amt)

    # --- ADMIN: BROADCAST SYSTEM (FIX 2: URL DATABASE STORAGE) ---
    elif d == "admin_broadcast":
        msg = bot.send_message(call.message.chat.id, "📢 <b>Sᴍᴀʀᴛ Bʀᴏᴀᴅᴄᴀꜱᴛ Eɴɢɪɴᴇ</b>\n✦ Sᴇɴᴅ Tʜᴇ Mᴇꜱꜱᴀɢᴇ (Tᴇxᴛ/Pʜᴏᴛᴏ/Vɪᴅᴇᴏ):\n<i>(Sᴇɴᴅ /cancel ᴛᴏ ꜱᴛᴏᴘ)</i>", parse_mode="HTML")
        bot.register_next_step_handler(msg, step_broadcast_msg)

    elif d.startswith("brd_sendnow_"):
        msg_id = d.split("_")[2]
        bot.edit_message_text("⏳ <b>Bʀᴏᴀᴅᴄᴀꜱᴛ Iꜱ Bᴇɪɴɢ Sᴇɴᴛ...</b>", call.message.chat.id, call.message.message_id, parse_mode="HTML")
        users = db_get("users") or {}
        count = 0
        for uid in users.keys():
            try:
                bot.copy_message(chat_id=uid, from_chat_id=call.message.chat.id, message_id=int(msg_id))
                count += 1
                time.sleep(0.05)
            except: pass
        bot.send_message(call.message.chat.id, f"✅ <b>Bʀᴏᴀᴅᴄᴀꜱᴛ Sᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ Sᴇɴᴛ Tᴏ {count} Uꜱᴇʀꜱ!</b>", parse_mode="HTML")

    elif d.startswith("brd_addbtn_"):
        msg_id = d.split("_")[2]
        msg = bot.send_message(call.message.chat.id, "✦ Sᴇɴᴅ Tʜᴇ Dɪꜱᴘʟᴀʏ Nᴀᴍᴇ Fᴏʀ Tʜɪꜱ Bᴜᴛᴛᴏɴ:\n<i>(Sᴇɴᴅ /cancel ᴛᴏ ꜱᴛᴏᴘ)</i>", parse_mode="HTML")
        bot.register_next_step_handler(msg, step_broadcast_url, msg_id)

    elif d.startswith("brdcolor_"):
        parts = d.split("||")
        color = parts[0].split("_")[1]
        msg_id = parts[1]
        bot.edit_message_text("⏳ <b>Bʀᴏᴀᴅᴄᴀꜱᴛ Iꜱ Bᴇɪɴɢ Sᴇɴᴛ...</b>", call.message.chat.id, call.message.message_id, parse_mode="HTML")
        
        temp_brd = db_get("settings/temp_brd") or {}
        btn_name = temp_brd.get("btn", "Link")
        url = temp_brd.get("url", "https://t.me")
        
        users = db_get("users") or {}
        count = 0
        kb = json.dumps({"inline_keyboard": [[{"text": btn_name, "url": url, "style": color}]]})
        for uid in users.keys():
            try:
                bot.copy_message(chat_id=uid, from_chat_id=call.message.chat.id, message_id=int(msg_id), reply_markup=kb)
                count += 1
                time.sleep(0.05)
            except: pass
        bot.send_message(call.message.chat.id, f"✅ <b>Bʀᴏᴀᴅᴄᴀꜱᴛ Sᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ Sᴇɴᴛ Tᴏ {count} Uꜱᴇʀꜱ!</b>", parse_mode="HTML")

    # --- ADMIN DEPOSIT ---
    elif d.startswith("dep_approve_"):
        parts = d.split("_")
        u_id = parts[2]
        pts_amt = parts[3] if len(parts) > 3 else "0"
        kb = {"inline_keyboard": [
            [{"text": f"✅ Cᴏɴꜰɪʀᴍ & Sᴇɴᴅ {pts_amt} Pᴛꜱ", "callback_data": f"dep_confirm_{u_id}_{pts_amt}", "style": "success"}],
            [{"text": "↫ Cᴀɴᴄᴇʟ", "callback_data": "dep_cancel", "style": "danger"}]
        ]}
        bot.send_message(call.message.chat.id, f"⚠️ Cᴏɴꜰɪʀᴍ ᴀᴅᴅɪɴɢ <b>{pts_amt} Pᴏɪɴᴛꜱ</b> ᴛᴏ ᴜꜱᴇʀ <code>{u_id}</code>?", reply_markup=json.dumps(kb), parse_mode="HTML")

    elif d.startswith("dep_reject_"):
        u_id = d.split("_")[2]
        bot.edit_message_caption("❌ <b>Dᴇᴘᴏꜱɪᴛ Pᴀʏᴍᴇɴᴛ Rᴇᴊᴇᴄᴛᴇᴅ!</b>", call.message.chat.id, call.message.message_id, parse_mode="HTML")
        try: bot.send_message(u_id, "❖ <b>Pᴀʏᴍᴇɴᴛ Rᴇᴊᴇᴄᴛᴇᴅ!</b>\n✦ Yᴏᴜʀ ᴘᴀʏᴍᴇɴᴛ ꜱᴄʀᴇᴇɴꜱʜᴏᴛ ᴡᴀꜱ ʀᴇᴊᴇᴄᴛᴇᴅ ʙʏ ᴀᴅᴍɪɴ.", parse_mode="HTML")
        except: pass
    
    elif d.startswith("dep_confirm_"):
        parts = d.split("_")
        u_id, amt = parts[2], int(parts[3])
        user = db_get(f"users/{u_id}")
        if user:
            new_pts = user.get("points", 0) + amt
            db_update(f"users/{u_id}", {"points": new_pts})
            bot.edit_message_text(f"✅ <b>Successfully Credited {amt} Points To User {u_id}!</b>", call.message.chat.id, call.message.message_id, parse_mode="HTML")
            try: bot.send_message(u_id, f"✧ <b>Dᴇᴘᴏꜱɪᴛ Aᴘᴘʀᴏᴠᴇᴅ & Cʀᴇᴅɪᴛᴇᴅ!</b>\n✦ Aᴅᴍɪɴ ᴀᴅᴅᴇᴅ <b>{amt} Pᴏɪɴᴛꜱ</b>.\n⊛ Nᴇᴡ Aᴄᴄᴏᴜɴᴛ Bᴀʟᴀɴᴄᴇ: <code>{new_pts}</code>", parse_mode="HTML")
            except: pass
            
            if user.get("referred_by"):
                ref_id = user["referred_by"]
                ref_user = db_get(f"users/{ref_id}")
                if ref_user:
                    deps = user.get("deposits_count", 0) + 1
                    db_update(f"users/{u_id}", {"deposits_count": deps})
                    comm_pct = safe_int("settings/first_dep_comm", 0) if deps == 1 else safe_int("settings/reg_dep_comm", 0)
                    if comm_pct > 0:
                        comm = int((amt * comm_pct) / 100)
                        if comm > 0:
                            db_update(f"users/{ref_id}", {"points": ref_user.get("points", 0) + comm})
                            try: bot.send_message(ref_id, f"💸 <b>Aꜰꜰɪʟɪᴀᴛᴇ Cᴏᴍᴍɪꜱꜱɪᴏɴ Bᴏɴᴜꜱ!</b>\n✦ Yᴏᴜʀ ʀᴇꜰᴇʀʀᴀʟ ᴍᴀᴅᴇ ᴀ ᴅᴇᴘᴏꜱɪᴛ.\n✦ Yᴏᴜ ᴇᴀʀɴᴇᴅ ᴄᴏᴍᴍɪꜱꜱɪᴏɴ: <b>{comm} Pᴏɪɴᴛꜱ</b>", parse_mode="HTML")
                            except: pass

    elif d == "dep_cancel":
        bot.delete_message(call.message.chat.id, call.message.message_id)

# ==========================================
#          STEP HANDLERS 
# ==========================================

def step_apply_promo(m, type_s, cid, sid, panel_msg_id):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❖ Cᴀɴᴄᴇʟʟᴇᴅ")
    code = m.text.strip().upper()
    data = db_get(f"promos/{code}")
    if not data: return bot.send_message(m.chat.id, "❖ Iɴᴠᴀʟɪᴅ Pʀᴏᴍᴏ Cᴏᴅᴇ!")
    if data['limit'] <= data.get('used', 0): return bot.send_message(m.chat.id, "❖ Tʜɪꜱ Pʀᴏᴍᴏ Cᴏᴅᴇ Uꜱᴀɢᴇ Lɪᴍɪᴛ Hᴀꜱ Bᴇᴇɴ Rᴇᴀᴄʜᴇᴅ!")
    if data['expiry'] > 0 and time.time() > data['expiry']: return bot.send_message(m.chat.id, "❖ Tʜɪꜱ Pʀᴏᴍᴏ Cᴏᴅᴇ Hᴀꜱ Exᴘɪʀᴇᴅ!")
    
    class FakeCall:
        id = "1"
        data = f"usrv_{type_s}_{cid}_{sid}_{code}"
        class Msg:
            chat = m.chat
            message_id = panel_msg_id
            content_type = 'text'
        message = Msg()
        from_user = m.from_user
    bot.send_message(m.chat.id, f"⎚ <b>Pʀᴏᴍᴏ Cᴏᴅᴇ '{code}' Sᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ Aᴘᴘʟɪᴇᴅ!</b>", parse_mode="HTML")
    handle_query(FakeCall())

def process_payment_proof(m, pts):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❖ Cᴀɴᴄᴇʟʟᴇᴅ")
    if m.content_type != 'photo': return bot.send_message(m.chat.id, "❖ Pʟᴇᴀꜱᴇ Sᴇɴᴅ A Vᴀʟɪᴅ <b>Pʜᴏᴛᴏɢʀᴀᴘʜ Sᴄʀᴇᴇɴꜱʜᴏᴛ</b>!", parse_mode="HTML")
    
    utr_matches = re.findall(r'\b\d{12}\b', m.caption or "")
    if not utr_matches:
        bot.delete_message(m.chat.id, m.message_id)
        return bot.send_message(m.chat.id, "❖ <b>Iɴᴠᴀʟɪᴅ Pᴀʏᴍᴇɴᴛ Pʀᴏᴏꜰ!</b>\nPʟᴇᴀꜱᴇ ꜱᴇɴᴅ ᴛʜᴇ ꜱᴄʀᴇᴇɴꜱʜᴏᴛ ᴡɪᴛʜ ᴀ ᴠᴀʟɪᴅ 12-Dɪɢɪᴛ UTR Rᴇꜰ Nᴜᴍʙᴇʀ ɪɴ ᴛʜᴇ ᴄᴀᴘᴛɪᴏɴ.", parse_mode="HTML")
    
    rate = safe_float("settings/point_rate", 2.0)
    user_id = m.from_user.id
    kb = {"inline_keyboard": [[{"text": "✅ Aᴘᴘʀᴏᴠᴇ & Cʀᴇᴅɪᴛ Pᴛꜱ", "callback_data": f"dep_approve_{user_id}_{pts}", "style": "success"}], [{"text": "❌ Rᴇᴊᴇᴄᴛ Pᴀʏᴍᴇɴᴛ", "callback_data": f"dep_reject_{user_id}", "style": "danger"}]]}
    bot.send_photo(MASTER_ADMIN, m.photo[-1].file_id, caption=f"💳 <b>Nᴇᴡ Pᴀʏᴍᴇɴᴛ Dᴇᴘᴏꜱɪᴛ RᴇQᴜᴇꜱᴛ</b>\n\n✦ <b>Uꜱᴇʀ Nᴀᴍᴇ:</b> {m.from_user.first_name}\n✦ <b>Uꜱᴇʀ ID:</b> <code>{user_id}</code>\n✦ <b>Pᴏɪɴᴛꜱ RᴇQᴜᴇꜱᴛᴇᴅ:</b> {pts} Pᴛꜱ\n✦ <b>Exᴘᴇᴄᴛᴇᴅ Pᴀʏᴍᴇɴᴛ:</b> ₹{round(int(pts)/rate, 2)}\n✦ <b>UTR Rᴇꜰ ID:</b> <code>{utr_matches[0]}</code>", reply_markup=json.dumps(kb), parse_mode="HTML")
    bot.send_message(m.chat.id, "❖ <b>Pᴀʏᴍᴇɴᴛ Sᴄʀᴇᴇɴꜱʜᴏᴛ Sᴜʙᴍɪᴛᴛᴇᴅ!</b>\n<i>Aᴅᴍɪɴ ᴡɪʟʟ ᴠᴇʀɪꜰʏ ʏᴏᴜʀ UTR ᴀɴᴅ ᴄʀᴇᴅɪᴛ ᴘᴏɪɴᴛꜱ ꜱʜᴏʀᴛʟʏ.</i>", parse_mode="HTML")

def step_stock_loop(m, cid, sid, menu_msg_id):
    if m.text and m.text == '/cancel': 
        bot.send_message(m.chat.id, "✅ Sᴛᴏᴄᴋ Aᴅᴅɪɴɢ Sᴇꜱꜱɪᴏɴ Sᴛᴏᴘᴘᴇᴅ.")
        return
    sdata = db_get(f"stock_categories/{cid}/services/{sid}")
    if not sdata: return bot.send_message(m.chat.id, "⚠️ Eʀʀᴏʀ: Sᴇʀᴠɪᴄᴇ Nᴏᴛ Fᴏᴜɴᴅ Iɴ Dᴀᴛᴀʙᴀꜱᴇ!")
    stock_list = get_stock_list(sdata)
    stock_list.append({"type": "text", "data": m.text} if m.content_type == 'text' else {"type": "file", "data": str(m.message_id)})
    db_update(f"stock_categories/{cid}/services/{sid}", {"stock": stock_list})
    
    kb = {"inline_keyboard": [[{"text": "✅ Dᴏɴᴇ (Sᴛᴏᴘ Sᴛᴏᴄᴋ Lᴏᴏᴘ)", "callback_data": f"ast_srv_{cid}_{sid}", "style": "danger"}]]}
    msg = bot.send_message(m.chat.id, f"📦 <b>Sᴛᴏᴄᴋ Iᴛᴇᴍ #{len(stock_list)} Sᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ Aᴅᴅᴇᴅ!</b>\nSᴇɴᴅ ɴᴇxᴛ ɪᴛᴇᴍ ᴏʀ ᴄʟɪᴄᴋ Dᴏɴᴇ ʙᴇʟᴏᴡ:", reply_markup=json.dumps(kb), parse_mode="HTML")
    bot.register_next_step_handler(msg, step_stock_loop, cid, sid, msg.message_id)

def step_welcome(m):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❌ Cᴀɴᴄᴇʟʟᴇᴅ")
    if m.text and m.text.lower() == 'off':
        db_delete("settings/welcome")
        return bot.send_message(m.chat.id, "✅ Wᴇʟᴄᴏᴍᴇ Mᴇɴᴜ Rᴇꜱᴇᴛ Tᴏ Dᴇꜰᴀᴜʟᴛ.")
    
    text_val = m.caption if m.content_type == 'photo' else m.text
    data = {}
    if text_val: data["text"] = text_val
    if m.content_type == 'photo': data["photo"] = m.photo[-1].file_id
    
    db_update("settings/welcome", data)
    bot.send_message(m.chat.id, "✅ Wᴇʟᴄᴏᴍᴇ Mᴇɴᴜ Sᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ Uᴘᴅᴀᴛᴇᴅ!")

def step_buy_points_amount(m):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❌ Cᴀɴᴄᴇʟʟᴇᴅ", reply_markup=permanent_main_menu())
    try: pts = int(m.text)
    except: 
        msg = bot.send_message(m.chat.id, "⚠️ Pʟᴇᴀꜱᴇ ᴇɴᴛᴇʀ ᴀ ᴠᴀʟɪᴅ ɴᴜᴍʙᴇʀ ɪɴ ᴅɪɢɪᴛꜱ (e.g. 100).", parse_mode="HTML")
        bot.register_next_step_handler(msg, step_buy_points_amount)
        return
    
    rate = safe_float("settings/point_rate", 2.0)
    min_dep = safe_int("settings/min_dep", 100)
    max_dep = safe_int("settings/max_dep", 10000)
    
    if pts < min_dep: return bot.send_message(m.chat.id, f"⚠️ Mɪɴɪᴍᴜᴍ ᴅᴇᴘᴏꜱɪᴛ ɪꜱ <b>{min_dep} Pᴏɪɴᴛꜱ</b>!", parse_mode="HTML")
    if pts > max_dep: return bot.send_message(m.chat.id, f"⚠️ Mᴀxɪᴍᴜᴍ ᴅᴇᴘᴏꜱɪᴛ ɪꜱ <b>{max_dep} Pᴏɪɴᴛꜱ</b>!", parse_mode="HTML")
        
    price_inr = round(pts / rate, 2)
    upi = db_get("settings/upi")
    
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=upi://pay?pa={upi}&pn=Admin&am={price_inr}"
    kb = {"inline_keyboard": [
        [{"text": "📤 Sᴜʙᴍɪᴛ Pᴀʏᴍᴇɴᴛ Pʀᴏᴏꜰ", "callback_data": f"sub_proof_{pts}", "style": "success"}],
        [{"text": "↫ Cᴀɴᴄᴇʟ", "callback_data": "main_menu", "style": "danger"}]
    ]}
    text = f"◈ <b>Pᴀʏᴍᴇɴᴛ Dᴇᴛᴀɪʟꜱ & QR Cᴏᴅᴇ</b> ◈\n\n✦ <b>Pᴏɪɴᴛꜱ RᴇQᴜᴇꜱᴛᴇᴅ:</b> <code>{pts}</code>\n✦ <b>Aᴍᴏᴜɴᴛ Tᴏ Pᴀʏ:</b> <code>₹{price_inr}</code>\n\n💳 <b>Aᴅᴍɪɴ UPI ID:</b> <code>{upi}</code>\n\n<i>Sᴄᴀɴ Tʜᴇ QR Cᴏᴅᴇ, Pᴀʏ Exᴀᴄᴛʟʏ ₹{price_inr}, Aɴᴅ Sᴜʙᴍɪᴛ Yᴏᴜʀ Sᴄʀᴇᴇɴꜱʜᴏᴛ!</i>"
    bot.send_photo(m.chat.id, qr_url, caption=text, reply_markup=json.dumps(kb), parse_mode="HTML")

def step_add_force_ch(m):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❌ <b>Cᴀɴᴄᴇʟʟᴇᴅ</b>", parse_mode="HTML")
    chat_id = m.forward_from_chat.id if m.forward_from_chat else m.text.strip()
    try:
        chat = bot.get_chat(chat_id)
        link = chat.invite_link or bot.export_chat_invite_link(chat.id)
        db_update(f"settings/force_channels/{chat.id}", {"name": chat.title or "📢 Jᴏɪɴ Cʜᴀɴɴᴇʟ", "url": link})
        bot.send_message(m.chat.id, f"✅ <b>Fᴏʀᴄᴇ Sᴜʙꜱᴄʀɪᴘᴛɪᴏɴ Cʜᴀɴɴᴇʟ Aᴅᴅᴇᴅ!</b>", parse_mode="HTML")
    except Exception as e:
        bot.send_message(m.chat.id, f"⚠️ Eʀʀᴏʀ: {e}")

def step_add_nf_name(m):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❌ Cᴀɴᴄᴇʟʟᴇᴅ")
    msg = bot.send_message(m.chat.id, "✦ Nᴏᴡ Sᴇɴᴅ Tʜᴇ Exᴛᴇʀɴᴀʟ URL Lɪɴᴋ:\n<i>(Sᴇɴᴅ /cancel ᴛᴏ ꜱᴛᴏᴘ)</i>", parse_mode="HTML")
    bot.register_next_step_handler(msg, step_add_nf_link, m.text)
    
def step_add_nf_link(m, name):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❌ Cᴀɴᴄᴇʟʟᴇᴅ")
    db_update(f"settings/non_force_channels/{str(int(time.time()))}", {"name": name, "url": m.text})
    bot.send_message(m.chat.id, "✅ <b>Nᴏɴ-Fᴏʀᴄᴇ Lɪɴᴋ Sᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ Aᴅᴅᴇᴅ!</b>", parse_mode="HTML")

def step_balance_id(m):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❌ Cᴀɴᴄᴇʟʟᴇᴅ")
    user = db_get(f"users/{m.text.strip()}")
    if not user: return bot.send_message(m.chat.id, "⚠️ Tᴀʀɢᴇᴛ Uꜱᴇʀ Nᴏᴛ Fᴏᴜɴᴅ.")
    bot.register_next_step_handler(bot.send_message(m.chat.id, f"⟡ <b>{user['name']}</b> (Current: {user.get('points',0)} Pts)\n✦ Sᴇɴᴅ Aᴍᴏᴜɴᴛ Tᴏ Add (+ve) Or Deduct (-ve):", parse_mode="HTML"), step_balance_amount, m.text.strip(), user.get('points',0))

def step_balance_amount(m, uid, curr):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❌ Cᴀɴᴄᴇʟʟᴇᴅ")
    try: amt = int(m.text)
    except: return bot.send_message(m.chat.id, "⚠️ Iɴᴠᴀʟɪᴅ Nᴜᴍʙᴇʀ!")
    db_update(f"users/{uid}", {"points": curr + amt})
    bot.send_message(m.chat.id, "✅ Uꜱᴇʀ Bᴀʟᴀɴᴄᴇ Sᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ Mᴏᴅɪꜰɪᴇᴅ!")

def step_set_upi(m):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❌ Cᴀɴᴄᴇʟʟᴇᴅ")
    db_update("settings", {"upi": m.text})
    bot.send_message(m.chat.id, "✅ Aᴅᴍɪɴ UPI ID Sᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ Uᴘᴅᴀᴛᴇᴅ!")

def step_set_points(m):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❌ Cᴀɴᴄᴇʟʟᴇᴅ")
    try: r = float(m.text)
    except: return bot.send_message(m.chat.id, "⚠️ Iɴᴠᴀʟɪᴅ Nᴜᴍʙᴇʀ!")
    db_update("settings", {"point_rate": r})
    bot.send_message(m.chat.id, "✅ Pᴏɪɴᴛꜱ Exᴄʜᴀɴɢᴇ Pʀɪᴄɪɴɢ Uᴘᴅᴀᴛᴇᴅ!")

def step_min_dep(m):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❌ Cᴀɴᴄᴇʟʟᴇᴅ")
    try: mind = int(m.text)
    except: return bot.send_message(m.chat.id, "⚠️ Iɴᴠᴀʟɪᴅ Nᴜᴍʙᴇʀ!")
    db_update("settings", {"min_dep": mind})
    bot.register_next_step_handler(bot.send_message(m.chat.id, "✦ Nᴏᴡ Sᴇɴᴅ <b>Mᴀxɪᴍᴜᴍ</b> Dᴇᴘᴏꜱɪᴛ Lɪᴍɪᴛ:", parse_mode="HTML"), step_max_dep)

def step_max_dep(m):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❌ Cᴀɴᴄᴇʟʟᴇᴅ")
    try: maxd = int(m.text)
    except: return bot.send_message(m.chat.id, "⚠️ Iɴᴠᴀʟɪᴅ Nᴜᴍʙᴇʀ!")
    db_update("settings", {"max_dep": maxd})
    bot.send_message(m.chat.id, "✅ Dᴇᴘᴏꜱɪᴛ Lɪᴍɪᴛꜱ Sᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ Uᴘᴅᴀᴛᴇᴅ!")

def step_ref_amt(m):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❌ Cᴀɴᴄᴇʟʟᴇᴅ")
    try: ref_b = int(m.text)
    except: return bot.send_message(m.chat.id, "⚠️ Iɴᴠᴀʟɪᴅ Nᴜᴍʙᴇʀ!")
    db_update("settings", {"ref_bonus": ref_b})
    bot.send_message(m.chat.id, "✅ Rᴇꜰᴇʀʀᴀʟ Bᴏɴᴜꜱ Sᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ Uᴘᴅᴀᴛᴇᴅ!")

def step_log_channel(m):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❌ Cᴀɴᴄᴇʟʟᴇᴅ")
    db_update("settings", {"log_channel": "" if m.text.lower() == 'off' else m.text})
    bot.send_message(m.chat.id, "✅ Pᴜʀᴄʜᴀꜱᴇ Lᴏɢ Cʜᴀɴɴᴇʟ Uᴘᴅᴀᴛᴇᴅ!")

def step_staff(m):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❌ Cᴀɴᴄᴇʟʟᴇᴅ")
    try: new_admin = int(m.text)
    except: return bot.send_message(m.chat.id, "⚠️ Iɴᴠᴀʟɪᴅ Nᴜᴍʙᴇʀ!")
    admins = db_get("settings/admins") or []
    if new_admin in admins: admins.remove(new_admin)
    else: admins.append(new_admin)
    db_update("settings", {"admins": admins})
    bot.send_message(m.chat.id, "✅ Sᴛᴀꜰꜰ Aᴅᴍɪɴꜱ Lɪꜱᴛ Sᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ Uᴘᴅᴀᴛᴇᴅ!")

def step_ban_user(m):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❌ Cᴀɴᴄᴇʟʟᴇᴅ")
    uid = m.text.strip()
    u = db_get(f"users/{uid}")
    if not u: return bot.send_message(m.chat.id, "⚠️ Tᴀʀɢᴇᴛ Uꜱᴇʀ Nᴏᴛ Fᴏᴜɴᴅ")
    new_stat = "Aᴄᴛɪᴠᴇ" if u.get("status") == "Banned" else "Banned"
    db_update(f"users/{uid}", {"status": new_stat})
    bot.send_message(m.chat.id, f"✅ Uꜱᴇʀ {uid} Aᴄᴄᴏᴜɴᴛ Sᴛᴀᴛᴜꜱ: <b>{new_stat}</b>", parse_mode="HTML")

def step_lb_size(m):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❌ Cᴀɴᴄᴇʟʟᴇᴅ")
    try: lb = int(m.text)
    except: return bot.send_message(m.chat.id, "⚠️ Iɴᴠᴀʟɪᴅ Nᴜᴍʙᴇʀ!")
    db_update("settings", {"lb_size": lb})
    bot.send_message(m.chat.id, "✅ Lᴇᴀᴅᴇʀʙᴏᴀʀᴅ Sɪᴢᴇ Uᴘᴅᴀᴛᴇᴅ!")

def step_lb_text(m):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❌ Cᴀɴᴄᴇʟʟᴇᴅ")
    db_update("settings", {"lb_text": m.text})
    bot.send_message(m.chat.id, "✅ Lᴇᴀᴅᴇʀʙᴏᴀʀᴅ Hᴇᴀᴅᴇʀ Tᴇxᴛ Uᴘᴅᴀᴛᴇᴅ!")

# --- FIX 2: BROADCAST SYSTEM URL STORAGE ---
def step_broadcast_msg(m):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❌ Cᴀɴᴄᴇʟʟᴇᴅ")
    kb = {"inline_keyboard": [
        [{"text": "➕ Yᴇꜱ, Aᴅᴅ Bᴜᴛᴛᴏɴ", "callback_data": f"brd_addbtn_{m.message_id}", "style": "success"}], 
        [{"text": "⏭️ Nᴏ, Sᴇɴᴅ Nᴏᴡ", "callback_data": f"brd_sendnow_{m.message_id}", "style": "primary"}]
    ]}
    bot.send_message(m.chat.id, "✦ <b>Dᴏ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴀᴅᴅ ᴀɴ Iɴʟɪɴᴇ Bᴜᴛᴛᴏɴ ᴛᴏ ᴛʜɪꜱ ʙʀᴏᴀᴅᴄᴀꜱᴛ?</b>", reply_markup=json.dumps(kb), parse_mode="HTML")

def step_broadcast_url(m, msg_id):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❌ Cᴀɴᴄᴇʟʟᴇᴅ")
    db_update("settings/temp_brd", {"btn": m.text})
    msg = bot.send_message(m.chat.id, "✦ Sᴇɴᴅ Tʜᴇ Exᴛᴇʀɴᴀʟ URL Lɪɴᴋ ꜰᴏʀ Tʜɪꜱ Bᴜᴛᴛᴏɴ:\n<i>(Sᴇɴᴅ /cancel ᴛᴏ ꜱᴛᴏᴘ)</i>", parse_mode="HTML")
    bot.register_next_step_handler(msg, step_broadcast_color, msg_id)

def step_broadcast_color(m, msg_id):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❌ Cᴀɴᴄᴇʟʟᴇᴅ")
    db_update("settings/temp_brd", {"url": m.text})
    kb = {"inline_keyboard": [
        [{"text": "🔵 Pʀɪᴍᴀʀʏ (Bʟᴜᴇ)", "callback_data": f"brdcolor_primary||{msg_id}", "style": "primary"}],
        [{"text": "🟢 Sᴜᴄᴄᴇꜱꜱ (Gʀᴇᴇɴ)", "callback_data": f"brdcolor_success||{msg_id}", "style": "success"}],
        [{"text": "🔴 Dᴀɴɢᴇʀ (Rᴇᴅ)", "callback_data": f"brdcolor_danger||{msg_id}", "style": "danger"}]
    ]}
    bot.send_message(m.chat.id, "✦ <b>Sᴇʟᴇᴄᴛ A Cᴏʟᴏʀ Pʀᴇꜱᴇᴛ ꜰᴏʀ Tʜᴇ Bᴜᴛᴛᴏɴ:</b>", reply_markup=json.dumps(kb), parse_mode="HTML")

def step_add_cat(m):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❌ Cᴀɴᴄᴇʟʟᴇᴅ")
    db_update(f"categories/{str(int(time.time()))}", {"name": m.text})
    bot.send_message(m.chat.id, "✅ Nᴇᴡ Sᴇʀᴠɪᴄᴇ Cᴀᴛᴇɢᴏʀʏ Sᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ Aᴅᴅᴇᴅ!")

def step_add_srv_name(m, cid):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❌ Cᴀɴᴄᴇʟʟᴇᴅ")
    bot.register_next_step_handler(bot.send_message(m.chat.id, "✦ Sᴇɴᴅ Sᴇʀᴠɪᴄᴇ Pʀɪᴄᴇ (Iɴ Pᴏɪɴᴛꜱ):"), step_srv_price, cid, m.text)

def step_srv_price(m, cid, name):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❌ Cᴀɴᴄᴇʟʟᴇᴅ")
    try: p = int(m.text)
    except: return bot.send_message(m.chat.id, "⚠️ Iɴᴠᴀʟɪᴅ Pʀɪᴄᴇ!")
    bot.register_next_step_handler(bot.send_message(m.chat.id, "✦ Sᴇɴᴅ Sᴇʀᴠɪᴄᴇ Dᴇꜱᴄʀɪᴘᴛɪᴏɴ Tᴇxᴛ:"), step_srv_desc, cid, name, p)

def step_srv_desc(m, cid, name, price):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❌ Cᴀɴᴄᴇʟʟᴇᴅ")
    bot.register_next_step_handler(bot.send_message(m.chat.id, "✦ Nᴏᴡ Sᴇɴᴅ Tʜᴇ <b>Dᴇʟɪᴠᴇʀᴀʙʟᴇ Mᴇꜱꜱᴀɢᴇ</b> (Tᴇxᴛ/Mᴇᴅɪᴀ ᴛᴏ ʙᴇ ꜱᴇɴᴛ ᴀꜰᴛᴇʀ ᴘᴜʀᴄʜᴀꜱᴇ):", parse_mode="HTML"), step_srv_delivery, cid, name, price, m.text)

def step_srv_delivery(m, cid, name, price, desc):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❌ Cᴀɴᴄᴇʟʟᴇᴅ")
    db_update(f"categories/{cid}/services/{str(int(time.time()))}", {"name": name, "price": price, "desc": desc, "sales": 0, "delivery": {"chat_id": m.chat.id, "message_id": m.message_id}})
    bot.send_message(m.chat.id, f"✅ Nᴏʀᴍᴀʟ Sᴇʀᴠɪᴄᴇ Sᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ Cʀᴇᴀᴛᴇᴅ & Dᴇᴘʟᴏʏᴇᴅ!")

def step_edit_srv(m, cid, sid, field):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❌ Cᴀɴᴄᴇʟʟᴇᴅ")
    if field == "price":
        try: val = int(m.text)
        except: return bot.send_message(m.chat.id, "⚠️ Iɴᴠᴀʟɪᴅ Pʀɪᴄᴇ!")
    else:
        val = m.text
    db_update(f"categories/{cid}/services/{sid}", {field: val})
    bot.send_message(m.chat.id, f"✅ Sᴇʀᴠɪᴄᴇ Pᴀʀᴀᴍᴇᴛᴇʀ Sᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ Uᴘᴅᴀᴛᴇᴅ!")

def step_edit_srv_delivery(m, cid, sid):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❌ Cᴀɴᴄᴇʟʟᴇᴅ")
    db_update(f"categories/{cid}/services/{sid}/delivery", {"chat_id": m.chat.id, "message_id": m.message_id})
    bot.send_message(m.chat.id, f"✅ Dᴇʟɪᴠᴇʀʏ Mᴇꜱꜱᴀɢᴇ Sᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ Uᴘᴅᴀᴛᴇᴅ!")

def step_prom_name(m):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❌ Cᴀɴᴄᴇʟʟᴇᴅ")
    bot.register_next_step_handler(bot.send_message(m.chat.id, "✦ Sᴇɴᴅ Dɪꜱᴄᴏᴜɴᴛ Pᴇʀᴄᴇɴᴛᴀɢᴇ % (e.g. 50):"), step_prom_disc, m.text.upper())

def step_prom_disc(m, name):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❌ Cᴀɴᴄᴇʟʟᴇᴅ")
    try: p = int(m.text)
    except: return bot.send_message(m.chat.id, "⚠️ Iɴᴠᴀʟɪᴅ Nᴜᴍʙᴇʀ!")
    bot.register_next_step_handler(bot.send_message(m.chat.id, "✦ Sᴇɴᴅ Mᴀxɪᴍᴜᴍ Cʟᴀɪᴍꜱ Uꜱᴀɢᴇ Lɪᴍɪᴛ (e.g. 100):"), step_prom_lim, name, p)

def step_prom_lim(m, name, d):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❌ Cᴀɴᴄᴇʟʟᴇᴅ")
    try: l = int(m.text)
    except: return bot.send_message(m.chat.id, "⚠️ Iɴᴠᴀʟɪᴅ Nᴜᴍʙᴇʀ!")
    bot.register_next_step_handler(bot.send_message(m.chat.id, "✦ Sᴇɴᴅ Vᴀʟɪᴅɪᴛʏ Dᴜʀᴀᴛɪᴏɴ Iɴ Hᴏᴜʀꜱ (e.g. 24 ꜰᴏʀ 1 ᴅᴀʏ, 0 ꜰᴏʀ ɴᴇᴠᴇʀ-ᴇxᴘɪʀɪɴɢ):"), step_prom_time, name, d, l)

def step_prom_time(m, name, d, lim):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❌ Cᴀɴᴄᴇʟʟᴇᴅ")
    try: h = int(m.text)
    except: return bot.send_message(m.chat.id, "⚠️ Iɴᴠᴀʟɪᴅ Nᴜᴍʙᴇʀ!")
    db_update(f"promos/{name}", {"discount": d, "limit": lim, "expiry": int(time.time()) + (h * 3600) if h > 0 else 0, "used": 0})
    bot.send_message(m.chat.id, f"✅ <b>Aᴅᴠᴀɴᴄᴇᴅ Pʀᴏᴍᴏ Cᴏᴅᴇ '{name}' Sᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ Cʀᴇᴀᴛᴇᴅ!</b>", parse_mode="HTML")

def step_add_stcat(m):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❌ Cᴀɴᴄᴇʟʟᴇᴅ")
    db_update(f"stock_categories/{str(int(time.time()))}", {"name": m.text})
    bot.send_message(m.chat.id, "✅ Nᴇᴡ Sᴛᴏᴄᴋ Cᴀᴛᴇɢᴏʀʏ Sᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ Cʀᴇᴀᴛᴇᴅ!")

def step_adds_name(m, cid):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❌ Cᴀɴᴄᴇʟʟᴇᴅ")
    bot.register_next_step_handler(bot.send_message(m.chat.id, "✦ Sᴇɴᴅ Sᴛᴏᴄᴋ Sᴇʀᴠɪᴄᴇ Pʀɪᴄᴇ (Iɴ Pᴏɪɴᴛꜱ):"), step_adds_price, cid, m.text)

def step_adds_price(m, cid, name):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❌ Cᴀɴᴄᴇʟʟᴇᴅ")
    try: p = int(m.text)
    except: return bot.send_message(m.chat.id, "⚠️ Iɴᴠᴀʟɪᴅ Pʀɪᴄᴇ!")
    bot.register_next_step_handler(bot.send_message(m.chat.id, "✦ Sᴇɴᴅ Sᴛᴏᴄᴋ Sᴇʀᴠɪᴄᴇ Dᴇꜱᴄʀɪᴘᴛɪᴏɴ Tᴇxᴛ:"), step_adds_desc, cid, name, p)

def step_adds_desc(m, cid, name, price):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❌ Cᴀɴᴄᴇʟʟᴇᴅ")
    db_update(f"stock_categories/{cid}/services/{str(int(time.time()))}", {"name": name, "price": price, "desc": m.text, "stock": [], "sold": 0})
    bot.send_message(m.chat.id, f"✅ Sᴛᴏᴄᴋ Sᴇʀᴠɪᴄᴇ Sᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ Cʀᴇᴀᴛᴇᴅ! Nᴏᴡ ᴄʟɪᴄᴋ ᴏɴ ɪᴛ ᴛᴏ ᴀᴅᴅ ꜱᴛᴏᴄᴋ ɪᴛᴇᴍꜱ.")

def step_edit_stsrv(m, cid, sid, field):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❌ Cᴀɴᴄᴇʟʟᴇᴅ")
    if field == "price":
        try: val = int(m.text)
        except: return bot.send_message(m.chat.id, "⚠️ Iɴᴠᴀʟɪᴅ Pʀɪᴄᴇ!")
    else:
        val = m.text
    db_update(f"stock_categories/{cid}/services/{sid}", {field: val})
    bot.send_message(m.chat.id, f"✅ Sᴛᴏᴄᴋ Sᴇʀᴠɪᴄᴇ Pᴀʀᴀᴍᴇᴛᴇʀ Sᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ Uᴘᴅᴀᴛᴇᴅ!")

def step_vip_price(m):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❌ Cᴀɴᴄᴇʟʟᴇᴅ")
    try: vp = int(m.text)
    except: return bot.send_message(m.chat.id, "⚠️ Iɴᴠᴀʟɪᴅ Pʀɪᴄᴇ!")
    db_update("settings", {"vip_price": vp})
    bot.register_next_step_handler(bot.send_message(m.chat.id, "✦ Sᴇɴᴅ VIP Mᴇᴍʙᴇʀꜱʜɪᴘ Vᴀʟɪᴅɪᴛʏ Iɴ Cᴀʟᴇɴᴅᴀʀ Dᴀʏꜱ:"), step_vip_days)

def step_vip_days(m):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❌ Cᴀɴᴄᴇʟʟᴇᴅ")
    try: vd = int(m.text)
    except: return bot.send_message(m.chat.id, "⚠️ Iɴᴠᴀʟɪᴅ Dᴀʏꜱ!")
    db_update("settings", {"vip_days": vd})
    bot.register_next_step_handler(bot.send_message(m.chat.id, "✦ Sᴇɴᴅ VIP Uɴɪᴠᴇʀꜱᴀʟ Dɪꜱᴄᴏᴜɴᴛ Pᴇʀᴄᴇɴᴛᴀɢᴇ % (e.g. 10):"), step_vip_disc)

def step_vip_disc(m):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❌ Cᴀɴᴄᴇʟʟᴇᴅ")
    try: vd = int(m.text)
    except: return bot.send_message(m.chat.id, "⚠️ Iɴᴠᴀʟɪᴅ Dɪꜱᴄᴏᴜɴᴛ!")
    db_update("settings", {"vip_discount": vd})
    bot.send_message(m.chat.id, "✅ VIP Mᴇᴍʙᴇʀꜱʜɪᴘ Pᴀʀᴀᴍᴇᴛᴇʀꜱ Sᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ Sᴀᴠᴇᴅ!")

def step_comm_first(m):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❌ Cᴀɴᴄᴇʟʟᴇᴅ")
    try: c = int(m.text)
    except: return bot.send_message(m.chat.id, "⚠️ Iɴᴠᴀʟɪᴅ Pᴇʀᴄᴇɴᴛᴀɢᴇ!")
    db_update("settings", {"first_dep_comm": c})
    bot.register_next_step_handler(bot.send_message(m.chat.id, "✦ Sᴇɴᴅ Cᴏᴍᴍɪꜱꜱɪᴏɴ % Fᴏʀ <b>Aʟʟ Oᴛʜᴇʀ Sᴜʙꜱᴇǫᴜᴇɴᴛ Dᴇᴘᴏꜱɪᴛꜱ</b>:", parse_mode="HTML"), step_comm_reg)

def step_comm_reg(m):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❌ Cᴀɴᴄᴇʟʟᴇᴅ")
    try: c = int(m.text)
    except: return bot.send_message(m.chat.id, "⚠️ Iɴᴠᴀʟɪᴅ Pᴇʀᴄᴇɴᴛᴀɢᴇ!")
    db_update("settings", {"reg_dep_comm": c})
    bot.send_message(m.chat.id, "✅ Mᴜʟᴛɪ-Tɪᴇʀ Aꜰꜰɪʟɪᴀᴛᴇ Cᴏᴍᴍɪꜱꜱɪᴏɴ Sᴛʀᴜᴄᴛᴜʀᴇ Sᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ Uᴘᴅᴀᴛᴇᴅ!")

def step_ms_reach(m):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❌ Cᴀɴᴄᴇʟʟᴇᴅ")
    try: reach = int(m.text)
    except: return bot.send_message(m.chat.id, "⚠️ Iɴᴠᴀʟɪᴅ Cᴏᴜɴᴛ!")
    bot.register_next_step_handler(bot.send_message(m.chat.id, "✦ Sᴇɴᴅ Rᴇᴡᴀʀᴅ Pᴏɪɴᴛꜱ Fᴏʀ Tʜɪꜱ Mɪʟᴇꜱᴛᴏɴᴇ:"), step_ms_reward, reach)

def step_ms_reward(m, r):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❌ Cᴀɴᴄᴇʟʟᴇᴅ")
    try: reward = int(m.text)
    except: return bot.send_message(m.chat.id, "⚠️ Iɴᴠᴀʟɪᴅ Rᴇᴡᴀʀᴅ!")
    db_update(f"milestones/{str(int(time.time()))}", {"reach": r, "reward": reward})
    bot.send_message(m.chat.id, "✅ Rᴇꜰᴇʀʀᴀʟ Mɪʟᴇꜱᴛᴏɴᴇ Sᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ Cʀᴇᴀᴛᴇᴅ!")

def step_user_redeem_code(m):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❖ Cᴀɴᴄᴇʟʟᴇᴅ", reply_markup=back_keyboard("main_menu"))
    code = m.text.strip().upper()
    user_id = str(m.from_user.id)
    if db_get(f"users/{user_id}/redeemed/{code}"): return bot.send_message(m.chat.id, "❖ <b>Yᴏᴜ Hᴀᴠᴇ Aʟʀᴇᴀᴅʏ Claimed Tʜɪꜱ Gɪꜰᴛ Cᴏᴅᴇ!</b>", parse_mode="HTML")
    code_data = db_get(f"codes/{code}")
    if not code_data or code_data.get("uses", 0) <= 0: return bot.send_message(m.chat.id, "❖ <b>Iɴᴠᴀʟɪᴅ Oʀ Aʟʀᴇᴀᴅʏ Exᴘɪʀᴇᴅ Cᴏᴅᴇ!</b>", parse_mode="HTML")
    
    db_update(f"users/{user_id}", {"points": (db_get(f"users/{user_id}/points") or 0) + code_data["amount"]})
    db_update(f"users/{user_id}/redeemed", {code: True})
    db_update(f"codes/{code}", {"uses": code_data["uses"] - 1})
    bot.send_message(m.chat.id, f"⎚ <b>Gɪꜰᴛ Cᴏᴅᴇ Sᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ Rᴇᴅᴇᴇᴍᴇᴅ!</b>\n✦ Aᴅᴅᴇᴅ Rᴇᴡᴀʀᴅ: <code>+{code_data['amount']} Pᴏɪɴᴛꜱ</code>", parse_mode="HTML")

def step_code_name(m):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❌ Cᴀɴᴄᴇʟʟᴇᴅ")
    bot.register_next_step_handler(bot.send_message(m.chat.id, "✦ Sᴇɴᴅ Rᴇᴡᴀʀᴅ Pᴏɪɴᴛꜱ Aᴍᴏᴜɴᴛ:"), step_code_reward, m.text.upper())

def step_code_reward(m, code):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❌ Cᴀɴᴄᴇʟʟᴇᴅ")
    try: amt = int(m.text)
    except: return bot.send_message(m.chat.id, "⚠️ Iɴᴠᴀʟɪᴅ Aᴍᴏᴜɴᴛ!")
    bot.register_next_step_handler(bot.send_message(m.chat.id, "✦ Hᴏᴡ Mᴀɴʏ Uꜱᴇꜱ? (e.g. 10):"), step_code_limit, code, amt)

def step_code_limit(m, code, amt):
    if m.text and m.text == '/cancel': return bot.send_message(m.chat.id, "❌ Cᴀɴᴄᴇʟʟᴇᴅ")
    try: limit = int(m.text)
    except: return bot.send_message(m.chat.id, "⚠️ Iɴᴠᴀʟɪᴅ Lɪᴍɪᴛ!")
    db_update(f"codes/{code}", {"amount": amt, "uses": limit})
    bot.send_message(m.chat.id, f"✅ Rᴇᴅᴇᴇᴍ Cᴏᴅᴇ '{code}' Sᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ Cʀᴇᴀᴛᴇᴅ!")

print("✨ GOD-LEVEL TERMUX MEGA SCRIPT IS ONLINE! ✨")
threading.Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000))), daemon=True).start()
bot.infinity_polling()
