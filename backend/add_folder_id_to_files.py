#!/usr/bin/env python3
"""
Добавить колонку folder_id в таблицу files
"""
import sqlite3

def add_folder_id_column():
    """Добавить колонку folder_id в таблицу files"""
    conn = sqlite3.connect("clinic.db")
    cursor = conn.cursor()
    
    try:
        # Проверяем, есть ли уже колонка folder_id
        cursor.execute("PRAGMA table_info(files)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'folder_id' in columns:
            print("✅ Колонка folder_id уже существует")
            return True
        
        # Добавляем колонку folder_id
        cursor.execute("ALTER TABLE files ADD COLUMN folder_id INTEGER")
        print("✅ Колонка folder_id добавлена")
        
        # Создаем индекс
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_files_folder_id ON files(folder_id)")
        print("✅ Индекс для folder_id создан")
        
        # Создаем внешний ключ
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS files_folder_fk 
            AFTER INSERT ON files
            WHEN NEW.folder_id IS NOT NULL
            BEGIN
                SELECT CASE
                    WHEN (SELECT COUNT(*) FROM file_folders WHERE id = NEW.folder_id) = 0
                    THEN RAISE(ABORT, 'Foreign key constraint failed: files.folder_id')
                END;
            END
        """)
        print("✅ Триггер для внешнего ключа создан")
        
        conn.commit()
        print("🎉 Колонка folder_id успешно добавлена в таблицу files")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    add_folder_id_column()

