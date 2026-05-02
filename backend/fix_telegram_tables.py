#!/usr/bin/env python3
"""
Исправление таблиц Telegram
"""
import sqlite3
import os

db_path = 'clinic.db'

print("🔧 ИСПРАВЛЕНИЕ ТАБЛИЦ TELEGRAM")
print("===============================")

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. Проверяем структуру таблицы telegram_users
    print("1. Проверяем структуру таблицы telegram_users...")
    cursor.execute("PRAGMA table_info(telegram_users);")
    columns = cursor.fetchall()
    column_names = [col[1] for col in columns]
    print(f"   Существующие колонки: {column_names}")

    # 2. Добавляем недостающие колонки
    if 'patient_id' not in column_names:
        print("   ➕ Добавляем колонку patient_id...")
        cursor.execute("ALTER TABLE telegram_users ADD COLUMN patient_id INTEGER REFERENCES patients(id);")
        print("   ✅ Колонка patient_id добавлена")
    else:
        print("   ℹ️ Колонка patient_id уже существует")

    if 'user_id' not in column_names:
        print("   ➕ Добавляем колонку user_id...")
        cursor.execute("ALTER TABLE telegram_users ADD COLUMN user_id INTEGER REFERENCES users(id);")
        print("   ✅ Колонка user_id добавлена")
    else:
        print("   ℹ️ Колонка user_id уже существует")

    # Добавляем остальные недостающие колонки
    missing_columns = [
        ('chat_id', 'INTEGER'),
        ('appointment_reminders', 'BOOLEAN DEFAULT 1'),
        ('lab_notifications', 'BOOLEAN DEFAULT 1'),
        ('blocked', 'BOOLEAN DEFAULT 0'),
        ('last_activity', 'DATETIME'),
        ('active', 'BOOLEAN DEFAULT 1'),  # Добавляем колонку active
        ('is_active', 'BOOLEAN DEFAULT 1')  # Добавляем колонку is_active
    ]
    
    for col_name, col_type in missing_columns:
        if col_name not in column_names:
            print(f"   ➕ Добавляем колонку {col_name}...")
            cursor.execute(f"ALTER TABLE telegram_users ADD COLUMN {col_name} {col_type};")
            print(f"   ✅ Колонка {col_name} добавлена")
        else:
            print(f"   ℹ️ Колонка {col_name} уже существует")

    # 3. Проверяем структуру таблицы telegram_configs
    print("\n2. Проверяем структуру таблицы telegram_configs...")
    cursor.execute("PRAGMA table_info(telegram_configs);")
    config_columns = cursor.fetchall()
    config_column_names = [col[1] for col in config_columns]
    print(f"   Существующие колонки: {config_column_names}")

    # 4. Проверяем структуру таблицы telegram_messages
    print("\n3. Проверяем структуру таблицы telegram_messages...")
    cursor.execute("PRAGMA table_info(telegram_messages);")
    message_columns = cursor.fetchall()
    message_column_names = [col[1] for col in message_columns]
    print(f"   Существующие колонки: {message_column_names}")

    # 5. Сохраняем изменения
    conn.commit()
    print("\n✅ Все изменения сохранены")

    # 6. Финальная проверка
    print("\n4. Финальная проверка структуры telegram_users...")
    cursor.execute("PRAGMA table_info(telegram_users);")
    final_columns = cursor.fetchall()
    print("   Обновленные колонки:")
    for col in final_columns:
        print(f"   - {col[1]} ({col[2]})")

    conn.close()
    print("\n🎉 Исправление таблиц Telegram завершено успешно!")

except sqlite3.Error as e:
    print(f"❌ Ошибка SQLite: {e}")
except Exception as e:
    print(f"❌ Произошла ошибка: {e}")
