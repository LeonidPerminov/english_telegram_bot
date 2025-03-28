import telebot
import psycopg2
import random
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

# === НАСТРОЙКИ ===
TOKEN = "7039489599:AAG7xh2vM2JE3L-m5lGB8qorUTTv8lSwkh8"
bot = telebot.TeleBot(TOKEN)

DB_NAME = "english_bot"
DB_USER = "postgres"
DB_PASSWORD = "1234"
DB_HOST = "localhost"

conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST)
cursor = conn.cursor()

user_answers = {}  # временное хранилище правильных ответов


# === РЕГИСТРАЦИЯ ПОЛЬЗОВАТЕЛЯ ===
def register_user(message):
    telegram_id = message.from_user.id
    username = message.from_user.username
    print(f"[register_user] Проверка пользователя {telegram_id} ({username})")

    cursor.execute("SELECT id FROM users WHERE telegram_id = %s", (telegram_id,))
    result = cursor.fetchone()
    if result is None:
        print("[register_user] Пользователь не найден в БД. Добавляем.")
        cursor.execute("INSERT INTO users (telegram_id, username) VALUES (%s, %s)", (telegram_id, username))
        conn.commit()
    else:
        print(f"[register_user] Пользователь уже существует с id = {result[0]}")


def get_user_db_id(telegram_id):
    cursor.execute("SELECT id FROM users WHERE telegram_id = %s", (telegram_id,))
    result = cursor.fetchone()
    print(f"[get_user_db_id] Результат запроса: {result}")
    return result[0] if result else None


@bot.message_handler(commands=['start'])
def start_handler(message):
    print("[start_handler] Старт команды /start")
    register_user(message)
    bot.send_message(message.chat.id, "👋 Привет! Я помогу тебе выучить английские слова.\nНапиши /play чтобы начать игру.")


@bot.message_handler(commands=['play'])
def play_game(message):
    print("[play_game] Старт команды /play")
    user_id = message.from_user.id
    db_user_id = get_user_db_id(user_id)
    print(f"[play_game] db_user_id = {db_user_id}")

    if db_user_id is None:
        bot.send_message(user_id, "⚠️ Ошибка: пользователь не найден. Попробуй сначала команду /start.")
        return

    cursor.execute("SELECT word_ru, word_en FROM words")
    common_words = cursor.fetchall()
    print(f"[play_game] Загружено общих слов: {len(common_words)}")

    cursor.execute("SELECT word_ru, word_en FROM user_words WHERE user_id = %s", (db_user_id,))
    personal_words = cursor.fetchall()
    print(f"[play_game] Загружено персональных слов: {len(personal_words)}")

    all_words = common_words + personal_words

    if len(all_words) < 4:
        bot.send_message(user_id, "❗ Недостаточно слов для игры. Добавь слова через /add_word")
        return

    correct = random.choice(all_words)
    word_ru = correct[0]
    correct_en = correct[1]

    wrong_options = random.sample([w[1] for w in all_words if w[1] != correct_en], 3)
    options = wrong_options + [correct_en]
    random.shuffle(options)

    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for opt in options:
        markup.add(KeyboardButton(opt))

    user_answers[user_id] = (correct_en, word_ru)
    bot.send_message(user_id, f"🧠 Выбери перевод слова:\n🔹 {word_ru}", reply_markup=markup)
@bot.message_handler(commands=['add_word'])
def add_word_step1(message):
    msg = bot.send_message(message.chat.id, "📝 Введи слово на русском:")
    bot.register_next_step_handler(msg, add_word_step2)

def add_word_step2(message):
    word_ru = message.text.strip()
    msg = bot.send_message(message.chat.id, "✏️ Теперь введи перевод на английском:")
    bot.register_next_step_handler(msg, add_word_save, word_ru)

def add_word_save(message, word_ru):
    word_en = message.text.strip()
    db_user_id = get_user_db_id(message.from_user.id)

    cursor.execute("INSERT INTO user_words (user_id, word_ru, word_en) VALUES (%s, %s, %s)", (db_user_id, word_ru, word_en))
    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM user_words WHERE user_id = %s", (db_user_id,))
    count = cursor.fetchone()[0]

    bot.send_message(message.chat.id, f"✅ Слово добавлено!\n📚 Теперь ты изучаешь {count} персональных слов.")
@bot.message_handler(commands=['delete_word'])
def delete_word_handler(message):
    db_user_id = get_user_db_id(message.from_user.id)
    cursor.execute("SELECT word_ru FROM user_words WHERE user_id = %s", (db_user_id,))
    words = cursor.fetchall()

    if not words:
        bot.send_message(message.chat.id, "❗ У тебя нет персональных слов для удаления.")
        return

    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for w in words:
        markup.add(KeyboardButton(w[0]))

    msg = bot.send_message(message.chat.id, "🗑️ Выбери слово для удаления:", reply_markup=markup)
    bot.register_next_step_handler(msg, delete_word_confirm)

def delete_word_confirm(message):
    word_ru = message.text.strip()
    db_user_id = get_user_db_id(message.from_user.id)

    cursor.execute("DELETE FROM user_words WHERE user_id = %s AND word_ru = %s", (db_user_id, word_ru))
    conn.commit()

    bot.send_message(message.chat.id, f"🗑️ Слово '{word_ru}' удалено.", reply_markup=ReplyKeyboardRemove())

# === ЗАПУСК ===
if __name__ == '__main__':
    print("✅ Бот запущен")
    bot.polling(none_stop=True)