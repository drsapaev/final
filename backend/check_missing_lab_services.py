#!/usr/bin/env python3
"""
Проверка отсутствующих лабораторных услуг
"""

import sqlite3
import os

def check_missing_lab_services():
    """Проверяем отсутствующие лабораторные услуги"""

    db_path = 'clinic.db'

    if not os.path.exists(db_path):
        print(f"❌ База данных '{db_path}' не найдена.")
        return False

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Получаем текущие лабораторные услуги
        cursor.execute('SELECT name FROM services WHERE category_code = "L" AND active = 1 ORDER BY service_code')
        current_services = [row[0] for row in cursor.fetchall()]

        # Полный список лабораторных услуг из требований
        required_services = [
            'Общий анализ крови',
            'Время свертываемости крови',
            'Общий анализ мочи',
            'Глюкоза экспресс тест',
            'HBsAg Экспресс тест',
            'HCV Экспресс тест',
            'HIV Экспресс тест',
            'RW Экспресс тест',
            'Общий белок',
            'Глюкоза',
            'Холестерин',
            'Мочевина',
            'Креатинин',
            'АлАТ - аланинаминотрансфераза',
            'АсАТ - аспартатаминотрансфераза',
            'Билирубин (общ, прям, непрям)',
            'Щелочная фосфатаза',
            'Альфа-амилаза',
            'Калий',
            'Кальций',
            'Натрий',
            'Витамин Д',
            'Иммуноглобулин Е',
            'Спермограмма',
            'Ревматоидный фактор (RF)',
            'С-реактивный белок (CRP)',
            'Антистрептолизин-О (ASlO)',
            'Бруцеллез (Rose Bengal)',
            'ТТГ (тиреотропный гормон)',
            'Т4 (тироксин)',
            'Т3 (трийодтиронин)',
            'АТ-ТПО (аутоантитело к тиреопероксидазе)',
            'Тестостерон',
            'Нити грибки',
            'Malassezia furfur',
            'Демодекоз',
            'Мазок на степень чистоты',
            'Кал на я/г',
            'Спермограмма'
        ]

        print(f"Текущих лабораторных услуг: {len(current_services)}")
        print(f"Требуемых лабораторных услуг: {len(required_services)}")

        missing_services = []
        for service in required_services:
            if service not in current_services:
                missing_services.append(service)

        print(f"\nОтсутствующие услуги ({len(missing_services)}):")
        for service in missing_services:
            print(f"  - {service}")

        return True

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    check_missing_lab_services()
