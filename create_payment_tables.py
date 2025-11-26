#!/usr/bin/env python3
"""
Создание платежных таблиц вручную
"""
import sqlite3
from datetime import datetime

def create_payment_tables():
    """Создание всех платежных таблиц"""
    conn = sqlite3.connect('clinic.db')
    cursor = conn.cursor()
    
    print("🔧 Создаем платежные таблицы...")
    
    try:
        # 1. Таблица payment_providers
        print("   📋 Создаем payment_providers...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payment_providers (
                id INTEGER PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                code VARCHAR(50) NOT NULL UNIQUE,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                webhook_url VARCHAR(500),
                api_key VARCHAR(500),
                secret_key VARCHAR(500),
                commission_percent INTEGER NOT NULL DEFAULT 0,
                min_amount INTEGER NOT NULL DEFAULT 0,
                max_amount INTEGER NOT NULL DEFAULT 100000000,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 2. Таблица payment_webhooks
        print("   📋 Создаем payment_webhooks...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payment_webhooks (
                id INTEGER PRIMARY KEY,
                provider VARCHAR(50) NOT NULL,
                webhook_id VARCHAR(100) NOT NULL UNIQUE,
                transaction_id VARCHAR(100) NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                amount INTEGER NOT NULL,
                currency VARCHAR(3) NOT NULL DEFAULT 'UZS',
                raw_data TEXT NOT NULL,
                signature VARCHAR(500),
                visit_id INTEGER,
                patient_id INTEGER,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                processed_at DATETIME,
                error_message TEXT
            )
        """)
        
        # 3. Таблица payment_transactions
        print("   📋 Создаем payment_transactions...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payment_transactions (
                id INTEGER PRIMARY KEY,
                transaction_id VARCHAR(100) NOT NULL UNIQUE,
                provider VARCHAR(50) NOT NULL,
                amount INTEGER NOT NULL,
                currency VARCHAR(3) NOT NULL DEFAULT 'UZS',
                commission INTEGER NOT NULL DEFAULT 0,
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                webhook_id INTEGER,
                visit_id INTEGER,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 4. Обновляем таблицу payments (если нужно)
        print("   📋 Проверяем payments...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY,
                visit_id INTEGER,
                cashier_id INTEGER,
                amount DECIMAL(12,2) NOT NULL DEFAULT 0,
                currency VARCHAR(8) NOT NULL DEFAULT 'UZS',
                method VARCHAR(16) NOT NULL DEFAULT 'cash',
                status VARCHAR(16) NOT NULL DEFAULT 'paid',
                receipt_no VARCHAR(64),
                note VARCHAR(512),
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                
                -- Новые поля для онлайн платежей
                provider VARCHAR(50),
                provider_payment_id VARCHAR(100),
                payment_url TEXT,
                paid_at DATETIME
            )
        """)
        
        # Создаем индексы
        print("   🔍 Создаем индексы...")
        
        # Индексы для payment_providers
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_payment_providers_code ON payment_providers(code)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_payment_providers_is_active ON payment_providers(is_active)")
        
        # Индексы для payment_webhooks  
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_payment_webhooks_provider ON payment_webhooks(provider)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_payment_webhooks_transaction_id ON payment_webhooks(transaction_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_payment_webhooks_status ON payment_webhooks(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_payment_webhooks_visit_id ON payment_webhooks(visit_id)")
        
        # Индексы для payment_transactions
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_payment_transactions_provider ON payment_transactions(provider)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_payment_transactions_status ON payment_transactions(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_payment_transactions_visit_id ON payment_transactions(visit_id)")
        
        # Индексы для payments
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_payments_visit_id ON payments(visit_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_payments_status ON payments(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_payments_provider ON payments(provider)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_payments_provider_payment_id ON payments(provider_payment_id)")
        
        # Заполняем провайдеров
        print("   💳 Добавляем провайдеров...")
        
        providers = [
            ('Click', 'click', 1, 'https://api.click.uz/v2/merchant', 'test_api_key', 'test_secret', 2, 1000, 10000000),
            ('Payme', 'payme', 1, 'https://checkout.paycom.uz/api', 'test_merchant', 'test_secret', 2, 1000, 10000000),
            ('Kaspi Pay', 'kaspi', 1, 'https://kaspi.kz/pay/api', 'test_merchant', 'test_secret', 3, 100, 1000000)
        ]
        
        for provider in providers:
            cursor.execute("""
                INSERT OR IGNORE INTO payment_providers 
                (name, code, is_active, webhook_url, api_key, secret_key, commission_percent, min_amount, max_amount)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, provider)
        
        conn.commit()
        
        # Проверяем результат
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'payment%'")
        tables = [t[0] for t in cursor.fetchall()]
        
        cursor.execute("SELECT COUNT(*) FROM payment_providers")
        providers_count = cursor.fetchone()[0]
        
        print(f"\n✅ Создано {len(tables)} платежных таблиц:")
        for table in tables:
            print(f"   - {table}")
        
        print(f"✅ Добавлено {providers_count} провайдеров")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Ошибка создания таблиц: {e}")
        conn.rollback()
        conn.close()
        return False

if __name__ == "__main__":
    success = create_payment_tables()
    
    if success:
        print("\n🎉 ПЛАТЕЖНЫЕ ТАБЛИЦЫ СОЗДАНЫ!")
        print("Теперь можно тестировать платежную систему.")
    else:
        print("\n❌ ОШИБКА СОЗДАНИЯ ТАБЛИЦ")
        print("Проверьте логи и исправьте проблемы.")
