#!/usr/bin/env python3
"""
Исправление названий таблиц
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from app.db.session import SessionLocal
from sqlalchemy import text

def fix_table_names():
    """Исправить названия таблиц"""
    db = SessionLocal()
    try:
        print("🔧 Исправляем названия таблиц...")
        
        # Переименовываем user_activity в user_activities
        try:
            db.execute(text("ALTER TABLE user_activity RENAME TO user_activities;"))
            print("✅ Переименована user_activity -> user_activities")
        except Exception as e:
            if "no such table" in str(e).lower():
                # Создаем таблицу user_activities с правильным названием
                db.execute(text("""
                    CREATE TABLE IF NOT EXISTS user_activities (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        activity_type VARCHAR(50) NOT NULL,
                        description TEXT,
                        ip_address VARCHAR(45),
                        user_agent TEXT,
                        extra_data TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (id)
                    );
                """))
                print("✅ Создана таблица user_activities")
            else:
                print(f"⚠️ Ошибка при переименовании user_activity: {e}")
        
        # Создаем недостающие таблицы для 2FA
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS two_factor_auth (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                totp_secret VARCHAR(32),
                totp_enabled BOOLEAN DEFAULT 0,
                backup_codes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            );
        """))
        print("✅ Создана таблица two_factor_auth")
        
        db.commit()
        print("\n✅ Исправления завершены!")
        
        # Проверяем все таблицы
        result = db.execute(text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"))
        tables = result.fetchall()
        
        print(f"\n📊 Все таблицы в БД:")
        for table in tables:
            print(f"  - {table[0]}")
            
    except Exception as e:
        print(f"❌ Ошибка при исправлении таблиц: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("🔧 Исправление названий таблиц...")
    fix_table_names()

