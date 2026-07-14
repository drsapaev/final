"""
Тест поиска пользователя в базе данных
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.app.db.session import engine
from sqlalchemy import text

def test_user_search():
    """Тестируем поиск пользователя"""
    print("🔍 Тестирование поиска пользователя...")

    try:
        with engine.connect() as conn:
            # Тестируем поиск по username
            result = conn.execute(text("""
                SELECT id, username, email, full_name, role, is_active, is_superuser
                FROM users
                WHERE username = :username
            """), {"username": "mcp_test"})

            user_row = result.fetchone()

            if user_row:
                user_id, username, email, full_name, role, is_active, is_superuser = user_row
                print(f"✅ Пользователь найден по username:")
                print(f"   ID: {user_id}")
                print(f"   Username: {username}")
                print(f"   Email: {email}")
                print(f"   Role: {role}")
                print(f"   Is Active: {is_active}")
                print(f"   Is Superuser: {is_superuser}")
            else:
                print("❌ Пользователь не найден по username")

            # Тестируем поиск по email
            result = conn.execute(text("""
                SELECT id, username, email, full_name, role, is_active, is_superuser
                FROM users
                WHERE email = :email
            """), {"email": "mcp_test@example.com"})

            user_row = result.fetchone()

            if user_row:
                user_id, username, email, full_name, role, is_active, is_superuser = user_row
                print(f"✅ Пользователь найден по email:")
                print(f"   ID: {user_id}")
                print(f"   Username: {username}")
                print(f"   Email: {email}")
                print(f"   Role: {role}")
                print(f"   Is Active: {is_active}")
                print(f"   Is Superuser: {is_superuser}")
            else:
                print("❌ Пользователь не найден по email")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_user_search()
