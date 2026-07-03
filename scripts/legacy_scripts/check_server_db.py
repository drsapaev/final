"""
Проверка пользователей в базе данных сервера
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.app.db.session import engine, DATABASE_URL
from sqlalchemy import text

def check_server_db():
    """Проверяем пользователей в базе данных сервера"""
    print(f"🔍 Проверка базы данных сервера: {DATABASE_URL}")
    
    try:
        with engine.connect() as conn:
            # Проверяем всех пользователей
            result = conn.execute(text("""
                SELECT id, username, email, full_name, role, is_active, is_superuser
                FROM users 
                ORDER BY id
            """))
            
            users = result.fetchall()
            
            print(f"📋 Найдено пользователей: {len(users)}")
            print("-" * 80)
            print(f"{'ID':<5} {'Username':<20} {'Email':<30} {'Role':<15} {'Active':<7}")
            print("-" * 80)
            
            for user in users:
                user_id, username, email, full_name, role, is_active, is_superuser = user
                print(f"{user_id:<5} {username:<20} {email:<30} {role:<15} {is_active:<7}")
            
            print("-" * 80)
            
            # Проверяем конкретно mcp_test
            result = conn.execute(text("""
                SELECT id, username, email, full_name, role, is_active, is_superuser, hashed_password
                FROM users 
                WHERE username = 'mcp_test'
            """))
            
            user_row = result.fetchone()
            
            if user_row:
                user_id, username, email, full_name, role, is_active, is_superuser, hashed_password = user_row
                print(f"\n✅ Пользователь mcp_test найден:")
                print(f"   ID: {user_id}")
                print(f"   Username: {username}")
                print(f"   Email: {email}")
                print(f"   Role: {role}")
                print(f"   Is Active: {is_active}")
                print(f"   Is Superuser: {is_superuser}")
                print(f"   Password Hash: {hashed_password[:50]}...")
            else:
                print(f"\n❌ Пользователь mcp_test НЕ найден!")
                
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_server_db()
