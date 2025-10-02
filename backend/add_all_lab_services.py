#!/usr/bin/env python3
"""
Добавление всех лабораторных услуг из полного списка
"""

import sqlite3
import os

def add_all_lab_services():
    """Добавляем все лабораторные услуги"""

    db_path = 'clinic.db'

    if not os.path.exists(db_path):
        print(f"❌ База данных '{db_path}' не найдена.")
        return False

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        print("🔄 Добавляем все лабораторные услуги...")

        # Полный список лабораторных услуг согласно требованиям (исключая L02, L31, L50)
        lab_services = [
            # L01 - Общий анализ крови (уже есть)
            # L02 - Биохимический анализ крови (исключить)
            # L03 - Время свертываемости крови (уже есть)
            # L25 - Общий анализ мочи (уже есть)
            # L30 - HBsAg Экспресс тест
            # L31 - Инфекции/серология (исключить)
            # L32 - HIV Экспресс тест
            # L33 - RW Экспресс тест
            # L35 - Глюкоза экспресс тест
            # L50 - Гормоны (исключить)

            # Добавляем недостающие
            ('lab.hbsag', 'HBsAg Экспресс тест', 'L30'),
            ('lab.hiv', 'HIV Экспресс тест', 'L32'),
            ('lab.rw', 'RW Экспресс тест', 'L33'),
            ('lab.glucose_express', 'Глюкоза экспресс тест', 'L35'),
            ('lab.protein', 'Общий белок', 'L10'),
            ('lab.glucose', 'Глюкоза', 'L11'),
            ('lab.cholesterol', 'Холестерин', 'L12'),
            ('lab.urea', 'Мочевина', 'L13'),
            ('lab.creatinine', 'Креатинин', 'L14'),
            ('lab.alt', 'АлАТ - аланинаминотрансфераза', 'L15'),
            ('lab.ast', 'АсАТ - аспартатаминотрансфераза', 'L16'),
            ('lab.bilirubin', 'Билирубин (общ, прям, непрям)', 'L17'),
            ('lab.alkaline', 'Щелочная фосфатаза', 'L18'),
            ('lab.amylase', 'Альфа-амилаза', 'L19'),
            ('lab.potassium', 'Калий', 'L20'),
            ('lab.calcium', 'Кальций', 'L21'),
            ('lab.sodium', 'Натрий', 'L22'),
            ('lab.vitamin_d', 'Витамин Д', 'L23'),
            ('lab.immunoglobulin', 'Иммуноглобулин Е', 'L65'),
            ('lab.spermogram', 'Спермограмма', 'L34'),
            ('lab.rheumatoid', 'Ревматоидный фактор (RF)', 'L40'),
            ('lab.crp', 'С-реактивный белок (CRP)', 'L41'),
            ('lab.aslo', 'Антистрептолизин-О (ASlO)', 'L42'),
            ('lab.brucellosis', 'Бруцеллез (Rose Bengal)', 'L43'),
            ('lab.tsh', 'ТТГ (тиреотропный гормон)', 'L51'),
            ('lab.t4', 'Т4 (тироксин)', 'L52'),
            ('lab.t3', 'Т3 (трийодтиронин)', 'L53'),
            ('lab.at_tpo', 'АТ-ТПО (аутоантитело к тиреопероксидазе)', 'L54'),
            ('lab.testosterone', 'Тестостерон', 'L55'),
            ('lab.fungi', 'Нити грибки', 'L60'),
            ('lab.malassezia', 'Malassezia furfur', 'L61'),
            ('lab.demodex', 'Демодекоз', 'L62'),
            ('lab.smear', 'Мазок на степень чистоты', 'L63'),
            ('lab.stool', 'Кал на я/г', 'L64'),
        ]

        added_count = 0
        for service_code, service_name, service_code_value in lab_services:
            # Проверяем, существует ли услуга
            cursor.execute('SELECT id FROM services WHERE code = ?', (service_code,))
            existing = cursor.fetchone()

            if existing:
                # Обновляем существующие
                cursor.execute("""
                    UPDATE services
                    SET service_code = ?, category_code = 'L', name = ?, active = 1
                    WHERE code = ?
                """, (service_code_value, service_name, service_code))
                print(f"✅ Обновлена лабораторная услуга: {service_code} -> {service_code_value}")
            else:
                # Добавляем новые
                cursor.execute("""
                    INSERT INTO services (code, name, department, unit, price, currency, active, category_code, service_code, duration_minutes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (service_code, service_name, 'laboratory', 'анализ', 15000.00, 'UZS', 1, 'L', service_code_value, 5))
                print(f"✅ Добавлена лабораторная услуга: {service_code_value} - {service_name}")
                added_count += 1

        print(f"\n📊 Добавлено лабораторных услуг: {added_count}")

        conn.commit()
        print("✅ Добавление лабораторных услуг завершено")

        return True

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    add_all_lab_services()
