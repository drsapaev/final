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
        'admin@example.com': 'admin123',
        'doctor@example.com': 'doctor123', 
        'registrar@example.com': 'registrar123',
        'cardio@example.com': 'cardio123',
        'derma@example.com': 'derma123',
        'dentist@example.com': 'dentist123',
        'lab@example.com': 'lab123',
        'cashier@example.com': 'cashier123'
    }
    
    print("🔐 Создаем хеши паролей...")
    
    db = SessionLocal()
    try:
        for email, password in passwords.items():
            password_hash = get_password_hash(password)
            print(f"📧 {email}: {password} -> {password_hash[:30]}...")
            
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
            print(f"  - {user[0]}: {user[1][:30]}...")
            
    except Exception as e:
        print(f"❌ Ошибка при обновлении паролей: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("🔐 Обновление паролей пользователей...")
    update_passwords()

