CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username TEXT
);

-- Таблица общих слов (доступна всем пользователям)
CREATE TABLE IF NOT EXISTS words (
    id SERIAL PRIMARY KEY,
    word_ru TEXT NOT NULL,
    word_en TEXT NOT NULL
);

-- Таблица персональных слов для каждого пользователя
CREATE TABLE IF NOT EXISTS user_words (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    word_ru TEXT NOT NULL,
    word_en TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);