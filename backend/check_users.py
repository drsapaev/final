#!/usr/bin/env python3
"""
Проверка пользователей в базе данных
"""
import sqlite3

def check_users():
    """Проверить пользователей в базе данных"""
    conn = sqlite3.connect("clinic.db")
    cursor = conn.cursor()
    
    try:
        # Проверяем пользователей
        cursor.execute("SELECT id, username, email, role FROM users LIMIT 5")
        users = cursor.fetchall()
        
        print("👥 Пользователи в базе данных:")
        for user in users:
            print(f"   ID: {user[0]}, Username: {user[1]}, Email: {user[2]}, Role: {user[3]}")
        
        if not users:
            print("❌ Пользователи не найдены!")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    check_users()

