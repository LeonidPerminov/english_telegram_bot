import telebot
import psycopg2
import random
import os

from telebot.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

# === НАСТРОЙКИ ===
TOKEN = os.getenv("TOKEN")
bot = telebot.TeleBot(TOKEN)

DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")

conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST)
cursor = conn.cursor()

user_answers = {}  # временное хранилище правильных ответов


# === Главное меню ===
def send_main_menu(chat_id, text="\ud83d\udccb Главное меню:"):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("\ud83c\udfae Играть"))
    markup.add(KeyboardButton("\u2795 Добавить слово"), KeyboardButton("\u2796 Удалить слово"))
    markup.add(KeyboardButton("\u2139\ufe0f Помощь"), KeyboardButton("\ud83d\udcc8 Статистика"))
    bot.send_message(chat_id, text, reply_markup=markup)


# === РЕГИСТРАЦИЯ ПОЛЬЗОВАТЕЛЯ ===
def register_user(message):
    telegram_id = message.from_user.id
    username = message.from_user.username
    cursor.execute("SELECT id FROM users WHERE telegram_id = %s", (telegram_id,))
    result = cursor.fetchone()
    if result is None:
        cursor.execute("INSERT INTO users (telegram_id, username) VALUES (%s, %s)", (telegram_id, username))
        conn.commit()


def get_user_db_id(telegram_id):
    cursor.execute("SELECT id FROM users WHERE telegram_id = %s", (telegram_id,))
    result = cursor.fetchone()
    return result[0] if result else None


@bot.message_handler(commands=['start'])
def start_handler(message):
    register_user(message)
    send_main_menu(message.chat.id, "\ud83d\udc4b Привет! Я помогу тебе выучить английские слова.\nВыбери действие:")


@bot.message_handler(commands=['help'])
def help_handler(message):
    help_text = (
        "\ud83d\udcd8 <b>Как использовать бота:</b>\n"
        "\ud83c\udfae <b>Играть</b> — бот покажет слово, ты выбираешь перевод.\n"
        "\u2795 <b>Добавить слово</b> — введи своё слово и перевод.\n"
        "\u2796 <b>Удалить слово</b> — удаляешь лишнее из своего списка.\n"
        "\ud83d\udd19 <b>Назад</b> — вернуться в главное меню.\n\n"
        "\ud83d\udca1 Советы:\n"
        "• Начни с 5–10 слов\n"
        "• Играй каждый день\n"
        "• Используй персональные слова!"
    )
    bot.send_message(message.chat.id, help_text, parse_mode="HTML")


@bot.message_handler(commands=['play'])
def play_game(message):
    user_id = message.from_user.id
    db_user_id = get_user_db_id(user_id)

    if db_user_id is None:
        bot.send_message(user_id, "\u26a0\ufe0f Ошибка: пользователь не найден. Попробуй сначала команду /start.")
        return

    cursor.execute("SELECT word_ru, word_en FROM words")
    common_words = cursor.fetchall()

    cursor.execute("SELECT word_ru, word_en FROM user_words WHERE user_id = %s", (db_user_id,))
    personal_words = cursor.fetchall()

    all_words = common_words + personal_words

    if len(all_words) < 4:
        bot.send_message(user_id, "\u2757 Недостаточно слов для игры. Добавь слова через \u2795 Добавить слово.")
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
    bot.send_message(user_id, f"\ud83e\udde0 Выбери перевод слова:\n\ud83d\udd39 {word_ru}", reply_markup=markup)


@bot.message_handler(commands=['add_word'])
def add_word_step1(message):
    msg = bot.send_message(message.chat.id, "\ud83d\udcdd Введи слово на русском:", reply_markup=ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, add_word_step2)


def add_word_step2(message):
    word_ru = message.text.strip()
    msg = bot.send_message(message.chat.id, "\u270f\ufe0f Теперь введи перевод на английском:")
    bot.register_next_step_handler(msg, add_word_save, word_ru)


def add_word_save(message, word_ru):
    word_en = message.text.strip()
    db_user_id = get_user_db_id(message.from_user.id)

    cursor.execute("INSERT INTO user_words (user_id, word_ru, word_en) VALUES (%s, %s, %s)", (db_user_id, word_ru, word_en))
    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM user_words WHERE user_id = %s", (db_user_id,))
    count = cursor.fetchone()[0]

    bot.send_message(message.chat.id, f"\u2705 Слово добавлено!\n\ud83d\udcda Теперь ты изучаешь {count} персональных слов.")
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("\ud83d\udd19 Назад"))
    bot.send_message(message.chat.id, "\ud83d\udd19 Вернуться в меню", reply_markup=markup)


@bot.message_handler(commands=['delete_word'])
def delete_word_handler(message):
    db_user_id = get_user_db_id(message.from_user.id)
    cursor.execute("SELECT word_ru FROM user_words WHERE user_id = %s", (db_user_id,))
    words = cursor.fetchall()

    if not words:
        bot.send_message(message.chat.id, "\u2757 У тебя нет персональных слов для удаления.")
        return

    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for w in words:
        markup.add(KeyboardButton(w[0]))

    msg = bot.send_message(message.chat.id, "\ud83d\uddd1\ufe0f Выбери слово для удаления:", reply_markup=markup)
    bot.register_next_step_handler(msg, delete_word_confirm)


def delete_word_confirm(message):
    word_ru = message.text.strip()
    db_user_id = get_user_db_id(message.from_user.id)

    cursor.execute("DELETE FROM user_words WHERE user_id = %s AND word_ru = %s", (db_user_id, word_ru))
    conn.commit()

    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("\ud83d\udd19 Назад"))
    bot.send_message(message.chat.id, f"\ud83d\uddd1\ufe0f Слово '{word_ru}' удалено.", reply_markup=markup)


# === Статистика ===
def show_stats(message):
    db_user_id = get_user_db_id(message.from_user.id)
    cursor.execute("SELECT correct_answers, wrong_answers FROM user_stats WHERE user_id = %s", (db_user_id,))
    result = cursor.fetchone()

    if result:
        correct, wrong = result
        total = correct + wrong
        accuracy = round(correct / total * 100, 1) if total else 0
        text = (
            f"\ud83d\udcca <b>Твоя статистика:</b>\n"
            f"\u2705 Правильных ответов: <b>{correct}</b>\n"
            f"\u274c Ошибок: <b>{wrong}</b>\n"
            f"\ud83c\udfaf Точность: <b>{accuracy}%</b>"
        )
    else:
        text = "\ud83d\udcca У тебя пока нет статистики. Сыграй хотя бы раз!"

    bot.send_message(message.chat.id, text, parse_mode="HTML")


# === Проверка ответа ===
@bot.message_handler(func=lambda message: True and message.from_user.id in user_answers)
def check_answer(message):
    user_id = message.from_user.id
    correct_en, word_ru = user_answers.pop(user_id)
    answer = message.text.strip()

    db_user_id = get_user_db_id(user_id)
    cursor.execute("SELECT * FROM user_stats WHERE user_id = %s", (db_user_id,))
    stats = cursor.fetchone()

    if stats is None:
        cursor.execute("INSERT INTO user_stats (user_id, correct_answers, wrong_answers) VALUES (%s, %s, %s)", (db_user_id, 0, 0))
        conn.commit()

    if answer == correct_en:
        bot.send_message(message.chat.id, f"\u2705 Верно! {word_ru} — это {correct_en} \ud83d\udc4d")
        cursor.execute("UPDATE user_stats SET correct_answers = correct_answers + 1 WHERE user_id = %s", (db_user_id,))
    else:
        bot.send_message(message.chat.id, f"\u274c Неверно. {word_ru} — это {correct_en} \ud83d\ude15")
        cursor.execute("UPDATE user_stats SET wrong_answers = wrong_answers + 1 WHERE user_id = %s", (db_user_id,))

    conn.commit()
    send_main_menu(message.chat.id, "\ud83d\udccb Что дальше?")


# === Обработка кнопок ===
@bot.message_handler(func=lambda message: True)
def handle_buttons(message):
    text = message.text

    if text == "\ud83c\udfae Играть":
        play_game(message)
    elif text == "\u2795 Добавить слово":
        add_word_step1(message)
    elif text == "\u2796 Удалить слово":
        delete_word_handler(message)
    elif text == "\u2139\ufe0f Помощь":
        help_handler(message)
    elif text == "\ud83d\udcc8 Статистика":
        show_stats(message)
    elif text == "\ud83d\udd19 Назад":
        send_main_menu(message.chat.id)
    else:
        bot.send_message(message.chat.id, "\u2753 Я не понял команду. Пожалуйста, выбери действие из меню.")


# === ЗАПУСК ===
if __name__ == '__main__':
    print("\u2705 Бот запущен")
    bot.polling(none_stop=True)
