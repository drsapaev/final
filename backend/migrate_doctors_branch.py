#!/usr/bin/env python3
"""
Миграция таблицы doctors для добавления поля branch_id
"""
import sqlite3
import sys
import os

# Добавляем путь к приложению
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def migrate_doctors_branch():
    """Добавляет поле branch_id в таблицу doctors"""
    print("🔧 МИГРАЦИЯ ТАБЛИЦЫ DOCTORS")
    print("=" * 40)
    
    try:
        conn = sqlite3.connect('clinic.db')
        cursor = conn.cursor()
        
        # Проверяем, есть ли уже поле branch_id
        cursor.execute("PRAGMA table_info(doctors)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'branch_id' in columns:
            print("✅ Поле branch_id уже существует")
            conn.close()
            return True
        
        print("📋 Добавление поля branch_id...")
        
        # Добавляем поле branch_id
        cursor.execute("ALTER TABLE doctors ADD COLUMN branch_id INTEGER")
        print("✅ Поле branch_id добавлено")
        
        # Добавляем внешний ключ (если поддерживается)
        try:
            cursor.execute("""
                CREATE TABLE doctors_new (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER,
                    specialty VARCHAR(100) NOT NULL,
                    cabinet VARCHAR(20),
                    price_default DECIMAL(10,2),
                    start_number_online INTEGER DEFAULT 1 NOT NULL,
                    max_online_per_day INTEGER DEFAULT 15 NOT NULL,
                    auto_close_time TIME DEFAULT '09:00',
                    active BOOLEAN DEFAULT 1 NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    branch_id INTEGER,
                    FOREIGN KEY (branch_id) REFERENCES branches (id)
                )
            """)
            
            # Копируем данные
            cursor.execute("""
                INSERT INTO doctors_new 
                SELECT *, NULL as branch_id FROM doctors
            """)
            
            # Удаляем старую таблицу и переименовываем новую
            cursor.execute("DROP TABLE doctors")
            cursor.execute("ALTER TABLE doctors_new RENAME TO doctors")
            
            print("✅ Внешний ключ добавлен")
            
        except Exception as e:
            print(f"⚠️ Не удалось добавить внешний ключ: {e}")
            print("✅ Поле branch_id добавлено без внешнего ключа")
        
        conn.commit()
        conn.close()
        
        print("✅ Миграция завершена успешно")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")
        return False

if __name__ == "__main__":
    success = migrate_doctors_branch()
    sys.exit(0 if success else 1)
