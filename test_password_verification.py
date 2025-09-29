#!/usr/bin/env python3
"""
Тест верификации паролей
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from app.core.security import verify_password, get_password_hash
from app.db.session import SessionLocal
from sqlalchemy import text

def test_password_verification():
    """Тест верификации паролей"""
    
    # Тестируем создание и верификацию хеша
    test_password = "admin123"
    hash1 = get_password_hash(test_password)
    hash2 = get_password_hash(test_password)
    
    print(f"🔐 Тестирование хеширования паролей:")
    print(f"Пароль: {test_password}")
    print(f"Хеш 1: {hash1[:50]}...")
    print(f"Хеш 2: {hash2[:50]}...")
    print(f"Хеши разные (это нормально): {hash1 != hash2}")
    
    # Тестируем верификацию
    verify1 = verify_password(test_password, hash1)
    verify2 = verify_password(test_password, hash2)
    verify_wrong = verify_password("wrong_password", hash1)
    
    print(f"\n✅ Верификация:")
    print(f"Правильный пароль с хешем 1: {verify1}")
    print(f"Правильный пароль с хешем 2: {verify2}")
    print(f"Неправильный пароль: {verify_wrong}")
    
    # Проверяем пароль admin из БД
    db = SessionLocal()
    try:
        result = db.execute(text("SELECT email, hashed_password FROM users WHERE email = 'admin@example.com';"))
        user_data = result.fetchone()
        
        if user_data:
            email, stored_hash = user_data
            print(f"\n👤 Проверка пароля admin из БД:")
            print(f"Email: {email}")
            print(f"Stored hash: {stored_hash[:50]}...")
            
            # Проверяем разные варианты паролей
            passwords_to_test = ["admin123", "admin", "123", "Admin123", "ADMIN123"]
            
            for pwd in passwords_to_test:
                is_valid = verify_password(pwd, stored_hash)
                print(f"Пароль '{pwd}': {'✅' if is_valid else '❌'}")
                
        else:
            print("❌ Пользователь admin@example.com не найден в БД")
            
    except Exception as e:
        print(f"❌ Ошибка при проверке БД: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    print("🧪 Тестирование верификации паролей...")
    test_password_verification()

