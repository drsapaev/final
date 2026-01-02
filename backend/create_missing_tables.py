"""Check and create missing tables"""
import sqlite3

conn = sqlite3.connect('clinic.db')
cursor = conn.cursor()

# Check existing tables starting with 'web'
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'web%'")
print("Tables starting with 'web':", cursor.fetchall())

# Check if webhooks table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='webhooks'")
if not cursor.fetchone():
    print("Creating webhooks table...")
    cursor.execute("""
        CREATE TABLE webhooks (
            id INTEGER PRIMARY KEY,
            uuid VARCHAR(36) UNIQUE NOT NULL,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            url VARCHAR(2048) NOT NULL,
            events JSON,
            headers JSON,
            secret VARCHAR(255),
            max_retries INTEGER DEFAULT 3,
            retry_delay INTEGER DEFAULT 60,
            timeout INTEGER DEFAULT 30,
            filters JSON,
            status VARCHAR(20) DEFAULT 'active',
            is_active BOOLEAN DEFAULT 1,
            total_calls INTEGER DEFAULT 0,
            successful_calls INTEGER DEFAULT 0,
            failed_calls INTEGER DEFAULT 0,
            last_call_at DATETIME,
            last_success_at DATETIME,
            last_failure_at DATETIME,
            created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("webhooks table created!")
else:
    print("webhooks table already exists")

# Check if webhook_logs table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='webhook_logs'")
if not cursor.fetchone():
    print("Creating webhook_logs table...")
    cursor.execute("""
        CREATE TABLE webhook_logs (
            id INTEGER PRIMARY KEY,
            webhook_id INTEGER REFERENCES webhooks(id) ON DELETE CASCADE,
            event_type VARCHAR(100),
            payload JSON,
            response_code INTEGER,
            response_body TEXT,
            error_message TEXT,
            duration_ms INTEGER,
            attempt_number INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("webhook_logs table created!")
else:
    print("webhook_logs table already exists")

conn.commit()
conn.close()
print("Done!")
