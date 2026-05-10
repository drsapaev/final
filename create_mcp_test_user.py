"""
Создание тестового пользователя для MCP тестирования
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.app.db.session import engine
from backend.app.core.security import get_password_hash
from sqlalchemy import text

def create_test_user():
    """Создаем тестового пользователя с известным паролем"""
    print("🔧 Создание тестового пользователя для MCP...")
    
    password = os.getenv("QA_MCP_PASSWORD")
    if not password:
        print("Set QA_MCP_PASSWORD before running this legacy MCP test user helper.")
        return

    try:
        with engine.connect() as conn:
            # Проверяем, есть ли уже тестовый пользователь
            result = conn.execute(text("""
                SELECT id FROM users WHERE username = 'mcp_test'
            """))
            
            existing_user = result.fetchone()
            
            if existing_user:
                print("✅ Тестовый пользователь уже существует")
                # Обновляем пароль
                password_hash = get_password_hash(password)
                conn.execute(text("""
                    UPDATE users 
                    SET hashed_password = :password_hash, is_active = 1
                    WHERE username = 'mcp_test'
                """), {"password_hash": password_hash})
                conn.commit()
                print("✅ Пароль обновлен")
            else:
                # Создаем нового пользователя
                password_hash = get_password_hash(password)
                conn.execute(text("""
                    INSERT INTO users (username, email, full_name, role, is_active, is_superuser, hashed_password)
                    VALUES ('mcp_test', 'mcp_test@example.com', 'MCP Test User', 'Admin', 1, 1, :password_hash)
                """), {"password_hash": password_hash})
                conn.commit()
                print("✅ Тестовый пользователь создан")
            
            print("\n📋 Учетные данные для тестирования:")
            print("  Username: mcp_test")
            print("  Password: <QA_MCP_PASSWORD>")
            print("  Role: Admin")
            print("  Email: mcp_test@example.com")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    create_test_user()
