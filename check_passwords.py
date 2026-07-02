"""
Проверка паролей пользователей
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.app.db.session import engine
from backend.app.core.security import verify_password
from sqlalchemy import text

def check_passwords():
    """Проверяем пароли пользователей"""
    print("🔍 Проверка паролей пользователей...")
    
    test_passwords = [
        value
        for value in (
            os.getenv("QA_ADMIN_PASSWORD"),
            os.getenv("QA_MCP_PASSWORD"),
            os.getenv("QA_REGISTRAR_PASSWORD"),
            os.getenv("QA_DOCTOR_PASSWORD"),
        )
        if value
    ]
    if not test_passwords:
        print("Set QA_ADMIN_PASSWORD, QA_MCP_PASSWORD, QA_REGISTRAR_PASSWORD, or QA_DOCTOR_PASSWORD before running this legacy password check.")
        return
    
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
                print("   Хеш пароля: <stored>")
                
                for index, test_password in enumerate(test_passwords, start=1):
                    is_valid = verify_password(test_password, hashed_password)
                    print(f"   QA password #{index}: {'✅' if is_valid else '❌'}")
                
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_passwords()
