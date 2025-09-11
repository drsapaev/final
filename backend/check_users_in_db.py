#!/usr/bin/env python3
"""
Проверить пользователей в базе данных
"""
import sqlite3

def check_users():
    """Проверить пользователей в БД"""
    conn = sqlite3.connect('clinic.db')
    cursor = conn.cursor()
    
    try:
        # Проверим количество пользователей
        cursor.execute("SELECT COUNT(*) FROM users")
        count = cursor.fetchone()[0]
        print(f"👥 Количество пользователей в БД: {count}")
        
        if count > 0:
            # Покажем всех пользователей
            cursor.execute("SELECT id, username, email, role, is_active FROM users")
            users = cursor.fetchall()
            
            print("\n📋 Пользователи в базе данных:")
            for user in users:
                print(f"  ID: {user[0]}, Username: {user[1]}, Email: {user[2]}, Role: {user[3]}, Active: {user[4]}")
            
            # Проверим есть ли admin
            cursor.execute("SELECT id, username, hashed_password FROM users WHERE username = 'admin'")
            admin = cursor.fetchone()
            
            if admin:
                print(f"\n✅ Пользователь 'admin' найден:")
                print(f"   ID: {admin[0]}")
                print(f"   Username: {admin[1]}")
                print(f"   Password hash: {admin[2][:20]}...")
            else:
                print(f"\n❌ Пользователь 'admin' НЕ найден")
        else:
            print("❌ В таблице users нет пользователей")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_users()

