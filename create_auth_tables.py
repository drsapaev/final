#!/usr/bin/env python3
"""
Создание таблиц для системы аутентификации
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from app.db.session import SessionLocal
from sqlalchemy import text

def create_auth_tables():
    """Создать таблицы для системы аутентификации"""
    db = SessionLocal()
    try:
        print("🔧 Создаем таблицы для системы аутентификации...")
        
        # Создаем таблицу login_attempts
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS login_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username VARCHAR(100),
                email VARCHAR(100),
                ip_address VARCHAR(45),
                user_agent TEXT,
                success BOOLEAN NOT NULL DEFAULT 0,
                failure_reason VARCHAR(100),
                attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            );
        """))
        print("✅ Создана таблица login_attempts")
        
        # Создаем таблицу user_sessions
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS user_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_token VARCHAR(255) NOT NULL,
                refresh_token VARCHAR(255) NOT NULL,
                ip_address VARCHAR(45),
                user_agent TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                revoked BOOLEAN DEFAULT 0,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            );
        """))
        print("✅ Создана таблица user_sessions")
        
        # Создаем таблицу refresh_tokens
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash VARCHAR(255) NOT NULL,
                jti VARCHAR(36) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                revoked BOOLEAN DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users (id)
            );
        """))
        print("✅ Создана таблица refresh_tokens")
        
        # Создаем таблицу user_activity
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS user_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                activity_type VARCHAR(50) NOT NULL,
                description TEXT,
                ip_address VARCHAR(45),
                user_agent TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            );
        """))
        print("✅ Создана таблица user_activity")
        
        # Создаем таблицу security_events
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS security_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                event_type VARCHAR(50) NOT NULL,
                description TEXT,
                severity VARCHAR(20) DEFAULT 'medium',
                ip_address VARCHAR(45),
                user_agent TEXT,
                resolved BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            );
        """))
        print("✅ Создана таблица security_events")
        
        # Создаем таблицу password_reset_tokens
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                used BOOLEAN DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users (id)
            );
        """))
        print("✅ Создана таблица password_reset_tokens")
        
        # Создаем таблицу email_verification_tokens
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS email_verification_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash VARCHAR(255) NOT NULL,
                email VARCHAR(100) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                used BOOLEAN DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users (id)
            );
        """))
        print("✅ Создана таблица email_verification_tokens")
        
        db.commit()
        print("\n✅ Все таблицы аутентификации созданы успешно!")
        
        # Проверяем созданные таблицы
        result = db.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%login%' OR name LIKE '%session%' OR name LIKE '%token%' OR name LIKE '%activity%' OR name LIKE '%security%';"))
        tables = result.fetchall()
        
        print(f"\n📊 Созданные таблицы аутентификации:")
        for table in tables:
            print(f"  - {table[0]}")
            
    except Exception as e:
        print(f"❌ Ошибка при создании таблиц: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("🔧 Создание таблиц системы аутентификации...")
    create_auth_tables()

