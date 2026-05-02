#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.session import SessionLocal
from app.core.security import get_password_hash
import sqlite3


def _required_admin_password() -> str:
    password = os.getenv("ADMIN_PASSWORD", "").strip()
    if not password:
        raise RuntimeError("Set ADMIN_PASSWORD before creating the admin user.")
    return password


def create_admin_user_sql():
    """Создает пользователя admin через SQL"""
    try:
        # Подключаемся к базе данных напрямую
        conn = sqlite3.connect('clinic.db')
        cursor = conn.cursor()
        
        # Проверяем, существует ли уже пользователь admin
        cursor.execute("SELECT id FROM users WHERE username = ?", ("admin",))
        if cursor.fetchone():
            print("✅ Пользователь admin уже существует")
            conn.close()
            return
        
        # Создаем пользователя admin согласно документации
        hashed_password = get_password_hash(_required_admin_password())
        cursor.execute("""
            INSERT INTO users (username, email, full_name, hashed_password, is_active, is_superuser, role)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ("admin", "admin@clinic.local", "Администратор", hashed_password, True, True, "Admin"))
        
        conn.commit()
        conn.close()
        
        print("✅ Пользователь admin создан успешно")
        print("   Логин: admin")
        print("   Пароль: задан через ADMIN_PASSWORD")
        
    except Exception as e:
        print(f"❌ Ошибка создания пользователя: {e}")

if __name__ == "__main__":
    create_admin_user_sql()
