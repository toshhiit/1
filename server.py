from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import threading
import telebot
import uuid
import psycopg2
import os
from urllib.parse import urlparse
from datetime import datetime, timezone, timedelta

BOT_TOKEN = os.getenv("BOT_TOKEN")
SITE_URL = os.getenv("SITE_URL")
PORT = int(os.environ.get("PORT", 8080))
SITE_DIR = os.path.dirname(__file__)
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL не найден!")

# =============== DB CONNECT ===============
url = urlparse(DATABASE_URL)
conn = psycopg2.connect(
    dbname=url.path[1:],
    user=url.username,
    password=url.password,
    host=url.hostname,
    port=url.port
)
cursor = conn.cursor()

# =============== BOT ===============
bot = telebot.TeleBot(BOT_TOKEN)

def get_user_id(tg_id):
    cursor.execute("SELECT id FROM users WHERE tg_id=%s", (tg_id,))
    row = cursor.fetchone()
    return row[0] if row else None


# =============== TOKEN GENERATOR (исправленный) ===============
def generate_token(user_id):
    token = str(uuid.uuid4())
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()

    cursor.execute("""
        INSERT INTO auth_tokens (user_id, token, expires_at)
        VALUES (%s, %s, %s)
        ON CONFLICT (token)
        DO UPDATE SET expires_at = EXCLUDED.expires_at
        RETURNING token;
    """, (user_id, token, expires_at))

    conn.commit()
    return cursor.fetchone()[0]


# =============== COMMAND: /start ===============
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
        "Добро пожаловать в Library of Games!\n"
        "• /games — вход на сайт\n"
        "• /stats — статистика\n"
        "• /help — помощь"
    )


# =============== COMMAND: /games ===============
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


# =============== COMMAND: /stats ===============
@bot.message_handler(commands=['stats'])
def stats_cmd(message):
    tg_id = message.from_user.id

    cursor.execute("""
        SELECT xp, coins, level
        FROM stats
        JOIN users ON users.id = stats.user_id
        WHERE users.tg_id=%s
    """, (tg_id,))

    row = cursor.fetchone()
    if not row:
        bot.send_message(message.chat.id, "Статистика не найдена.")
        return

    xp, coins, level = row
    bot.send_message(message.chat.id, f"📊 Статистика:\nУровень: {level}\nXP: {xp}\nМонеты: {coins}")


# =============== FLASK ===============
app = Flask(__name__, static_folder=SITE_DIR, static_url_path='')
CORS(app)

@app.route('/')
def index():
    return send_from_directory(SITE_DIR, 'index.html')

@app.route('/login')
def login_page():
    return send_from_directory(SITE_DIR, 'login.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory(SITE_DIR, path)


# =============== API: VERIFY TOKEN ===============
@app.post("/api/auth/verify")
def verify():
    data = request.get_json()
    token = data.get("token")

    if not token:
        return jsonify({"success": False, "error": "no_token"})

    cursor.execute("""
        SELECT users.id, users.username, auth_tokens.expires_at
        FROM auth_tokens
        JOIN users ON users.id = auth_tokens.user_id
        WHERE auth_tokens.token=%s
    """, (token,))

    row = cursor.fetchone()
    if not row:
        return jsonify({"success": False, "error": "invalid"})

    user_id, username, expires_at_text = row
    expires_at = datetime.fromisoformat(expires_at_text)

    if datetime.now(timezone.utc) > expires_at:
        return jsonify({"success": False, "error": "expired"})

    session_id = str(uuid.uuid4())

    cursor.execute(
        "INSERT INTO sessions (user_id, session_id) VALUES (%s, %s)",
        (user_id, session_id)
    )

    conn.commit()

    return jsonify({"success": True, "username": username, "session": session_id})


# =============== API: GET USER BY SESSION ===============
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


# =============== BOT THREAD ===============
def run_bot():
    bot.remove_webhook()
    bot.infinity_polling(skip_pending=True)

threading.Thread(target=run_bot, daemon=True).start()


# =============== RUN FLASK ===============
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)



