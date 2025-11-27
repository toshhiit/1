import telebot
import uuid
import psycopg2
from datetime import datetime, timedelta

# Токен бота
BOT_TOKEN = "7961739892:AAEzrVbw-5kRBFKvi-_jRvy4pxMBLTNA6DM"
bot = telebot.TeleBot(BOT_TOKEN)

# Подключение к базе PostgreSQL
conn = psycopg2.connect(
    host="localhost",
    database="mini_game_db",
    user="postgres",
    password="1234",
    port=5432
)
cursor = conn.cursor()


# Функция получения user_id из таблицы users
def get_user_id(tg_id):
    cursor.execute("SELECT id FROM users WHERE tg_id=%s", (tg_id,))
    result = cursor.fetchone()
    if result:
        return result[0]
    return None


# Функция генерации одноразового токена
def generate_token(user_id):
    token = str(uuid.uuid4())
    expires_at = datetime.now() + timedelta(minutes=10)

    cursor.execute(
        "INSERT INTO auth_tokens (user_id, token, expires_at) VALUES (%s, %s, %s)",
        (user_id, token, expires_at)
    )
    conn.commit()
    return token


# /start
@bot.message_handler(commands=['start'])
def start(message):
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

        # Создаём запись в stats
        cursor.execute(
            "INSERT INTO stats (user_id, xp, coins, level) VALUES (%s, 0, 0, 1)",
            (new_user_id,)
        )

        conn.commit()

    bot.send_message(
        message.chat.id,
        """Привет! Добро пожаловать в Library of Games [LOG]! Я LOG Bot.\n С помощью меня ты сможешь получить доступ к сайту с мини играми .
        \nНажми /games, чтобы играть в мини-игры.\n Чтобы узнать возможности бота, используй командe: /help
        """
    )

@bot.message_handler(commands=['help'])
def info(message):
    text = (
        "ℹ️ *Информация о командах LOG Bot*\n\n"
        "• /start — регистрация\n"
        "• /games — вход на сайт\n"
        "• /stats — твоя статистика\n"
        "• /achievements — ачивки\n"
        "• /top — топ игроков\n"
        "• /profile — твой профиль\n"
        "• /help — список команд\n"
        "• /info — информация о проекте \n"
    )

    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# /games — кнопка для входа на сайт
@bot.message_handler(commands=['games'])
def games(message):
    tg_id = message.from_user.id
    user_id = get_user_id(tg_id)

    if not user_id:
        bot.send_message(message.chat.id, "Ошибка: пользователь не найден.")
        return

    token = generate_token(user_id)

    # Пока домена нет — ставим локальную ссылку
    link = f"https://libraryofgames.netlify.app//login?token={token}"

    markup = telebot.types.InlineKeyboardMarkup()
    btn = telebot.types.InlineKeyboardButton("Играть в мини-игры 🎮", url=link)
    markup.add(btn)

    bot.send_message(message.chat.id, "Нажми кнопку, чтобы перейти на сайт:", reply_markup=markup)


# /stats — показать статистику
@bot.message_handler(commands=['stats'])
def stats(message):
    tg_id = message.from_user.id

    cursor.execute(
        "SELECT xp, coins, level FROM stats "
        "JOIN users ON stats.user_id = users.id "
        "WHERE users.tg_id=%s",
        (tg_id,)
    )

    stat = cursor.fetchone()

    if stat:
        xp, coins, level = stat
        bot.send_message(
            message.chat.id,
            f"📊 Твоя статистика:\n"
            f"Уровень: {level}\n"
            f"XP: {xp}\n"
            f"Монеты: {coins}"
        )
    else:
        bot.send_message(message.chat.id, "Статистика не найдена.")


# /achievements — показать ачивки
@bot.message_handler(commands=['achievements'])
def achievements(message):
    tg_id = message.from_user.id

    cursor.execute(
        "SELECT title, timestamp FROM achievements "
        "JOIN users ON achievements.user_id = users.id "
        "WHERE users.tg_id=%s",
        (tg_id,)
    )
    achs = cursor.fetchall()

    if achs:
        text = "🏆 Твои ачивки:\n"
        for title, ts in achs:
            text += f"{title} — {ts.strftime('%Y-%m-%d %H:%M')}\n"
        bot.send_message(message.chat.id, text)
    else:
        bot.send_message(message.chat.id, "У тебя пока нет ачивок 😢")


# /top — топ пользователей
@bot.message_handler(commands=['top'])
def top(message):
    cursor.execute(
        "SELECT u.username, s.xp, s.level FROM stats s "
        "JOIN users u ON s.user_id = u.id "
        "ORDER BY s.xp DESC "
        "LIMIT 10"
    )

    top_users = cursor.fetchall()

    if top_users:
        text = "🏅 Топ игроков по XP:\n"
        for i, (username, xp, level) in enumerate(top_users, start=1):
            text += f"{i}. {username} — Уровень {level}, XP: {xp}\n"
        bot.send_message(message.chat.id, text)
    else:
        bot.send_message(message.chat.id, "Нет данных для топа.")


bot.infinity_polling()
