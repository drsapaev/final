#!/usr/bin/env python3
"""
Создание таблицы telegram_templates
"""
import sqlite3
import os

db_path = 'clinic.db'

print("🔧 СОЗДАНИЕ ТАБЛИЦЫ TELEGRAM_TEMPLATES")
print("=======================================")

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Создаем таблицу telegram_templates
    print("1. Создаем таблицу telegram_templates...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS telegram_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_key VARCHAR(100) NOT NULL UNIQUE,
            template_type VARCHAR(50) NOT NULL,
            language VARCHAR(10) NOT NULL DEFAULT 'ru',
            subject VARCHAR(200),
            message_text TEXT NOT NULL,
            parse_mode VARCHAR(20) DEFAULT 'HTML',
            disable_web_page_preview BOOLEAN DEFAULT 0,
            inline_buttons TEXT,
            active BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("   ✅ Таблица telegram_templates создана")

    # Добавляем базовые шаблоны
    print("2. Добавляем базовые шаблоны...")
    templates = [
        ('appointment_reminder', 'notification', 'ru', 'Напоминание о записи', 
         'Напоминаем о записи на {appointment_date} в {appointment_time} к врачу {doctor_name}.', 
         'HTML', 0, None),
        ('lab_result_ready', 'notification', 'ru', 'Результаты анализов готовы', 
         'Результаты ваших анализов готовы. Обратитесь к врачу для получения результатов.', 
         'HTML', 0, None),
        ('payment_confirmation', 'notification', 'ru', 'Подтверждение оплаты', 
         'Оплата в размере {amount} руб. успешно проведена. Спасибо!', 
         'HTML', 0, None),
        ('welcome_message', 'welcome', 'ru', 'Добро пожаловать!', 
         'Добро пожаловать в нашу клинику! Мы рады видеть вас среди наших пациентов.', 
         'HTML', 0, None)
    ]
    
    for template in templates:
        cursor.execute("""
            INSERT OR IGNORE INTO telegram_templates 
            (template_key, template_type, language, subject, message_text, parse_mode, disable_web_page_preview, inline_buttons)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, template)
    
    print(f"   ✅ Добавлено {len(templates)} шаблонов")

    # Сохраняем изменения
    conn.commit()
    print("\n✅ Все изменения сохранены")

    # Проверяем созданную таблицу
    print("\n3. Проверяем созданную таблицу...")
    cursor.execute("SELECT COUNT(*) FROM telegram_templates")
    count = cursor.fetchone()[0]
    print(f"   Количество шаблонов: {count}")

    cursor.execute("SELECT template_key, template_type FROM telegram_templates")
    templates_list = cursor.fetchall()
    print("   Созданные шаблоны:")
    for template in templates_list:
        print(f"   - {template[0]} ({template[1]})")

    conn.close()
    print("\n🎉 Создание таблицы telegram_templates завершено успешно!")

except sqlite3.Error as e:
    print(f"❌ Ошибка SQLite: {e}")
except Exception as e:
    print(f"❌ Произошла ошибка: {e}")
