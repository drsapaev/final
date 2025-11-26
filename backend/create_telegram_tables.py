#!/usr/bin/env python3
"""
Создание таблиц для Telegram интеграции
"""
import sqlite3
import os

def create_telegram_tables():
    """Создание таблиц для Telegram"""
    print("🔧 Создание таблиц для Telegram интеграции...")
    
    # Путь к базе данных
    db_path = "clinic.db"
    
    if not os.path.exists(db_path):
        print(f"❌ База данных {db_path} не найдена!")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Создаем таблицу telegram_configs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS telegram_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_token VARCHAR(255),
                webhook_url VARCHAR(500),
                webhook_secret VARCHAR(255),
                bot_username VARCHAR(100),
                bot_name VARCHAR(100),
                admin_chat_ids JSON,
                notifications_enabled BOOLEAN DEFAULT 1,
                appointment_reminders BOOLEAN DEFAULT 1,
                lab_results_notifications BOOLEAN DEFAULT 1,
                payment_notifications BOOLEAN DEFAULT 1,
                default_language VARCHAR(10) DEFAULT 'ru',
                supported_languages JSON,
                active BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Создаем таблицу telegram_users
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS telegram_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username VARCHAR(100),
                first_name VARCHAR(100),
                last_name VARCHAR(100),
                language_code VARCHAR(10) DEFAULT 'ru',
                is_bot BOOLEAN DEFAULT 0,
                is_active BOOLEAN DEFAULT 1,
                notifications_enabled BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Создаем таблицу telegram_messages
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS telegram_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_user_id INTEGER NOT NULL,
                message_type VARCHAR(50) NOT NULL,
                message_text TEXT,
                message_data JSON,
                sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                status VARCHAR(20) DEFAULT 'sent',
                error_message TEXT
            )
        """)
        
        # Создаем индексы
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_telegram_configs_active ON telegram_configs(active)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_telegram_users_telegram_id ON telegram_users(telegram_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_telegram_users_active ON telegram_users(is_active)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_telegram_messages_user_id ON telegram_messages(telegram_user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_telegram_messages_type ON telegram_messages(message_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_telegram_messages_status ON telegram_messages(status)")
        
        # Вставляем дефолтную конфигурацию
        cursor.execute("""
            INSERT OR IGNORE INTO telegram_configs (
                id, bot_token, bot_username, bot_name, 
                admin_chat_ids, supported_languages, active
            ) VALUES (
                1, 'test_token', 'test_bot', 'Test Bot',
                '[]', '["ru", "en"]', 1
            )
        """)
        
        conn.commit()
        print("✅ Таблицы Telegram созданы успешно!")
        
        # Проверяем созданные таблицы
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'telegram_%'")
        tables = cursor.fetchall()
        print(f"📋 Созданные таблицы: {[table[0] for table in tables]}")
        
    except Exception as e:
        print(f"❌ Ошибка создания таблиц: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    create_telegram_tables()
