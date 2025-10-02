#!/usr/bin/env python3
"""
Проверка структуры таблиц очередей
"""

import sqlite3

def check_queue_tables_structure():
    """Проверяем структуру таблиц очередей"""
    conn = sqlite3.connect('clinic.db')
    cursor = conn.cursor()
    
    print("🔍 СТРУКТУРА ТАБЛИЦ ОЧЕРЕДЕЙ")
    print("=" * 50)
    
    # Проверяем все таблицы очередей
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%queue%'")
    queue_tables = cursor.fetchall()
    
    for table_name in queue_tables:
        table = table_name[0]
        print(f"\n📋 ТАБЛИЦА '{table}':")
        
        cursor.execute(f"PRAGMA table_info({table})")
        columns = cursor.fetchall()
        
        for col in columns:
            print(f"  {col[1]} ({col[2]}) - {'NOT NULL' if col[3] else 'NULL'}")
        
        # Проверяем несколько записей
        cursor.execute(f"SELECT * FROM {table} LIMIT 3")
        records = cursor.fetchall()
        
        if records:
            print(f"\n  Примеры записей:")
            for i, record in enumerate(records):
                print(f"    Запись {i+1}: {record}")
        else:
            print(f"\n  Таблица пуста")
    
    conn.close()

if __name__ == "__main__":
    check_queue_tables_structure()
