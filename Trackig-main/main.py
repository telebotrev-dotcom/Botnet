import json
import re
import sqlite3
from datetime import datetime
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# --- SETTINGS LANGSUNG DI SCRIPT ---
TELEGRAM_BOT_TOKEN = "8551821431:AAGixisAcP3yh_BEu729hu0Vy1ihcrcn79o"
ADMIN_IDS = ["8086581937"]  # ganti dengan user ID admin

DB_FILE = 'bot_data.db'

# --- DATABASE ---
def init_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            first_name TEXT,
            username TEXT,
            last_activity TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usage_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username_searched TEXT,
            timestamp TEXT
        )
    ''')
    conn.commit()
    conn.close()

def log_user_activity(user_id, first_name, username_tele):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, first_name, username, last_activity)
        VALUES (?, ?, ?, ?)
    ''', (user_id, first_name, username_tele, timestamp))
    conn.commit()
    conn.close()

def log_search_query(user_id, username_searched):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('''
        INSERT INTO usage_log (user_id, username_searched, timestamp)
        VALUES (?, ?, ?)
    ''', (user_id, username_searched, timestamp))
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, first_name, username, last_activity FROM users")
    users = cursor.fetchall()
    conn.close()
    return users

def get_total_searches():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM usage_log")
    total = cursor.fetchone()[0]
    conn.close()
    return total

# --- INSTAGRAM ---
def get_instagram_user_data(username):
    url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'X-IG-App-ID': '936619743392459',
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error fetch IG data: {e}")
    return None

def analyze_profile_completeness(user):
    completeness_score = 0
    total_items = 5
    if user.get('biography'): completeness_score += 1
    if user.get('external_url'): completeness_score += 1
    if user.get('profile_pic_url_hd'): completeness_score += 1
    if user.get('full_name') and user['full_name'].strip(): completeness_score += 1
    if user.get('edge_owner_to_timeline_media', {}).get('count', 0) > 0: completeness_score += 1
    return f"{(completeness_score / total_items) * 100:.0f}%"

def get_account_age_estimate(user_data):
    try:
        posts = user_data['data']['user']['edge_owner_to_timeline_media']['edges']
        if posts:
            oldest_post = posts[-1]['node']['taken_at_timestamp']
            account_age = (datetime.now().timestamp() - oldest_post) / (365 * 24 * 3600)
            return f"{account_age:.1f} tahun"
    except:
        pass
    return "Tidak dapat diestimasi"

def analyze_following_pattern(followers, following):
    if following == 0: return "Tidak following siapapun"
    ratio = followers / following if following > 0 else 0
    if ratio > 10: return "Popular (Followers >> Following) 🎯"
    elif ratio > 5: return "Selective Following ⚡"
    elif ratio > 1: return "Balanced Following ⚖️"
    elif ratio > 0.5: return "Followback Strategy 🤝"
    else: return "Mass Following 📈"

def extract_profile_insights(user):
    bio = user.get('biography', '')
    return {
        'has_email': bool(re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', bio)),
        'has_phone': bool(re.search(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}\b|\b\d{3}[-\s]?\d{4}[-\s]?\d{4}\b', bio)),
        'has_links': bool(re.search(r'https?://[^\s]+', bio)),
        'bio_length': len(bio),
        'word_count': len(bio.split())
    }

def format_profile_details(data):
    if not data or 'data' not in data:
        return "❌ Data tidak valid."
    try:
        user = data['data']['user']
        followers = user['edge_followed_by']['count']
        following = user['edge_follow']['count']
        posts = user['edge_owner_to_timeline_media']['count']
        insights = extract_profile_insights(user)
        return (
            f"*INFORMASI PENGGUNA*\n\n"
            f"👤 *Username:* @{user['username']}\n"
            f"✍️ *Nama Lengkap:* {user['full_name']}\n"
            f"📝 *Bio:* {user.get('biography', 'Tidak ada bio')}\n"
            f"🌐 *Website:* {user.get('external_url', 'Tidak ada')}\n"
            f"🔗 *Profil URL:* https://www.instagram.com/{user['username']}/\n\n"
            f"👥 *Followers:* {followers:,}\n"
            f"🤝 *Following:* {following:,}\n"
            f"🖼️ *Total Post:* {posts:,}\n"
            f"⚖️ *Rasio Follow:* {analyze_following_pattern(followers, following)}\n\n"
            f"✅ *Terverifikasi:* {'Ya' if user.get('is_verified') else 'Tidak'}\n"
            f"🔒 *Private:* {'Ya' if user.get('is_private') else 'Tidak'}\n"
            f"⏳ *Estimasi Usia Akun:* {get_account_age_estimate(data)}\n"
            f"📊 *Kelengkapan Profil:* {analyze_profile_completeness(user)}\n\n"
            f"🔍 *Analisis Bio:*\n"
            f"  - Panjang Bio: {insights['bio_length']} karakter\n"
            f"  - Jumlah Kata: {insights['word_count']} kata\n"
            f"  - Email di Bio: {'✅ Ya' if insights['has_email'] else '❌ Tidak'}\n"
            f"  - Telepon di Bio: {'✅ Ya' if insights['has_phone'] else '❌ Tidak'}\n"
            f"  - Link di Bio: {'✅ Ya' if insights['has_links'] else '❌ Tidak'}\n\n"
            f"ℹ️ *User ID:* {user.get('id', 'N/A')}"
        )
    except Exception as e:
        return f"❌ Terjadi kesalahan saat memproses data: {e}"

# --- BOT TELEGRAM ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_user_activity(user.id, user.first_name, user.username)
    await update.message.reply_text(
        "Halo! Saya adalah bot untuk mencari informasi profil Instagram.\n\n"
        "Gunakan perintah `/get <username>` untuk memulai. Contoh:\n"
        "`/get instagram`",
        parse_mode='Markdown'
    )

async def get_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from telegram import InputMediaPhoto
    user = update.effective_user
    log_user_activity(user.id, user.first_name, user.username)
    
    if not context.args:
        await update.message.reply_text("Silakan berikan username. Contoh: `/get instagram`")
        return
    
    username = context.args[0].replace('@', '').strip()
    log_search_query(user.id, username)
    
    message_sent = await update.message.reply_text(f"Sedang mencari data untuk *@{username}*...", parse_mode='Markdown')
    
    data = get_instagram_user_data(username)
    if not data or 'data' not in data:
        await message_sent.edit_text(f"❌ Maaf, tidak dapat mengambil data untuk *@{username}*.", parse_mode='Markdown')
        return

    user_data = data['data']['user']
    text = format_profile_details(data)
    profile_pic = user_data.get('profile_pic_url_hd')
    
    if profile_pic:
        await message_sent.delete()
        await update.message.reply_photo(photo=profile_pic, caption=text, parse_mode='Markdown')
    else:
        await message_sent.edit_text(text, parse_mode='Markdown')

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if str(user.id) not in ADMIN_IDS:
        await update.message.reply_text("❌ Maaf, Anda tidak memiliki akses ke menu ini.")
        return
    
    users_list = get_all_users()
    total_searches = get_total_searches()
    user_count = len(users_list)
    
    user_info_text = "Daftar Pengguna:\n\n"
    if user_count > 0:
        for u in users_list:
            user_info_text += f"- ID: `{u[0]}`\n"
            user_info_text += f"  Nama: {u[1]} (@{u[2]})\n" if u[2] else f"  Nama: {u[1]}\n"
            user_info_text += f"  Aktivitas Terakhir: {u[3]}\n\n"
    else:
        user_info_text = "Belum ada pengguna terdaftar."
    
    admin_message = (
        "*MENU ADMIN*\n\n"
        f"👥 *Total Pengguna:* {user_count}\n"
        f"🔎 *Total Pencarian:* {total_searches}\n\n"
        f"{user_info_text}"
    )
    await update.message.reply_text(admin_message, parse_mode='Markdown')

# --- MAIN ---
def main():
    init_db()
    
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("get", get_info_command))
    application.add_handler(CommandHandler("admin", admin_command))
    
    print("Bot berjalan...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()