#!/usr/bin/env python3
"""
Исправление группировки процедур в базе данных
"""

import sqlite3

def fix_procedures_grouping():
    """Исправляем группировку процедур в базе данных"""
    conn = sqlite3.connect('clinic.db')
    cursor = conn.cursor()
    
    print("🔧 ИСПРАВЛЯЕМ ГРУППИРОВКУ ПРОЦЕДУР")
    print("=" * 50)
    
    # 1. Перемещаем все косметологические процедуры в группу 'procedures'
    print("\n📋 ШАГ 1: Перемещаем косметологию в группу 'procedures'")
    
    # Проверяем текущее состояние косметологии
    cursor.execute("SELECT id, name, service_code, category_code FROM services WHERE category_code = 'C'")
    cosmo_services = cursor.fetchall()
    
    print(f"Найдено косметологических услуг: {len(cosmo_services)}")
    for service in cosmo_services:
        print(f"  ID {service[0]}: {service[1]} (код: {service[2]})")
    
    # Обновляем queue_tag для косметологии
    cursor.execute("UPDATE services SET queue_tag = 'procedures' WHERE category_code = 'C'")
    updated_cosmo = cursor.rowcount
    print(f"✅ Обновлено косметологических услуг: {updated_cosmo}")
    
    # 2. Проверяем текущее состояние процедур
    print("\n📋 ШАГ 2: Проверяем текущее состояние процедур")
    
    cursor.execute("SELECT id, name, service_code, category_code, queue_tag FROM services WHERE queue_tag = 'procedures'")
    procedure_services = cursor.fetchall()
    
    print(f"Найдено услуг с queue_tag = 'procedures': {len(procedure_services)}")
    for service in procedure_services:
        print(f"  ID {service[0]}: {service[1]} (код: {service[2]}, категория: {service[3]}, очередь: {service[4]})")
    
    # 3. Проверяем все процедуры по категориям
    print("\n📋 ШАГ 3: Проверяем все процедуры по категориям")
    
    categories = ['P', 'C', 'D_PROC']
    for category in categories:
        cursor.execute("SELECT COUNT(*) FROM services WHERE category_code = ?", (category,))
        count = cursor.fetchone()[0]
        print(f"  Категория {category}: {count} услуг")
    
    # 4. Проверяем записи пациентов
    print("\n📋 ШАГ 4: Проверяем записи пациентов")
    
    cursor.execute("SELECT DISTINCT department FROM appointments WHERE services IS NOT NULL")
    departments = cursor.fetchall()
    
    print(f"Отделы с записями: {[d[0] for d in departments]}")
    
    # Проверяем записи с процедурами
    cursor.execute("""
        SELECT id, patient_id, services, department 
        FROM appointments 
        WHERE services IS NOT NULL 
        ORDER BY created_at DESC 
        LIMIT 10
    """)
    appointments = cursor.fetchall()
    
    print(f"\nПоследние записи:")
    for appt in appointments:
        appt_id, patient_id, services_json, department = appt
        print(f"  Запись {appt_id} (пациент {patient_id}, отдел: {department})")
        print(f"    Услуги: {services_json}")
    
    # Сохраняем изменения
    conn.commit()
    
    # 5. Проверяем результат
    print(f"\n📊 РЕЗУЛЬТАТ:")
    print("-" * 30)
    
    cursor.execute("SELECT COUNT(*) FROM services WHERE queue_tag = 'procedures'")
    total_procedures = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM services WHERE category_code = 'C' AND queue_tag = 'procedures'")
    cosmo_in_procedures = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM services WHERE category_code = 'P' AND queue_tag = 'procedures'")
    physio_in_procedures = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM services WHERE category_code = 'D_PROC' AND queue_tag = 'procedures'")
    derm_proc_in_procedures = cursor.fetchone()[0]
    
    print(f"Всего процедур с queue_tag = 'procedures': {total_procedures}")
    print(f"Косметология с queue_tag = 'procedures': {cosmo_in_procedures}")
    print(f"Физиотерапия с queue_tag = 'procedures': {physio_in_procedures}")
    print(f"Дерматологические процедуры с queue_tag = 'procedures': {derm_proc_in_procedures}")
    
    conn.close()
    print(f"\n🎉 Исправление завершено!")

if __name__ == "__main__":
    fix_procedures_grouping()
