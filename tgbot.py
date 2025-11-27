import telebot
import uuid
import psycopg2
import os
from datetime import datetime, timedelta
from urllib.parse import urlparse

# =============================
#  CONFIG ДЛЯ RAILWAY
# =============================

BOT_TOKEN = os.getenv("BOT_TOKEN")  # token TG bot
SITE_URL = os.getenv("SITE_URL", "https://libraryofgames.netlify.app")

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL не найден! Добавь его в Railway → Variables")

# Railway → postgres://...
url = urlparse(DATABASE_URL)

conn = psycopg2.connect(
    dbname=url.path[1:],
    user=url.username,
    password=url.password,
    host=url.hostname,
    port=url.port
)
cursor = conn.cursor()

bot = telebot.TeleBot(BOT_TOKEN)


# =============================
#  FUNCTIONS
# =============================
def get_user_id(tg_id):
    cursor.execute("SELECT id FROM users WHERE tg_id=%s", (tg_id,))
    r = cursor.fetchone()
    return r[0] if r else None


def generate_token(user_id):
    token = str(uuid.uuid4())
    expires_at = datetime.utcnow() + timedelta(minutes=10)

    cursor.execute(
        "INSERT INTO auth_tokens (user_id, token, expires_at) VALUES (%s, %s, %s)",
        (user_id, token, expires_at)
    )
    conn.commit()
    return token


# =============================
#  BOT COMMANDS
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


bot.infinity_polling()


