#!/usr/bin/env python3
"""
Проверка структуры таблицы services
"""

import sqlite3

def check_services_structure():
    """Проверяем структуру таблицы services"""
    conn = sqlite3.connect('clinic.db')
    cursor = conn.cursor()
    
    print("🔍 СТРУКТУРА ТАБЛИЦЫ SERVICES")
    print("=" * 50)
    
    # Получаем структуру таблицы
    cursor.execute("PRAGMA table_info(services)")
    columns = cursor.fetchall()
    
    print("📋 Колонки таблицы services:")
    for col in columns:
        print(f"  {col[1]} ({col[2]}) - {'NOT NULL' if col[3] else 'NULL'}")
    
    # Проверяем несколько записей
    cursor.execute("SELECT * FROM services LIMIT 3")
    services = cursor.fetchall()
    
    print(f"\n📅 ПРИМЕРЫ ЗАПИСЕЙ:")
    for i, service in enumerate(services):
        print(f"\n  Запись {i+1}:")
        for j, col in enumerate(columns):
            print(f"    {col[1]}: {service[j]}")
    
    conn.close()

if __name__ == "__main__":
    check_services_structure()
