# server.py
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import threading
import telebot
import uuid
import psycopg2
import os
from urllib.parse import urlparse
from datetime import datetime, timedelta

# =============================
# CONFIG
# =============================
BOT_TOKEN = os.getenv("BOT_TOKEN")
SITE_URL = os.getenv("SITE_URL")  # например: https://libraryofgames.netlify.app
PORT = int(os.environ.get("PORT", 8080))

# 👉 ВСЁ ЛЕЖИТ В КОРНЕ, ИСПОЛЬЗУЕМ DIRNAME
SITE_DIR = os.path.dirname(__file__)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL не найден!")

# =============================
# Database
# =============================
url = urlparse(DATABASE_URL)
conn = psycopg2.connect(
    dbname=url.path[1:],
    user=url.username,
    password=url.password,
    host=url.hostname,
    port=url.port
)
cursor = conn.cursor()

# =============================
# Telegram Bot
# =============================
bot = telebot.TeleBot(BOT_TOKEN)

def get_user_id(tg_id):
    cursor.execute("SELECT id FROM users WHERE tg_id=%s", (tg_id,))
    r = cursor.fetchone()
    return r[0] if r else None

def generate_token(user_id):
    token = str(uuid.uuid4())
    expires_at = datetime.utcnow() + timedelta(minutes=10)
    cursor.execute(
        """
        INSERT INTO auth_tokens (user_id, token, expires_at)
        VALUES (%s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE
        SET token = EXCLUDED.token, expires_at = EXCLUDED.expires_at
        """,
        (user_id, token, expires_at)
    )
    conn.commit()
    return token

# =============================
# Bot commands
# =============================
@bot.message_handler(commands=['start'])
def start_cmd(message):
    tg_id = message.from_user.id
    username = message.from_user.username

    cursor.execute("SELECT id FROM users WHERE tg_id=%s", (tg_id,))
    user = cursor.fetchone()

    if not user:
        cursor.execute(
            "INSERT INTO users (tg_id, username) VALUES (%s, %s) RETURNING id",
            (tg_id, username)
        )
        new_user_id = cursor.fetchone()[0]

        cursor.execute(
            "INSERT INTO stats (user_id, xp, coins, level) VALUES (%s, 0, 0, 1)",
            (new_user_id,)
        )
        conn.commit()

    bot.send_message(message.chat.id,
        "Привет! Добро пожаловать в Library of Games!\n"
        "• /games — вход на сайт\n"
        "• /stats — статистика\n"
        "• /help — команды"
    )

@bot.message_handler(commands=['games'])
def games_cmd(message):
    tg_id = message.from_user.id
    user_id = get_user_id(tg_id)
    if not user_id:
        bot.send_message(message.chat.id, "Ошибка: пользователь не найден.")
        return

    if not SITE_URL:
        bot.send_message(message.chat.id, "Ошибка: SITE_URL не задан.")
        return

    token = generate_token(user_id)
    link = f"{SITE_URL}/login?token={token}"

    btn = telebot.types.InlineKeyboardButton("Перейти на сайт 🎮", url=link)
    markup = telebot.types.InlineKeyboardMarkup().add(btn)

    bot.send_message(message.chat.id, "Нажми кнопку:", reply_markup=markup)

@bot.message_handler(commands=['stats'])
def stats_cmd(message):
    tg_id = message.from_user.id
    cursor.execute("""
        SELECT xp, coins, level
        FROM stats
        JOIN users ON stats.user_id = users.id
        WHERE users.tg_id=%s
    """, (tg_id,))
    s = cursor.fetchone()
    if not s:
        bot.send_message(message.chat.id, "Статистика не найдена.")
        return
    xp, coins, level = s
    bot.send_message(
        message.chat.id,
        f"📊 Статистика:\nУровень: {level}\nXP: {xp}\nМонеты: {coins}"
    )


# =============================
# Flask
# =============================
app = Flask(__name__, static_folder=SITE_DIR, static_url_path='')
CORS(app)

@app.route('/')
def index():
    return send_from_directory(SITE_DIR, 'index.html')

# 👉 Чтобы /login открывал login.html
@app.route('/login')
def login_page():
    return send_from_directory(SITE_DIR, 'login.html')

# Остальные файлы (CSS/JS/etc)
@app.route('/<path:path>')
def static_files(path):
    return send_from_directory(SITE_DIR, path)


@app.post("/api/auth/verify")
def verify():
    data = request.get_json()
    token = data.get("token")
    cursor.execute("""
        SELECT users.id, users.username, auth_tokens.expires_at
        FROM auth_tokens
        JOIN users ON users.id = auth_tokens.user_id
        WHERE token=%s
    """, (token,))
    row = cursor.fetchone()
    if not row:
        return jsonify({"success": False, "error": "invalid"})
    user_id, username, expires_at = row
    if datetime.utcnow() > expires_at:
        return jsonify({"success": False, "error": "expired"})
    session_id = str(uuid.uuid4())
    cursor.execute(
        "INSERT INTO sessions (user_id, session_id) VALUES (%s, %s)",
        (user_id, session_id)
    )
    conn.commit()
    return jsonify({"success": True, "username": username, "session": session_id})

@app.get("/api/user")
def get_user():
    session_id = request.args.get("session")
    cursor.execute("""
        SELECT users.username, users.tg_id
        FROM sessions
        JOIN users ON users.id = sessions.user_id
        WHERE sessions.session_id=%s
    """, (session_id,))
    row = cursor.fetchone()
    if not row:
        return jsonify({"success": False})
    username, tg_id = row
    return jsonify({"success": True, "username": username, "tg_id": tg_id})

# =============================
# Telegram polling thread
# =============================
def run_bot():
    bot.remove_webhook()  # убираем любой предыдущий webhook
    bot.infinity_polling(skip_pending=True)

threading.Thread(target=run_bot).start()

# =============================
# Flask
# =============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)


