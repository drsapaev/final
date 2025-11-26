#!/usr/bin/env python3
"""
Пошаговое тестирование аутентификации
"""
import sys
sys.path.append('.')

from app.db.session import get_db
from app.models.user import User
from app.core.security import verify_password
from sqlalchemy.orm import Session
from sqlalchemy import or_

def test_auth_step_by_step():
    """Пошаговое тестирование аутентификации"""
    print("🔐 Пошаговое тестирование аутентификации...")
    
    # Получаем сессию базы данных
    db = next(get_db())
    
    try:
        # Шаг 1: Проверяем, что пользователь существует
        print("\n1️⃣ Поиск пользователя 'admin'...")
        user = db.query(User).filter(
            or_(User.username == "admin", User.email == "admin")
        ).first()
        
        if not user:
            print("   ❌ Пользователь 'admin' не найден")
            return False
        
        print(f"   ✅ Пользователь найден: ID={user.id}, Username={user.username}")
        print(f"   ✅ Email: {user.email}")
        print(f"   ✅ Is Active: {user.is_active}")
        print(f"   ✅ Password Hash: {user.hashed_password[:20]}...")
        
        # Шаг 2: Проверяем верификацию пароля
        print("\n2️⃣ Верификация пароля 'admin123'...")
        password = "admin123"
        stored_hash = user.hashed_password
        
        try:
            result = verify_password(password, stored_hash)
            print(f"   ✅ Результат верификации: {result}")
            
            if not result:
                print("   ❌ Пароль неверный")
                return False
                
        except Exception as e:
            print(f"   ❌ Ошибка верификации: {e}")
            return False
        
        # Шаг 3: Проверяем статус пользователя
        print("\n3️⃣ Проверка статуса пользователя...")
        if not user.is_active:
            print("   ❌ Пользователь неактивен")
            return False
        
        print("   ✅ Пользователь активен")
        
        # Шаг 4: Имитируем полную аутентификацию
        print("\n4️⃣ Имитация полной аутентификации...")
        
        # Проверяем все условия
        if user and user.is_active and verify_password(password, stored_hash):
            print("   ✅ Все проверки пройдены успешно!")
            print("   ✅ Аутентификация должна работать")
            return True
        else:
            print("   ❌ Одна из проверок не пройдена")
            return False
            
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = test_auth_step_by_step()
    
    if success:
        print("\n🎉 Аутентификация должна работать!")
        print("   Проблема может быть в сервисе аутентификации")
    else:
        print("\n❌ Проблема найдена в базовых проверках")

