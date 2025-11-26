#!/usr/bin/env python3
"""
Скрипт для исправления пароля пользователя admin
"""

import os
import sys
from pathlib import Path

# Добавляем путь к проекту
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, text
from app.core.config import settings
from passlib.context import CryptContext

# Создаем движок базы данных
engine = create_engine(settings.DATABASE_URL, echo=False)

# Создаем контекст для хеширования паролей (используем argon2 как в системе)
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

print("🔧 Исправление пароля пользователя admin...")

try:
    with engine.connect() as conn:
        # Обновляем пароль для admin
        new_password_hash = get_password_hash("admin123")
        
        result = conn.execute(text("""
            UPDATE users 
            SET hashed_password = :password_hash 
            WHERE username = 'admin'
        """), {"password_hash": new_password_hash})
        
        conn.commit()
        
        if result.rowcount > 0:
            print("✅ Пароль пользователя admin обновлен на 'admin123'")
        else:
            print("❌ Пользователь admin не найден")
            
        # Проверяем результат
        result = conn.execute(text("SELECT username, email, role FROM users WHERE username = 'admin'"))
        user = result.fetchone()
        
        if user:
            print(f"👤 Пользователь: {user[0]} ({user[1]}) - {user[2]}")
            
except Exception as e:
    print(f"❌ Ошибка при обновлении пароля: {e}")

print("\n🎉 Исправление завершено!")
