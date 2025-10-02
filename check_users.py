#!/usr/bin/env python3
"""
Проверка пользователей в системе
"""

import sqlite3

def check_users():
    """Проверяем пользователей в системе"""
    conn = sqlite3.connect('backend/clinic.db')
    cursor = conn.cursor()
    
    print("👥 ПРОВЕРКА ПОЛЬЗОВАТЕЛЕЙ В СИСТЕМЕ")
    print("=" * 50)
    
    # Проверяем таблицу пользователей
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%user%'")
    user_tables = cursor.fetchall()
    print(f"📋 Таблицы пользователей: {[t[0] for t in user_tables]}")
    
    # Проверяем таблицу users
    try:
        cursor.execute("SELECT id, email, username, role FROM users LIMIT 10")
        users = cursor.fetchall()
        print(f"\n👤 ПОЛЬЗОВАТЕЛИ ({len(users)} найдено):")
        for user in users:
            print(f"  ID: {user[0]}, Email: {user[1]}, Username: {user[2]}, Role: {user[3]}")
    except Exception as e:
        print(f"❌ Ошибка при чтении пользователей: {e}")
    
    # Проверяем таблицу staff
    try:
        cursor.execute("SELECT id, email, username, role FROM staff LIMIT 10")
        staff = cursor.fetchall()
        print(f"\n👨‍⚕️ СТАФФ ({len(staff)} найдено):")
        for person in staff:
            print(f"  ID: {person[0]}, Email: {person[1]}, Username: {person[2]}, Role: {person[3]}")
    except Exception as e:
        print(f"❌ Ошибка при чтении стаффа: {e}")
    
    conn.close()

if __name__ == "__main__":
    check_users()