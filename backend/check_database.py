#!/usr/bin/env python3
"""
Скрипт для проверки базы данных
"""

import os
import sys
from pathlib import Path

# Добавляем путь к проекту
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, text
from app.core.config import settings

# Создаем движок базы данных
engine = create_engine(settings.DATABASE_URL, echo=False)

print("🔍 Проверка базы данных...")
print(f"📁 DATABASE_URL: {settings.DATABASE_URL}")

try:
    with engine.connect() as conn:
        # Проверяем, существует ли таблица users
        result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='users'"))
        tables = result.fetchall()
        
        if tables:
            print("✅ Таблица 'users' существует")
            
            # Проверяем количество пользователей
            result = conn.execute(text("SELECT COUNT(*) FROM users"))
            count = result.fetchone()[0]
            print(f"👥 Количество пользователей: {count}")
            
            # Показываем пользователей
            result = conn.execute(text("SELECT username, email, role, is_active FROM users LIMIT 5"))
            users = result.fetchall()
            print("📋 Пользователи:")
            for user in users:
                print(f"  - {user[0]} ({user[1]}) - {user[2]} - {'активен' if user[3] else 'неактивен'}")
                
        else:
            print("❌ Таблица 'users' не существует")
            
        # Показываем все таблицы
        result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        all_tables = result.fetchall()
        print(f"\n📊 Всего таблиц в базе: {len(all_tables)}")
        print("📋 Список таблиц:")
        for table in all_tables:
            print(f"  - {table[0]}")
            
except Exception as e:
    print(f"❌ Ошибка при проверке базы данных: {e}")

print("\n🎉 Проверка завершена!")
