#!/usr/bin/env python3
"""
Проверка структуры таблицы appointments
"""

import sqlite3

def check_appointments_structure():
    """Проверяем структуру таблицы appointments"""
    conn = sqlite3.connect('backend/clinic.db')
    cursor = conn.cursor()
    
    print("🔍 СТРУКТУРА ТАБЛИЦЫ APPOINTMENTS")
    print("=" * 50)
    
    # Получаем структуру таблицы
    cursor.execute("PRAGMA table_info(appointments)")
    columns = cursor.fetchall()
    
    print("📋 Колонки таблицы appointments:")
    for col in columns:
        print(f"  {col[1]} ({col[2]}) - {'NOT NULL' if col[3] else 'NULL'}")
    
    # Проверяем записи
    cursor.execute("SELECT * FROM appointments ORDER BY created_at DESC LIMIT 5")
    appointments = cursor.fetchall()
    
    print(f"\n📅 ПОСЛЕДНИЕ ЗАПИСИ ({len(appointments)} найдено):")
    for i, appt in enumerate(appointments):
        print(f"\n  Запись {i+1}:")
        for j, col in enumerate(columns):
            print(f"    {col[1]}: {appt[j]}")
    
    conn.close()

if __name__ == "__main__":
    check_appointments_structure()
