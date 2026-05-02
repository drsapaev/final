#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.security import get_password_hash
import sqlite3


def _required_admin_password() -> str:
    password = os.getenv("ADMIN_PASSWORD", "").strip()
    if not password:
        raise RuntimeError("Set ADMIN_PASSWORD before updating the admin password.")
    return password


def update_admin_password():
    """Обновляет пароль пользователя admin на ADMIN_PASSWORD."""
    try:
        # Подключаемся к базе данных напрямую
        conn = sqlite3.connect('clinic.db')
        cursor = conn.cursor()
        
        # Обновляем пароль пользователя admin
        hashed_password = get_password_hash(_required_admin_password())
        cursor.execute("""
            UPDATE users 
            SET hashed_password = ? 
            WHERE username = ?
        """, (hashed_password, "admin"))
        
        conn.commit()
        conn.close()
        
        print("✅ Пароль пользователя admin обновлен")
        
    except Exception as e:
        print(f"❌ Ошибка обновления пароля: {e}")

if __name__ == "__main__":
    update_admin_password()
