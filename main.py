import os
import re
import json
import pyotp
import pandas as pd
from faker import Faker
from datetime import datetime
from telegram import (
    Update, 
    ReplyKeyboardMarkup, 
    KeyboardButton, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

# USA Name Generator Setup
fake = Faker('en_US')

# --- CONFIGURATION ---
BOT_TOKEN = "8820382524:AAH7zkiLSptvPpBWQuQFB679WQAONy2k0WA"

# Required Telegram Channel Username & Link
CHANNEL_USERNAME = "@rotgofficial"
CHANNEL_LINK = "https://t.me/rotgofficial"

# Admin Username Configuration (Must include @)
ADMIN_USERNAME = "JohnRipper1337"

# JSON file to store unique user IDs
USERS_FILE = "registered_users.json"

# In-memory storage for active tasks & admin states
user_tasks = {}
admin_states = {}

# --- HELPER FUNCTIONS ---

def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_user(user_id):
    users = load_users()
    if user_id not in users:
        users.add(user_id)
        with open(USERS_FILE, "w") as f:
            json.dump(list(users), f)

def clean_secret_key(raw_key):
    if not raw_key:
        return ""
    return re.sub(r'[^A-Za-z2-7]', '', str(raw_key)).upper()

def get_daily_password():
    today_day = datetime.now().strftime('%d')
    return f"@ratmethod{today_day}"

def get_user_file_dir(user_id):
    path = os.path.join("user_data", f"user_{user_id}")
    os.makedirs(path, exist_ok=True)
    return path

def get_today_excel_file(user_id):
    user_dir = get_user_file_dir(user_id)
    filename = f"Tasks_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
    return os.path.join(user_dir, filename)

# স্থায়ী কিবোর্ড জেনারেটর (এডমিন হলে অতিরিক্ত Admin Panel বাটন থাকবে)
def get_persistent_keyboard(user_handle=None):
    keyboard = [
        [KeyboardButton("➕ New Task"), KeyboardButton("📁 File Manager")],
        [KeyboardButton("✅ Done (Submit 2FA)"), KeyboardButton("❌ Cancel")],
        [KeyboardButton("📤 Submit Task")]
    ]
    if user_handle and user_handle.lower() == ADMIN_USERNAME.lower():
        keyboard.append([KeyboardButton("👑 Admin Dashboard")])
        
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def is_user_joined(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        if member.status in ['creator', 'administrator', 'member']:
            return True
        return False
    except Exception as e:
        print(f"Channel membership check error: {e}")
        return False

async def send_join_request(update: Update):
    keyboard = [
        [InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK)],
        [InlineKeyboardButton("🔄 Verify / Check Join", callback_data="check_join")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = (
        "🔒 **Access Restricted!**\n\n"
        "এই বটটি ব্যবহার করতে হলে আপনাকে আমাদের অফিশিয়াল টেলিগ্রাম চ্যানেলে জয়েন করতে হবে।\n"
        "নিচের বাটনে ক্লিক করে জয়েন করুন এবং 'Verify' চাপুন।"
    )
    if update.message:
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.message.reply_text(msg, parse_mode="Markdown", reply_markup=reply_markup)

# /start কমান্ড
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user.id)
    
    if not await is_user_joined(context, user.id):
        await send_join_request(update)
        return

    reply_markup = get_persistent_keyboard(user.username)
    await update.message.reply_text(
        "👋 Welcome to Rubel Task Bot!\n\nNicer button press kore task ba file manage করুন।",
        reply_markup=reply_markup
    )

def get_file_manager_markup(user_id):
    user_dir = get_user_file_dir(user_id)
    files = [f for f in os.listdir(user_dir) if f.endswith(".xlsx")]
    
    keyboard = []
    if not files:
        keyboard.append([InlineKeyboardButton("❌ No Excel Files Found", callback_data="none")])
    else:
        for f in files:
            keyboard.append([InlineKeyboardButton(f"📄 {f}", callback_data=f"file_opt_{f}")])
            
    keyboard.append([InlineKeyboardButton("❌ Close Manager", callback_data="close_manager")])
    return InlineKeyboardMarkup(keyboard)

# Admin Dashboard UI
def get_admin_dashboard_markup():
    keyboard = [
        [
            InlineKeyboardButton("📊 Total Users", callback_data="admin_user_count"),
            InlineKeyboardButton("📢 Broadcast Msg", callback_data="admin_broadcast_start")
        ],
        [InlineKeyboardButton("❌ Close Dashboard", callback_data="close_manager")]
    ]
    return InlineKeyboardMarkup(keyboard)

# Callback Handler
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    data = query.data

    if data == "check_join":
        if await is_user_joined(context, user.id):
            await query.message.delete()
            await query.message.reply_text(
                "✅ Verification Successful!\nEkhon apni bot ti bebohar korte parben.",
                reply_markup=get_persistent_keyboard(user.username)
            )
        else:
            await query.answer("❌ Apni ekhono channel-e join korenni!", show_alert=True)
        return

    if not await is_user_joined(context, user.id):
        await send_join_request(update)
        return

    if data == "close_manager":
        await query.message.delete()
        return

    # Admin Callback Handling
    if user.username and user.username.lower() == ADMIN_USERNAME.lower():
        if data == "admin_user_count":
            total = len(load_users())
            await query.answer(f"👥 Total Bot Users: {total}", show_alert=True)
            return
        elif data == "admin_broadcast_start":
            admin_states[user.id] = "WAITING_BROADCAST_TEXT"
            await query.edit_message_text(
                "📢 **Broadcast Mode Active**\n\nযে মেসেজটি সব ইউজারের কাছে পাঠাতে চান, তা লিখে মেসেজ দিন।\n(ক্যানসেল করতে চাইলে '❌ Cancel' লিখুন)",
                parse_mode="Markdown"
            )
            return

    # File Manager Callbacks
    if data.startswith("file_opt_"):
        filename = data.replace("file_opt_", "")
        keyboard = [
            [
                InlineKeyboardButton("📥 Download", callback_data=f"dl_{filename}"),
                InlineKeyboardButton("🗑️ Delete", callback_data=f"del_{filename}")
            ],
            [InlineKeyboardButton("✏️ Remove Last Entry", callback_data=f"edit_pop_{filename}")],
            [InlineKeyboardButton("🔙 Back to List", callback_data="back_to_list")]
        ]
        await query.edit_message_text(
            f"📁 **File:** `{filename}`\nKi korte chan select করুন:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == "back_to_list":
        await query.edit_message_text(
            "📁 **File Manager (Your Excel Files):**",
            parse_mode="Markdown",
            reply_markup=get_file_manager_markup(user.id)
        )

    elif data.startswith("dl_"):
        filename = data.replace("dl_", "")
        file_path = os.path.join(get_user_file_dir(user.id), filename)
        if os.path.exists(file_path):
            await query.message.reply_document(document=open(file_path, 'rb'), caption=f"📄 {filename}")
        else:
            await query.answer("❌ File not found!", show_alert=True)

    elif data.startswith("del_"):
        filename = data.replace("del_", "")
        file_path = os.path.join(get_user_file_dir(user.id), filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            await query.answer("✅ File deleted successfully!")
            await query.edit_message_text(
                "📁 **File Manager (Your Excel Files):**",
                parse_mode="Markdown",
                reply_markup=get_file_manager_markup(user.id)
            )
        else:
            await query.answer("❌ File not found!", show_alert=True)

    elif data.startswith("edit_pop_"):
        filename = data.replace("edit_pop_", "")
        file_path = os.path.join(get_user_file_dir(user.id), filename)
        if os.path.exists(file_path):
            try:
                df = pd.read_excel(file_path, dtype=str)
                if not df.empty:
                    df = df.iloc[:-1]
                    df.to_excel(file_path, index=False)
                    await query.answer("✅ Last entry removed from file!")
                else:
                    await query.answer("⚠️ File is already empty!", show_alert=True)
            except Exception as e:
                await query.answer(f"❌ Error updating file: {e}", show_alert=True)
        else:
            await query.answer("❌ File not found!", show_alert=True)

# Message Handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_id = user.id
    text = update.message.text.strip()
    
    save_user(user_id)
    reply_markup = get_persistent_keyboard(user.username)

    if not await is_user_joined(context, user_id):
        await send_join_request(update)
        return

    # --- BROADCAST SYSTEM FOR ADMIN ---
    if user.username and user.username.lower() == ADMIN_USERNAME.lower() and admin_states.get(user_id) == "WAITING_BROADCAST_TEXT":
        if text == "❌ Cancel":
            del admin_states[user_id]
            await update.message.reply_text("❌ Broadcast cancelled.", reply_markup=reply_markup)
            return

        users = load_users()
        success = 0
        failed = 0
        
        await update.message.reply_text(f"⏳ Sending broadcast to {len(users)} users...")
        
        for uid in users:
            try:
                await context.bot.send_message(chat_id=uid, text=text)
                success += 1
            except Exception:
                failed += 1
                
        del admin_states[user_id]
        await update.message.reply_text(
            f"✅ **Broadcast Finished!**\n\n🎯 Success: `{success}`\n❌ Failed/Blocked: `{failed}`",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        return

    # --- ADMIN DASHBOARD BUTTON ---
    if text == "👑 Admin Dashboard" and user.username and user.username.lower() == ADMIN_USERNAME.lower():
        total_users = len(load_users())
        msg = f"⚙️ **Admin Control Panel**\n\n👤 Logged Admin: @{ADMIN_USERNAME}\n📊 Total Users in DB: `{total_users}`"
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=get_admin_dashboard_markup())
        return

    # --- ➕ New Task Button ---
    if text == "➕ New Task":
        full_name = fake.name()
        first_name = fake.first_name()
        last_name = fake.last_name()
        random_num = fake.random_int(min=100, max=9999)
        generated_username = f"{first_name.lower()}{last_name.lower()}{random_num}"
        
        current_password = get_daily_password()

        user_tasks[user_id] = {
            "name": full_name,
            "username": generated_username,
            "password": current_password,
            "2fa": None,
            "state": "IDLE"
        }

        msg = (
            f"🎯 **New Task Generated!**\n\n"
            f"📛 **Name:** `{full_name}`\n"
            f"👤 **Username:** `{generated_username}`\n"
            f"🔑 **Password:** `{current_password}`\n\n"
            f"Task complete hole নিচের '✅ Done (Submit 2FA)' বাটন প্রেস করুন।"
        )
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=reply_markup)

    # --- 📁 File Manager Button ---
    elif text == "📁 File Manager":
        await update.message.reply_text(
            "📁 **File Manager (Your Excel Files):**",
            parse_mode="Markdown",
            reply_markup=get_file_manager_markup(user_id)
        )

    # --- ✅ Done (Submit 2FA) Button ---
    elif text == "✅ Done (Submit 2FA)":
        if user_id in user_tasks:
            user_tasks[user_id]["state"] = "WAITING_FOR_2FA"
            await update.message.reply_text(
                "📥 Ekhon apnar **2FA Secret Key**-ti message hisebe pathan:",
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text("❌ Kono active task pawa jayni. '➕ New Task' প্রেস করুন।", reply_markup=reply_markup)

    # --- ❌ Cancel Button ---
    elif text == "❌ Cancel":
        if user_id in user_tasks:
            del user_tasks[user_id]
        await update.message.reply_text("❌ Task Cancelled! Excel-e save kora hoyni.", reply_markup=reply_markup)

    # --- 📤 Submit Task Button ---
    elif text == "📤 Submit Task":
        if user_id in user_tasks and user_tasks[user_id].get("2fa"):
            task = user_tasks[user_id]
            excel_file = get_today_excel_file(user_id)

            new_data = {
                "Name": [task["name"]],
                "Username": [task["username"]],
                "Password": [task["password"]],
                "2FA_Secret": [task["2fa"]]
            }
            df_new = pd.DataFrame(new_data)

            try:
                if os.path.exists(excel_file):
                    df_existing = pd.read_excel(excel_file, dtype=str)
                    df_combined = pd.concat([df_existing, df_new], ignore_index=True)
                    df_combined.to_excel(excel_file, index=False)
                else:
                    df_new.to_excel(excel_file, index=False)

                del user_tasks[user_id]

                await update.message.reply_text("✅ Task successfully saved to **Excel Sheet (.xlsx)**!", parse_mode="Markdown", reply_markup=reply_markup)

            except Exception as e:
                await update.message.reply_text(f"❌ Error saving to Excel: {e}", reply_markup=reply_markup)
        else:
            await update.message.reply_text("⚠️ Age 2FA Secret Key pathan, tarpor Submit korun!", reply_markup=reply_markup)

    # --- Handling 2FA Input Text ---
    elif user_id in user_tasks and user_tasks[user_id].get("state") == "WAITING_FOR_2FA":
        secret_key = clean_secret_key(text)

        if not secret_key:
            await update.message.reply_text("⚠️ Invalid 2FA Key! Sothik 2FA Secret Key pathan:", reply_markup=reply_markup)
            return

        try:
            totp = pyotp.TOTP(secret_key)
            otp_code = totp.now()

            user_tasks[user_id]["2fa"] = secret_key
            user_tasks[user_id]["state"] = "READY_TO_SUBMIT"

            await update.message.reply_text(
                f"🔑 **Generated OTP:** `{otp_code}`\n\n"
                f"Excel Sheet-e save korte নিচের **'📤 Submit Task'** বাটন প্রেস করুন।",
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
        except Exception:
            await update.message.reply_text("❌ Invalid 2FA Secret Key. Sothik key pathan:", reply_markup=reply_markup)

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Rubel Bot is running with Admin Dashboard & Broadcast Support...")
    app.run_polling()
