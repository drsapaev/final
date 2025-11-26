"""
Проверка паролей пользователей
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.app.db.session import engine
from backend.app.core.security import verify_password, get_password_hash
from sqlalchemy import text

def check_passwords():
    """Проверяем пароли пользователей"""
    print("🔍 Проверка паролей пользователей...")
    
    test_passwords = ["admin", "test123", "registrar", "doctor"]
    
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id, username, email, hashed_password
                FROM users 
                WHERE username IN ('admin', 'mcp_test', 'registrar')
            """))
            
            users = result.fetchall()
            
            for user_id, username, email, hashed_password in users:
                print(f"\n👤 Пользователь: {username} (ID: {user_id})")
                print(f"   Email: {email}")
                print(f"   Хеш пароля: {hashed_password[:50]}...")
                
                for test_password in test_passwords:
                    is_valid = verify_password(test_password, hashed_password)
                    print(f"   Пароль '{test_password}': {'✅' if is_valid else '❌'}")
                
                # Попробуем создать новый хеш для тестирования
                new_hash = get_password_hash("test123")
                print(f"   Новый хеш для 'test123': {new_hash[:50]}...")
                
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_passwords()