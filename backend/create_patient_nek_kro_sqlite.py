#!/usr/bin/env python3
"""
Создание пациента "нек кро" с дерматологическими услугами (SQLite версия)
Данные пациента:
- ФИО: нек кро
- Возраст: 33 года (год рождения 1992)
- Телефон: +998 (92) 365-86-63
- Адрес: ждлорпа 654
- Услуги: D01, D12 (дерматологические)
- Тип: Платный
"""

import sqlite3
import os
from datetime import date, datetime

def create_patient_nek_kro_sqlite():
    """Создание пациента и записи на приём в SQLite"""

    db_path = 'clinic.db'

    if not os.path.exists(db_path):
        print(f"❌ База данных '{db_path}' не найдена.")
        return False

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        print("🚀 Начинаем создание пациента 'нек кро'...")

        # Создаем пациента
        cursor.execute("""
            INSERT INTO patients (first_name, last_name, middle_name, birth_date, phone, address, doc_type, doc_number, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (
            'Нек',
            'Кро',
            None,
            '1992-01-01',
            '+998923658663',
            'ждлорпа 654',
            'passport',
            'НЕИЗВЕСТЕН'
        ))

        patient_id = cursor.lastrowid
        print(f"✅ Создан пациент: ID={patient_id}")

        # Получаем дерматологические услуги
        cursor.execute("""
            SELECT id, name, price FROM services
            WHERE service_code IN ('D01', 'D12') AND active = 1
        """)

        services = cursor.fetchall()

        if not services:
            print("❌ Не найдены услуги с кодами D01, D12. Сначала запустите seed_services.py")
            return False

        print(f"✅ Найдены услуги: {[s[1] for s in services]}")

        # Создаем запись на приём
        today = date.today().strftime('%Y-%m-%d')
        total_price = sum(s[2] or 0 for s in services)

        cursor.execute("""
            INSERT INTO appointments (patient_id, department, appointment_date, appointment_time, status, visit_type,
                                   payment_type, services, payment_amount, payment_currency, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (
            patient_id,
            'dermatology',
            today,
            '10:00',
            'scheduled',
            'paid',
            'cash',
            str([s[1] for s in services]),  # Названия услуг
            total_price,
            'UZS',
            'Создано через скрипт для пациента нек кро'
        ))

        appointment_id = cursor.lastrowid
        print(f"✅ Создана запись на приём: ID={appointment_id}")

        # Выводим итоговую информацию
        print("📊 Итоговая информация:")
        print(f"  👤 Пациент: Нек Кро (ID: {patient_id})")
        print(f"  📞 Телефон: +998923658663")
        print(f"  📍 Адрес: ждлорпа 654")
        print(f"  🏥 Отделение: dermatology")
        print(f"  📅 Дата: {today}")
        print(f"  ⏰ Время: 10:00")
        print(f"  💰 Сумма: {total_price} UZS")
        print(f"  🏷️ Услуги: {', '.join([s[1] for s in services])}")
        print(f"  💳 Тип оплаты: платный")

        conn.commit()
        print("\n✅ Операция завершена успешно")

        return True

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    success = create_patient_nek_kro_sqlite()
    exit(0 if success else 1)
