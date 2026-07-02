#!/usr/bin/env python3
"""
Создание таблиц для системы webhook'ов
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from app.core.config import settings
from app.models.webhook import Webhook, WebhookCall, WebhookEvent

def create_webhook_tables():
    """Создает таблицы для webhook'ов"""
    engine = create_engine(settings.DATABASE_URL)
    
    # SQL для создания таблиц
    create_webhooks_table = """
    CREATE TABLE IF NOT EXISTS webhooks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        uuid VARCHAR(36) UNIQUE NOT NULL,
        name VARCHAR(255) NOT NULL,
        description TEXT,
        url VARCHAR(500) NOT NULL,
        events JSON NOT NULL,
        headers JSON DEFAULT '{}',
        secret VARCHAR(255),
        max_retries INTEGER DEFAULT 3,
        retry_delay INTEGER DEFAULT 60,
        timeout INTEGER DEFAULT 30,
        filters JSON DEFAULT '{}',
        status VARCHAR(20) DEFAULT 'active',
        is_active BOOLEAN DEFAULT 1,
        total_calls INTEGER DEFAULT 0,
        successful_calls INTEGER DEFAULT 0,
        failed_calls INTEGER DEFAULT 0,
        last_call_at DATETIME,
        last_success_at DATETIME,
        last_failure_at DATETIME,
        created_by INTEGER,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME,
        FOREIGN KEY (created_by) REFERENCES users (id)
    );
    """
    
    create_webhook_calls_table = """
    CREATE TABLE IF NOT EXISTS webhook_calls (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        uuid VARCHAR(36) UNIQUE NOT NULL,
        webhook_id INTEGER NOT NULL,
        event_type VARCHAR(50) NOT NULL,
        event_data JSON NOT NULL,
        url VARCHAR(500) NOT NULL,
        method VARCHAR(10) DEFAULT 'POST',
        headers JSON DEFAULT '{}',
        payload JSON NOT NULL,
        status VARCHAR(20) DEFAULT 'pending',
        response_status_code INTEGER,
        response_headers JSON DEFAULT '{}',
        response_body TEXT,
        error_message TEXT,
        attempt_number INTEGER DEFAULT 1,
        max_attempts INTEGER DEFAULT 3,
        next_retry_at DATETIME,
        duration_ms INTEGER,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME,
        completed_at DATETIME,
        FOREIGN KEY (webhook_id) REFERENCES webhooks (id) ON DELETE CASCADE
    );
    """
    
    create_webhook_events_table = """
    CREATE TABLE IF NOT EXISTS webhook_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        uuid VARCHAR(36) UNIQUE NOT NULL,
        event_type VARCHAR(50) NOT NULL,
        event_data JSON NOT NULL,
        source VARCHAR(100),
        source_id VARCHAR(100),
        correlation_id VARCHAR(100),
        processed BOOLEAN DEFAULT 0,
        processed_at DATETIME,
        failed_webhooks JSON DEFAULT '[]',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """
    
    # Индексы для производительности
    create_indexes = [
        "CREATE INDEX IF NOT EXISTS idx_webhooks_uuid ON webhooks(uuid);",
        "CREATE INDEX IF NOT EXISTS idx_webhooks_status ON webhooks(status);",
        "CREATE INDEX IF NOT EXISTS idx_webhooks_is_active ON webhooks(is_active);",
        "CREATE INDEX IF NOT EXISTS idx_webhooks_created_by ON webhooks(created_by);",
        
        "CREATE INDEX IF NOT EXISTS idx_webhook_calls_uuid ON webhook_calls(uuid);",
        "CREATE INDEX IF NOT EXISTS idx_webhook_calls_webhook_id ON webhook_calls(webhook_id);",
        "CREATE INDEX IF NOT EXISTS idx_webhook_calls_event_type ON webhook_calls(event_type);",
        "CREATE INDEX IF NOT EXISTS idx_webhook_calls_status ON webhook_calls(status);",
        "CREATE INDEX IF NOT EXISTS idx_webhook_calls_created_at ON webhook_calls(created_at);",
        
        "CREATE INDEX IF NOT EXISTS idx_webhook_events_uuid ON webhook_events(uuid);",
        "CREATE INDEX IF NOT EXISTS idx_webhook_events_event_type ON webhook_events(event_type);",
        "CREATE INDEX IF NOT EXISTS idx_webhook_events_processed ON webhook_events(processed);",
        "CREATE INDEX IF NOT EXISTS idx_webhook_events_created_at ON webhook_events(created_at);"
    ]
    
    try:
        with engine.connect() as conn:
            # Создаем таблицы
            print("Создание таблицы webhooks...")
            conn.execute(text(create_webhooks_table))
            
            print("Создание таблицы webhook_calls...")
            conn.execute(text(create_webhook_calls_table))
            
            print("Создание таблицы webhook_events...")
            conn.execute(text(create_webhook_events_table))
            
            # Создаем индексы
            print("Создание индексов...")
            for index_sql in create_indexes:
                conn.execute(text(index_sql))
            
            conn.commit()
            print("✅ Таблицы webhook'ов успешно созданы!")
            
            # Проверяем созданные таблицы
            result = conn.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name LIKE '%webhook%'
                ORDER BY name
            """))
            
            tables = result.fetchall()
            print(f"\nСозданные таблицы: {[table[0] for table in tables]}")
            
            return True
            
    except Exception as e:
        print(f"❌ Ошибка создания таблиц webhook'ов: {e}")
        return False


if __name__ == "__main__":
    success = create_webhook_tables()
    sys.exit(0 if success else 1)
