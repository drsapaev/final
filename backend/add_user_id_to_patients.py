#!/usr/bin/env python3
"""
Добавление поля user_id в таблицу patients
"""
import sqlite3
import os

def add_user_id_to_patients():
    db_path = 'clinic.db'
    
    if not os.path.exists(db_path):
        print(f"❌ База данных '{db_path}' не найдена.")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Проверяем, есть ли уже поле user_id
        cursor.execute("PRAGMA table_info(patients)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if 'user_id' in column_names:
            print("✅ Поле user_id уже существует в таблице patients")
        else:
            # Добавляем поле user_id
            print("➕ Добавляем поле user_id в таблицу patients...")
            cursor.execute("ALTER TABLE patients ADD COLUMN user_id INTEGER REFERENCES users(id)")
            print("✅ Поле user_id добавлено")
        
        # Проверяем результат
        cursor.execute("PRAGMA table_info(patients)")
        columns = cursor.fetchall()
        print("\n📋 Структура таблицы patients:")
        for col in columns:
            print(f"   - {col[1]} ({col[2]})")
        
        conn.commit()
        print("\n✅ Миграция завершена успешно")
        
    except Exception as e:
        print(f"❌ Ошибка при добавлении поля: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    add_user_id_to_patients()
