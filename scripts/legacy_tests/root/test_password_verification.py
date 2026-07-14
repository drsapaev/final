"""
Тест функции verify_password
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.app.db.session import engine
from backend.app.core.security import verify_password
from sqlalchemy import text

def test_password_verification():
    """Тестируем функцию проверки пароля"""
    print("🔍 Тестирование функции verify_password...")

    try:
        with engine.connect() as conn:
            # Получаем пользователя mcp_test
            result = conn.execute(text("""
                SELECT id, username, email, hashed_password
                FROM users
                WHERE username = 'mcp_test'
            """))

            user_row = result.fetchone()

            if not user_row:
                print("❌ Пользователь mcp_test не найден")
                return

            user_id, username, email, hashed_password = user_row

            print(f"👤 Пользователь: {username} (ID: {user_id})")
            print(f"   Email: {email}")
            print("   Хеш пароля: <stored>")

            # Тестируем разные пароли
            test_passwords = [
                value
                for value in (
                    os.getenv("QA_MCP_PASSWORD"),
                    os.getenv("QA_ADMIN_PASSWORD"),
                )
                if value
            ]
            if not test_passwords:
                print("Set QA_MCP_PASSWORD or QA_ADMIN_PASSWORD before running this legacy password verification smoke script.")
                return

            for index, password in enumerate(test_passwords, start=1):
                try:
                    is_valid = verify_password(password, hashed_password)
                    print(f"   QA password #{index}: {'✅' if is_valid else '❌'}")
                except Exception as e:
                    print(f"   QA password #{index}: ❌ Ошибка: {e}")

            # Тестируем с пустым паролем
            try:
                is_valid = verify_password("", hashed_password)
                print(f"   Пустой пароль: {'✅' if is_valid else '❌'}")
            except Exception as e:
                print(f"   Пустой пароль: ❌ Ошибка: {e}")

            # Тестируем с None
            try:
                is_valid = verify_password(None, hashed_password)
                print(f"   None пароль: {'✅' if is_valid else '❌'}")
            except Exception as e:
                print(f"   None пароль: ❌ Ошибка: {e}")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_password_verification()
