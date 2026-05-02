#!/usr/bin/env python3
"""
Скрипт для создания таблиц файловой системы
"""
import sqlite3
import os

def create_file_system_tables():
    """Создать таблицы файловой системы"""
    
    # Подключаемся к базе данных
    db_path = "clinic.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Создаем таблицы файловой системы
        tables = [
            # Таблица файлов
            """
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename VARCHAR(255) NOT NULL,
                original_filename VARCHAR(255) NOT NULL,
                file_path VARCHAR(500) NOT NULL,
                file_size INTEGER NOT NULL,
                file_type VARCHAR(50) NOT NULL,
                mime_type VARCHAR(100) NOT NULL,
                file_hash VARCHAR(64),
                status VARCHAR(20) DEFAULT 'uploading' NOT NULL,
                permission VARCHAR(20) DEFAULT 'private' NOT NULL,
                title VARCHAR(255),
                description TEXT,
                tags TEXT,
                file_metadata TEXT,
                owner_id INTEGER NOT NULL,
                patient_id INTEGER,
                appointment_id INTEGER,
                emr_id INTEGER,
                folder_id INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                expires_at DATETIME,
                FOREIGN KEY (owner_id) REFERENCES users(id),
                FOREIGN KEY (patient_id) REFERENCES patients(id),
                FOREIGN KEY (appointment_id) REFERENCES appointments(id),
                FOREIGN KEY (emr_id) REFERENCES emr(id)
            )
            """,
            
            # Таблица версий файлов
            """
            CREATE TABLE IF NOT EXISTS file_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER NOT NULL,
                version_number INTEGER NOT NULL,
                file_path VARCHAR(500) NOT NULL,
                file_size INTEGER NOT NULL,
                file_hash VARCHAR(64),
                change_description TEXT,
                created_by INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                FOREIGN KEY (file_id) REFERENCES files(id),
                FOREIGN KEY (created_by) REFERENCES users(id)
            )
            """,
            
            # Таблица совместного использования файлов
            """
            CREATE TABLE IF NOT EXISTS file_shares (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER NOT NULL,
                shared_with_user_id INTEGER,
                shared_with_email VARCHAR(255),
                permission VARCHAR(20) NOT NULL,
                access_token VARCHAR(64),
                expires_at DATETIME,
                is_active BOOLEAN DEFAULT 1 NOT NULL,
                created_by INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                FOREIGN KEY (file_id) REFERENCES files(id),
                FOREIGN KEY (shared_with_user_id) REFERENCES users(id),
                FOREIGN KEY (created_by) REFERENCES users(id)
            )
            """,
            
            # Таблица папок
            """
            CREATE TABLE IF NOT EXISTS file_folders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                parent_id INTEGER,
                owner_id INTEGER NOT NULL,
                is_system BOOLEAN DEFAULT 0 NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                FOREIGN KEY (parent_id) REFERENCES file_folders(id),
                FOREIGN KEY (owner_id) REFERENCES users(id)
            )
            """,
            
            # Таблица логов доступа к файлам
            """
            CREATE TABLE IF NOT EXISTS file_access_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER NOT NULL,
                user_id INTEGER,
                action VARCHAR(50) NOT NULL,
                ip_address VARCHAR(45),
                user_agent TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                FOREIGN KEY (file_id) REFERENCES files(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """,
            
            # Таблица настроек хранилища
            """
            CREATE TABLE IF NOT EXISTS file_storage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100) NOT NULL UNIQUE,
                storage_type VARCHAR(50) NOT NULL,
                config TEXT NOT NULL,
                is_default BOOLEAN DEFAULT 0 NOT NULL,
                is_active BOOLEAN DEFAULT 1 NOT NULL,
                max_file_size INTEGER,
                allowed_types TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
            """,
            
            # Таблица квот пользователей
            """
            CREATE TABLE IF NOT EXISTS file_quotas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                max_storage_bytes INTEGER NOT NULL,
                used_storage_bytes INTEGER DEFAULT 0 NOT NULL,
                max_files INTEGER,
                used_files INTEGER DEFAULT 0 NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        ]
        
        # Выполняем создание таблиц
        for table_sql in tables:
            cursor.execute(table_sql)
            print(f"✅ Таблица создана: {table_sql.split('(')[0].split()[-1]}")
        
        # Создаем индексы
        indexes = [
            "CREATE INDEX IF NOT EXISTS ix_files_id ON files(id)",
            "CREATE INDEX IF NOT EXISTS ix_files_filename ON files(filename)",
            "CREATE INDEX IF NOT EXISTS ix_files_file_type ON files(file_type)",
            "CREATE INDEX IF NOT EXISTS ix_files_status ON files(status)",
            "CREATE INDEX IF NOT EXISTS ix_files_owner_id ON files(owner_id)",
            "CREATE INDEX IF NOT EXISTS ix_files_patient_id ON files(patient_id)",
            "CREATE INDEX IF NOT EXISTS ix_files_appointment_id ON files(appointment_id)",
            "CREATE INDEX IF NOT EXISTS ix_files_emr_id ON files(emr_id)",
            "CREATE INDEX IF NOT EXISTS ix_files_file_hash ON files(file_hash)",
            
            "CREATE INDEX IF NOT EXISTS ix_file_versions_id ON file_versions(id)",
            "CREATE INDEX IF NOT EXISTS ix_file_versions_file_id ON file_versions(file_id)",
            
            "CREATE INDEX IF NOT EXISTS ix_file_shares_id ON file_shares(id)",
            "CREATE INDEX IF NOT EXISTS ix_file_shares_file_id ON file_shares(file_id)",
            "CREATE INDEX IF NOT EXISTS ix_file_shares_shared_with_user_id ON file_shares(shared_with_user_id)",
            "CREATE INDEX IF NOT EXISTS ix_file_shares_shared_with_email ON file_shares(shared_with_email)",
            "CREATE INDEX IF NOT EXISTS ix_file_shares_access_token ON file_shares(access_token)",
            
            "CREATE INDEX IF NOT EXISTS ix_file_folders_id ON file_folders(id)",
            "CREATE INDEX IF NOT EXISTS ix_file_folders_owner_id ON file_folders(owner_id)",
            "CREATE INDEX IF NOT EXISTS ix_file_folders_parent_id ON file_folders(parent_id)",
            
            "CREATE INDEX IF NOT EXISTS ix_file_access_logs_id ON file_access_logs(id)",
            "CREATE INDEX IF NOT EXISTS ix_file_access_logs_file_id ON file_access_logs(file_id)",
            "CREATE INDEX IF NOT EXISTS ix_file_access_logs_user_id ON file_access_logs(user_id)",
            
            "CREATE INDEX IF NOT EXISTS ix_file_storage_id ON file_storage(id)",
            
            "CREATE INDEX IF NOT EXISTS ix_file_quotas_id ON file_quotas(id)",
            "CREATE INDEX IF NOT EXISTS ix_file_quotas_user_id ON file_quotas(user_id)"
        ]
        
        for index_sql in indexes:
            cursor.execute(index_sql)
            print(f"✅ Индекс создан: {index_sql.split('ON')[1].strip()}")
        
        # Добавляем внешний ключ для папок
        cursor.execute("""
            ALTER TABLE files ADD COLUMN folder_id INTEGER REFERENCES file_folders(id)
        """)
        print("✅ Внешний ключ добавлен: files.folder_id")
        
        # Создаем папку по умолчанию для каждого пользователя
        cursor.execute("SELECT id FROM users")
        users = cursor.fetchall()
        
        for user_id in users:
            cursor.execute("""
                INSERT OR IGNORE INTO file_folders (name, description, owner_id, is_system)
                VALUES (?, ?, ?, ?)
            """, ("Корневая папка", "Основная папка пользователя", user_id[0], 1))
        
        print(f"✅ Созданы корневые папки для {len(users)} пользователей")
        
        # Создаем настройки хранилища по умолчанию
        cursor.execute("""
            INSERT OR IGNORE INTO file_storage (name, storage_type, config, is_default, is_active, max_file_size, allowed_types)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            "Локальное хранилище",
            "local",
            '{"path": "storage/files"}',
            1,
            1,
            104857600,  # 100MB
            '["image", "video", "audio", "document", "archive", "medical_record", "lab_result", "xray", "prescription", "report", "backup", "other"]'
        ))
        print("✅ Созданы настройки хранилища по умолчанию")
        
        # Создаем квоты по умолчанию для пользователей
        for user_id in users:
            cursor.execute("""
                INSERT OR IGNORE INTO file_quotas (user_id, max_storage_bytes, max_files)
                VALUES (?, ?, ?)
            """, (user_id[0], 1073741824, 1000))  # 1GB, 1000 файлов
        
        print(f"✅ Созданы квоты по умолчанию для {len(users)} пользователей")
        
        # Сохраняем изменения
        conn.commit()
        print("\n🎉 Все таблицы файловой системы успешно созданы!")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    create_file_system_tables()

