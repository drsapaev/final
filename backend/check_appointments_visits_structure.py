#!/usr/bin/env python3
"""
Проверка структуры таблиц appointments и visits
"""

import sqlite3

def check_appointments_visits_structure():
    """Проверяем структуру таблиц appointments и visits"""
    conn = sqlite3.connect('clinic.db')
    cursor = conn.cursor()
    
    print("🔍 СТРУКТУРА ТАБЛИЦ APPOINTMENTS И VISITS")
    print("=" * 60)
    
    tables = ['appointments', 'visits']
    
    for table_name in tables:
        print(f"\n📋 ТАБЛИЦА '{table_name}':")
        
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        
        for col in columns:
            print(f"  {col[1]} ({col[2]}) - {'NOT NULL' if col[3] else 'NULL'}")
        
        # Проверяем несколько записей
        cursor.execute(f"SELECT * FROM {table_name} LIMIT 2")
        records = cursor.fetchall()
        
        if records:
            print(f"\n  Примеры записей:")
            for i, record in enumerate(records):
                print(f"    Запись {i+1}: {record}")
        else:
            print(f"\n  Таблица пуста")
    
    conn.close()

if __name__ == "__main__":
    check_appointments_visits_structure()
