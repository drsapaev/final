"""
Проверка пользователей в базе данных
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.app.db.session import engine
from sqlalchemy import text

def check_users():
    """Проверяем пользователей в базе данных"""
    print("🔍 Проверка пользователей в базе данных...")
    
    try:
        with engine.connect() as conn:
            # Получаем всех пользователей
            result = conn.execute(text("""
                SELECT id, username, email, role, is_active, is_superuser
                FROM users 
                ORDER BY id
            """))
            
            users = result.fetchall()
            
            if not users:
                print("❌ Пользователи не найдены в базе данных")
                return
            
            print(f"✅ Найдено пользователей: {len(users)}")
            print("\n📋 Список пользователей:")
            print("-" * 80)
            print(f"{'ID':<5} {'Username':<20} {'Email':<30} {'Role':<15} {'Active':<8} {'Superuser':<10}")
            print("-" * 80)
            
            for user in users:
                user_id, username, email, role, is_active, is_superuser = user
                print(f"{user_id:<5} {username:<20} {email or 'N/A':<30} {role or 'N/A':<15} {is_active:<8} {is_superuser:<10}")
            
            print("-" * 80)
            
            # Проверяем конкретных пользователей
            test_users = ['admin', 'registrar', 'doctor', 'cardio', 'derma', 'dentist']
            
            print("\n🔍 Проверка тестовых пользователей:")
            for test_user in test_users:
                result = conn.execute(text("""
                    SELECT id, username, email, role, is_active, hashed_password IS NOT NULL as has_password
                    FROM users 
                    WHERE username = :username
                """), {"username": test_user})
                
                user_row = result.fetchone()
                if user_row:
                    user_id, username, email, role, is_active, has_password = user_row
                    print(f"  ✅ {username}: ID={user_id}, Role={role}, Active={is_active}, HasPassword={has_password}")
                else:
                    print(f"  ❌ {test_user}: не найден")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_users()