#!/usr/bin/env python3
"""
Скрипт для диагностики проблем с тестами ролей.
Симулирует то, что делает CI при создании пользователей.
"""

import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, '.')

# Устанавливаем переменные окружения как в CI
os.environ['DATABASE_URL'] = 'sqlite:///./test_ci_db.db'
os.environ['CORS_DISABLE'] = '1'
os.environ['WS_DEV_ALLOW'] = '1'

from app.db.base import Base
from app.db.session import engine, SessionLocal
from app.models.user import User
from app.core.security import get_password_hash, verify_password

# Create tables
print("Creating tables...")
Base.metadata.create_all(bind=engine)

db = SessionLocal()

try:
    # Создаем пользователей как в CI
    print("\nСоздание пользователей...")
    
    users_data = [
        ("admin", "admin123", "Admin"),
        ("registrar", "registrar123", "Registrar"),
        ("doctor", "doctor123", "Doctor"),
        ("cashier", "cashier123", "Cashier"),
        ("lab", "lab123", "Lab"),
        ("cardio", "cardio123", "cardio"),
        ("derma", "derma123", "derma"),
        ("dentist", "dentist123", "dentist"),
    ]
    
    for username, password, role in users_data:
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            print(f"  - {username}: уже существует")
            continue
            
        hashed = get_password_hash(password)
        user = User(
            username=username,
            full_name=username.title(),
            role=role,
            hashed_password=hashed,
            is_active=True
        )
        db.add(user)
        print(f"  - {username}: создан с ролью '{role}'")
    
    db.commit()
    print("\n✅ Пользователи созданы!")
    
    # Теперь проверяем, что можем верифицировать пароли
    print("\nПроверка верификации паролей:")
    for username, password, role in users_data:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            print(f"  ❌ {username}: не найден в БД!")
            continue
        
        # Проверяем пароль
        is_valid = verify_password(password, user.hashed_password)
        if is_valid:
            print(f"  ✅ {username}: пароль верифицирован, роль = '{user.role}'")
        else:
            print(f"  ❌ {username}: пароль НЕ ВЕРИФИЦИРОВАН!")
            print(f"      Ожидаемый пароль: {password}")
            print(f"      Хеш в БД: {user.hashed_password[:50]}...")

except Exception as e:
    print(f"\n❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
    db.rollback()
finally:
    db.close()
    
# Удаляем тестовую БД
import os
if os.path.exists('test_ci_db.db'):
    os.remove('test_ci_db.db')
    print("\n🗑️ Тестовая БД удалена")
