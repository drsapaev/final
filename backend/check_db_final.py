#!/usr/bin/env python3
"""
Финальная проверка базы данных
"""
from app.db.session import get_db
from sqlalchemy import text

def check_database_final():
    """Финальная проверка базы данных"""
    print("🔍 ФИНАЛЬНАЯ ПРОВЕРКА БАЗЫ ДАННЫХ")
    print("=" * 40)
    
    try:
        db = next(get_db())
        
        # Проверяем количество пользователей
        result = db.execute(text("SELECT COUNT(*) FROM users"))
        count = result.scalar()
        print(f"👥 Пользователей в БД: {count}")
        
        # Проверяем admin пользователя
        result = db.execute(text("SELECT username, role FROM users WHERE username='admin'"))
        admin = result.fetchone()
        if admin:
            print(f"👤 Admin найден: {admin[0]} (роль: {admin[1]})")
        else:
            print("❌ Admin не найден")
        
        # Проверяем таблицы
        result = db.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='users'"))
        users_table = result.fetchone()
        if users_table:
            print("✅ Таблица users существует")
        else:
            print("❌ Таблица users не найдена")
        
        # Проверяем все таблицы
        result = db.execute(text("SELECT COUNT(*) FROM sqlite_master WHERE type='table'"))
        table_count = result.scalar()
        print(f"📋 Всего таблиц в БД: {table_count}")
        
    except Exception as e:
        print(f"❌ Ошибка проверки БД: {e}")

if __name__ == "__main__":
    check_database_final()
