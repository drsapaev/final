#!/usr/bin/env python3
"""
Добавление недостающих колонок в БД
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from app.db.session import SessionLocal
from sqlalchemy import text

def add_missing_columns():
    """Добавить недостающие колонки"""
    db = SessionLocal()
    try:
        print("🔧 Добавляем недостающие колонки...")
        
        # Добавляем колонку is_superuser
        try:
            db.execute(text("ALTER TABLE users ADD COLUMN is_superuser BOOLEAN DEFAULT 0;"))
            db.commit()
            print("✅ Добавлена колонка is_superuser")
        except Exception as e:
            if "duplicate column name" in str(e).lower():
                print("ℹ️ Колонка is_superuser уже существует")
            else:
                print(f"❌ Ошибка при добавлении is_superuser: {e}")
        
        # Проверяем результат
        result = db.execute(text("PRAGMA table_info(users);"))
        columns = result.fetchall()
        
        print("\n📊 Обновленная структура таблицы 'users':")
        for column in columns:
            print(f"  - {column[1]} ({column[2]})")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        db.rollback()
    finally:
        db.close()

def update_user_emails():
    """Обновить email адреса пользователей"""
    db = SessionLocal()
    try:
        print("\n📧 Обновляем email адреса пользователей...")
        
        # Обновляем admin пользователя
        db.execute(text("UPDATE users SET email = 'admin@example.com' WHERE email = 'admin@test.com';"))
        
        # Обновляем doctor пользователя
        db.execute(text("UPDATE users SET email = 'doctor@example.com' WHERE email = 'doctor@test.com';"))
        
        # Добавляем недостающих пользователей если их нет
        users_to_add = [
            ('registrar', 'registrar@example.com', 'Registrar', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj3QJflHQinm'),  # registrar123
            ('cardio', 'cardio@example.com', 'Doctor', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj3QJflHQinm'),  # cardio123
            ('derma', 'derma@example.com', 'Doctor', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj3QJflHQinm'),  # derma123
            ('dentist', 'dentist@example.com', 'Doctor', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj3QJflHQinm'),  # dentist123
            ('lab', 'lab@example.com', 'Lab', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj3QJflHQinm'),  # lab123
            ('cashier', 'cashier@example.com', 'Cashier', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj3QJflHQinm'),  # cashier123
        ]
        
        for username, email, role, password_hash in users_to_add:
            # Проверяем, существует ли пользователь
            result = db.execute(text("SELECT COUNT(*) FROM users WHERE email = :email"), {"email": email})
            if result.fetchone()[0] == 0:
                db.execute(text("""
                    INSERT INTO users (username, email, role, hashed_password, is_active, is_superuser) 
                    VALUES (:username, :email, :role, :password_hash, 1, 0)
                """), {
                    "username": username,
                    "email": email, 
                    "role": role,
                    "password_hash": password_hash
                })
                print(f"✅ Добавлен пользователь: {email}")
            else:
                print(f"ℹ️ Пользователь {email} уже существует")
        
        # Устанавливаем is_superuser=1 для admin
        db.execute(text("UPDATE users SET is_superuser = 1 WHERE email = 'admin@example.com';"))
        
        db.commit()
        print("✅ Email адреса обновлены")
        
        # Показываем результат
        result = db.execute(text("SELECT username, email, role, is_superuser FROM users;"))
        users = result.fetchall()
        print("\n👥 Обновленный список пользователей:")
        for user in users:
            print(f"  - {user[1]} ({user[0]}) - Role: {user[2]}, Superuser: {user[3]}")
            
    except Exception as e:
        print(f"❌ Ошибка при обновлении email: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("🔧 Исправление структуры базы данных...")
    add_missing_columns()
    update_user_emails()
    print("\n✅ Готово!")

