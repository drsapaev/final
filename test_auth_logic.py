"""
Тест логики авторизации
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.app.db.session import get_db
from backend.app.core.security import verify_password
from sqlalchemy import text

def test_auth_logic():
    """Тестируем логику авторизации"""
    print("🔍 Тестирование логики авторизации...")
    
    username = "mcp_test"
    password = "test123"
    
    try:
        # Используем get_db как в сервере
        db_gen = get_db()
        db = next(db_gen)
        
        print(f"🔍 Поиск пользователя: {username}")
        
        # Используем точно такой же SQL запрос как в сервере
        result = db.execute(text("""
            SELECT id, username, email, full_name, role, is_active, is_superuser, hashed_password
            FROM users 
            WHERE username = :username OR email = :username
        """), {"username": username})
        
        user_row = result.fetchone()
        
        if not user_row:
            print(f"❌ Пользователь не найден для username={username}")
            return False
        
        user_id, db_username, email, full_name, role, is_active, is_superuser, hashed_password = user_row
        
        print(f"✅ Пользователь найден: ID={user_id}, Username={db_username}, IsActive={is_active}")
        
        if not is_active:
            print(f"❌ Пользователь деактивирован")
            return False
        
        print(f"🔍 Проверка пароля...")
        password_valid = verify_password(password, hashed_password)
        print(f"✅ Результат проверки пароля: {password_valid}")
        
        if not password_valid:
            print(f"❌ Неверный пароль")
            return False
        
        print(f"✅ Авторизация успешна!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка в логике авторизации: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        try:
            db.close()
        except:
            pass

if __name__ == "__main__":
    success = test_auth_logic()
    if success:
        print(f"\n🎉 Логика авторизации работает правильно!")
    else:
        print(f"\n❌ Логика авторизации не работает!")
