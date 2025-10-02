#!/usr/bin/env python3
"""
Проверка распределения услуг по категориям в базе данных
"""

import sqlite3
import os

def check_services_distribution():
    """Проверяем распределение услуг по категориям"""

    db_path = 'clinic.db'

    if not os.path.exists(db_path):
        print(f"❌ База данных '{db_path}' не найдена.")
        return False

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        print("🔍 Проверяем услуги в базе данных...")

        # Получаем все активные услуги
        cursor.execute("""
            SELECT service_code, name, department, category_code, category_id
            FROM services
            WHERE active = 1
            ORDER BY service_code
        """)

        services = cursor.fetchall()

        print(f"\n📊 Найдено {len(services)} активных услуг:")
        print("=" * 80)

        # Группируем услуги по категориям
        categories = {
            'K': {'name': 'Кардиология', 'services': []},
            'D': {'name': 'Дерматология', 'services': []},
            'S': {'name': 'Стоматология', 'services': []},
            'L': {'name': 'Лаборатория', 'services': []},
            'C': {'name': 'Косметология', 'services': []},
            'P': {'name': 'Физиотерапия', 'services': []},
            'ECG': {'name': 'ЭКГ', 'services': []},
            'ECHO': {'name': 'ЭхоКГ', 'services': []},
            'D_PROC': {'name': 'Дерматологические процедуры', 'services': []},
            'OTHER': {'name': 'Другие', 'services': []}
        }

        for service_code, name, department, category_code, category_id in services:
            if not service_code:
                categories['OTHER']['services'].append(f"{name} (код: {service_code}, отдел: {department})")
                continue

            # Определяем категорию по коду услуги
            if service_code.upper().startswith('K') or service_code == 'K01' or service_code == 'K02':
                categories['K']['services'].append(f"{name} ({service_code})")
            elif service_code.upper().startswith('D') or service_code == 'D01' or service_code == 'D02':
                categories['D']['services'].append(f"{name} ({service_code})")
            elif service_code.upper().startswith('S') or service_code == 'S01' or service_code == 'S02':
                categories['S']['services'].append(f"{name} ({service_code})")
            elif service_code.upper().startswith('L') or service_code == 'L01' or service_code == 'L02':
                categories['L']['services'].append(f"{name} ({service_code})")
            elif service_code.upper().startswith('C') or service_code == 'C01' or service_code == 'C02':
                categories['C']['services'].append(f"{name} ({service_code})")
            elif service_code.upper().startswith('P') or service_code == 'P01' or service_code == 'P02':
                categories['P']['services'].append(f"{name} ({service_code})")
            elif 'ECG' in service_code.upper() or 'ЭКГ' in name.upper():
                categories['ECG']['services'].append(f"{name} ({service_code})")
            elif 'ECHO' in service_code.upper() or 'ЭхоКГ' in name or 'ЭХО' in name.upper():
                categories['ECHO']['services'].append(f"{name} ({service_code})")
            else:
                categories['OTHER']['services'].append(f"{name} ({service_code})")

        # Выводим распределение
        for cat_code, cat_data in categories.items():
            if cat_data['services']:
                print(f"\n🏥 {cat_data['name']} ({cat_code}):")
                for service in cat_data['services']:
                    print(f"   • {service}")

        print("\n" + "=" * 80)

        # Проверим распределение по требованиям пользователя
        print("\n🔍 Проверка соответствия требованиям:")

        # Кардиолог (должен включать K и ECHO)
        cardio_services = categories['K']['services'] + categories['ECHO']['services']
        print(f"✅ Кардиолог: {len(cardio_services)} услуг")
        for service in cardio_services[:3]:  # Показываем первые 3
            print(f"   • {service}")
        if len(cardio_services) > 3:
            print(f"   ... и ещё {len(cardio_services) - 3} услуг")

        # ЭКГ (только ECG)
        ecg_services = categories['ECG']['services']
        print(f"✅ ЭКГ: {len(ecg_services)} услуг")
        for service in ecg_services:
            print(f"   • {service}")

        # Дерматолог (только D)
        derma_services = categories['D']['services']
        print(f"✅ Дерматолог: {len(derma_services)} услуг")
        for service in derma_services[:3]:
            print(f"   • {service}")
        if len(derma_services) > 3:
            print(f"   ... и ещё {len(derma_services) - 3} услуг")

        # Стоматолог (только S)
        dental_services = categories['S']['services']
        print(f"✅ Стоматолог: {len(dental_services)} услуг")
        for service in dental_services:
            print(f"   • {service}")

        # Лаборатория (только L)
        lab_services = categories['L']['services']
        print(f"✅ Лаборатория: {len(lab_services)} услуг")
        for service in lab_services[:3]:
            print(f"   • {service}")
        if len(lab_services) > 3:
            print(f"   ... и ещё {len(lab_services) - 3} услуг")

        # Процедуры (P, C, D_PROC)
        proc_services = categories['P']['services'] + categories['C']['services'] + categories['D_PROC']['services']
        print(f"✅ Процедуры: {len(proc_services)} услуг")

        physio_services = categories['P']['services']
        cosmetology_services = categories['C']['services']
        derm_proc_services = categories['D_PROC']['services']

        if physio_services:
            print(f"   📋 Физиотерапия: {len(physio_services)} услуг")
            for service in physio_services[:2]:
                print(f"      • {service}")
            if len(physio_services) > 2:
                print(f"      ... и ещё {len(physio_services) - 2} услуг")

        if cosmetology_services:
            print(f"   💄 Косметология: {len(cosmetology_services)} услуг")
            for service in cosmetology_services[:2]:
                print(f"      • {service}")
            if len(cosmetology_services) > 2:
                print(f"      ... и ещё {len(cosmetology_services) - 2} услуг")

        if derm_proc_services:
            print(f"   🩺 Дерматологические процедуры: {len(derm_proc_services)} услуг")
            for service in derm_proc_services:
                print(f"      • {service}")

        # Другие услуги
        other_services = categories['OTHER']['services']
        if other_services:
            print(f"\n⚠️ Другие услуги (требуют классификации): {len(other_services)} услуг")
            for service in other_services[:3]:
                print(f"   • {service}")
            if len(other_services) > 3:
                print(f"   ... и ещё {len(other_services) - 3} услуг")

        return True

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    check_services_distribution()
