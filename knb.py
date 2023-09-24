import bcrypt
import psycopg2
import pyshorteners
from datetime import datetime, timedelta
import flake8
import pytest
import uvicorn
from fastapi import FastAPI, HTTPException
from starlette.responses import HTMLResponse
from starlette.requests import Request

# экземпляр FastAPI
app = FastAPI()

# Соединение с базой данных
def connect_to_database():
    host = "127.0.0.1"
    user = "postgres"
    password = "1234"
    db_name = "postgres"

    try:
        connection = psycopg2.connect(
            host=host,
            user=user,
            password=password,
            database=db_name
        )
        connection.autocommit = True
        return connection
    except Exception as ex:
        print(f"[INFO] {ex}")
        return None

connection = connect_to_database()

# Функция для создания таблицы
def create_url_table():
    with connection.cursor() as cursor:
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS url_project (
            id serial PRIMARY KEY,
            user_id INTEGER,
            original_url TEXT NOT NULL,
            short_url TEXT NOT NULL,
            expiration_date DATE,
            date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )"""
        )

        cursor.execute(
            """CREATE TABLE IF NOT EXISTS users (
            id serial PRIMARY KEY,
            username TEXT NOT NULL,
            password TEXT NOT NULL
            )"""
        )

# таблица при запуске приложения
create_url_table()

# Функция для регистрации пользователя
def register_user(username, password):
    try:
        with connection.cursor() as cursor:
            # Хеширование пароля
            hashed_password = hash_password(password)
            cursor.execute(
                "INSERT INTO users (username, password) VALUES (%s, %s)",
                (username, hashed_password)
            )
            print("Пользователь успешно зарегистрирован.")
    except Exception as ex:
        print(f"Ошибка при регистрации пользователя: {ex}")

# Функция для аутентификации пользователя
def login_user(username, password):
    try:
        with connection.cursor() as cursor:
            # хешированный пароль из базы данных для данного пользователя
            cursor.execute("SELECT id, password FROM users WHERE username = %s", (username,))
            user_record = cursor.fetchone()

            if user_record:
                stored_password = user_record[1]

                # хешированный пароль
                if check_password(password, stored_password):
                    return user_record[0]

            return None  # Неверное имя пользователя или пароль
    except Exception as ex:
        print(f"Ошибка при входе в систему: {ex}")

# Функция для хеширования пароля
def hash_password(password):
    # соль (salt)
    salt = bcrypt.gensalt()

    # пароль с использованием соли
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)

    return hashed_password.decode('utf-8')

# Функция для проверки пароля
def check_password(input_password, stored_password):
    # введенный пароль с хешем пароля из базы данных
    return bcrypt.checkpw(input_password.encode('utf-8'), stored_password.encode('utf-8'))
# Регистрация пользователя
@app.post("/register")
def register(username: str, password: str):
    register_user(username, password)
    return {"message": "Пользователь успешно зарегистрирован."}

# Аутентификация пользователя
@app.post("/login")
def user_login(username: str, password: str):
    user_id = login_user(username, password)
    if user_id is not None:
        return {"message": "Вход выполнен успешно.", "user_id": user_id}
    else:
        raise HTTPException(status_code=400, detail="Неправильное имя пользователя или пароль.")

# Функция для сокращения URL
def shorten_url(user_id, original_url, expiration_date):
    try:
        # короткая ссылку с использованием библиотеки pyshorteners
        shortener = pyshorteners.Shortener()
        short_url = shortener.tinyurl.short(original_url)

        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO url_project (user_id, original_url, short_url, expiration_date) VALUES (%s, %s, %s, %s)",
                (user_id, original_url, short_url, expiration_date)
            )

            return short_url
    except Exception as ex:
        print(f"Ошибка при сжатии URL: {ex}")
        return None

# Создание сжатой ссылки
@app.post("/shorten")
def create_short_url(user_id: int, original_url: str, expiration_date: datetime):
    short_url = shorten_url(user_id, original_url, expiration_date)
    if short_url:
        return {"short_url": short_url}
    else:
        raise HTTPException(status_code=500, detail="Не удалось создать сжатую ссылку.")

# Получение сжатой ссылки по ее ID
@app.get("/shorten/{url_id}")
def get_short_url(url_id: int):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT short_url FROM url_project WHERE id = %s", (url_id,))
            result = cursor.fetchone()
            if result:
                return {"short_url": result[0]}
            else:
                raise HTTPException(status_code=404, detail="Сжатая ссылка не найдена.")
    except Exception as ex:
        print(f"Ошибка при получении сжатой ссылки: {ex}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера.")

# Управление сжатыми ссылками, удаление
@app.delete("/shorten/{url_id}")
def delete_short_url(url_id=None):
    try:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM url_project WHERE id = %s", (url_id,))
        return {"message": "Сжатая ссылка успешно удалена."}
    except Exception as ex:
        print(f"Ошибка при удалении сжатой ссылки: {ex}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера.")

    # Запуск приложения


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=80)