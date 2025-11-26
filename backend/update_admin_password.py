#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.security import get_password_hash
import sqlite3

def update_admin_password():
    """Обновляет пароль пользователя admin на admin123"""
    try:
        # Подключаемся к базе данных напрямую
        conn = sqlite3.connect('clinic.db')
        cursor = conn.cursor()
        
        # Обновляем пароль пользователя admin
        hashed_password = get_password_hash("admin123")
        cursor.execute("""
            UPDATE users 
            SET hashed_password = ? 
            WHERE username = ?
        """, (hashed_password, "admin"))
        
        conn.commit()
        conn.close()
        
        print("✅ Пароль пользователя admin обновлен на admin123")
        
    except Exception as e:
        print(f"❌ Ошибка обновления пароля: {e}")

if __name__ == "__main__":
    update_admin_password()
