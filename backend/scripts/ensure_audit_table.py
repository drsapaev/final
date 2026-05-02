import os
import sqlite3

DB_PATH = os.getenv("CLINIC_DB_PATH", "./clinic.db")

schema_sql = """
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    entity_type TEXT,
    entity_id INTEGER,
    actor_user_id INTEGER,
    payload TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at ON audit_logs (created_at DESC);
"""


def main():
    print(f"Using DB: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.executescript(schema_sql)
        conn.commit()
        print("audit_logs ensured.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
