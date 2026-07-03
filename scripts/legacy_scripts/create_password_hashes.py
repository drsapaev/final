#!/usr/bin/env python3
"""
Создание правильных хешей паролей
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from app.core.security import get_password_hash
from app.db.session import SessionLocal
from sqlalchemy import text

def update_passwords():
    """Обновить пароли пользователей"""
    
    # Создаем хеши для паролей
    passwords = {
        'admin@example.com': os.getenv('QA_ADMIN_PASSWORD'),
        'doctor@example.com': os.getenv('QA_DOCTOR_PASSWORD'),
        'registrar@example.com': os.getenv('QA_REGISTRAR_PASSWORD'),
        'cardio@example.com': os.getenv('QA_CARDIO_PASSWORD'),
        'derma@example.com': os.getenv('QA_DERMA_PASSWORD'),
        'dentist@example.com': os.getenv('QA_DENTIST_PASSWORD'),
        'lab@example.com': os.getenv('QA_LAB_PASSWORD'),
        'cashier@example.com': os.getenv('QA_CASHIER_PASSWORD')
    }
    missing = [email for email, env_password in passwords.items() if not env_password]
    if missing:
        print("Set role-specific QA_*_PASSWORD environment variables before running this legacy password update helper.")
        print(f"Missing env values for {len(missing)} account(s).")
        return
    
    print("🔐 Создаем хеши паролей...")
    
    db = SessionLocal()
    try:
        for email, env_password in passwords.items():
            password_hash = get_password_hash(env_password)
            
            # Обновляем пароль в БД
            db.execute(text("UPDATE users SET hashed_password = :hash WHERE email = :email"), {
                "hash": password_hash,
                "email": email
            })
        
        db.commit()
        print("✅ Пароли обновлены!")
        
        # Проверяем результат
        result = db.execute(text("SELECT email, hashed_password FROM users;"))
        users = result.fetchall()
        print("\n👥 Пользователи с обновленными паролями:")
        for user in users:
            print(f"  - {user[0]}: stored hash present")
            
    except Exception as e:
        print(f"❌ Ошибка при обновлении паролей: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("🔐 Обновление паролей пользователей...")
    update_passwords()

