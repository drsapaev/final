"""
Тест подключения к базе данных из сервера
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.app.db.session import get_db
from sqlalchemy import text

def test_db_connection():
    """Тестируем подключение к базе данных"""
    print("🔍 Тестирование подключения к базе данных...")

    try:
        # Используем get_db как в сервере
        db_gen = get_db()
        db = next(db_gen)

        print("✅ Подключение к базе данных успешно")

        # Проверяем пользователя mcp_test
        result = db.execute(text("""
            SELECT id, username, email, full_name, role, is_active, is_superuser, hashed_password
            FROM users
            WHERE username = :username
        """), {"username": "mcp_test"})

        user_row = result.fetchone()

        if user_row:
            user_id, username, email, full_name, role, is_active, is_superuser, hashed_password = user_row
            print(f"✅ Пользователь mcp_test найден:")
            print(f"   ID: {user_id}")
            print(f"   Username: {username}")
            print(f"   Email: {email}")
            print(f"   Role: {role}")
            print(f"   Is Active: {is_active}")
            print(f"   Is Superuser: {is_superuser}")
            print(f"   Password Hash: {hashed_password[:50]}...")
        else:
            print("❌ Пользователь mcp_test НЕ найден!")

        # Закрываем соединение
        db.close()

    except Exception as e:
        print(f"❌ Ошибка подключения к базе данных: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_db_connection()
