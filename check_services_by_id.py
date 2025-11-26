#!/usr/bin/env python3
"""
Проверка услуг по ID из записей пациентов
"""

import sqlite3
import json

def check_services_by_id():
    """Проверяем услуги по ID из записей"""
    conn = sqlite3.connect('backend/clinic.db')
    cursor = conn.cursor()
    
    print("🔍 ПРОВЕРКА УСЛУГ ПО ID ИЗ ЗАПИСЕЙ")
    print("=" * 50)
    
    # Получаем все записи с услугами
    cursor.execute("SELECT id, patient_id, services, department FROM appointments WHERE services IS NOT NULL ORDER BY created_at DESC LIMIT 10")
    appointments = cursor.fetchall()
    
    print(f"📅 ЗАПИСИ С УСЛУГАМИ ({len(appointments)} найдено):")
    
    for appt in appointments:
        appt_id, patient_id, services_json, department = appt
        print(f"\n  Запись {appt_id} (пациент {patient_id}, отдел: {department}):")
        
        try:
            services = json.loads(services_json) if isinstance(services_json, str) else services_json
            print(f"    Услуги (ID): {services}")
            
            # Проверяем каждую услугу по ID
            for service_id in services:
                cursor.execute("SELECT id, name, service_code, category_code FROM services WHERE id = ?", (int(service_id),))
                service = cursor.fetchone()
                if service:
                    print(f"      ID {service_id}: {service[1]} (код: {service[2]}, категория: {service[3]})")
                else:
                    print(f"      ID {service_id}: УСЛУГА НЕ НАЙДЕНА!")
                    
        except Exception as e:
            print(f"    ❌ Ошибка обработки услуг: {e}")
    
    # Проверяем проблемные услуги (старые коды)
    print(f"\n🔍 ПРОВЕРКА ПРОБЛЕМНЫХ УСЛУГ:")
    print("-" * 30)
    
    # Ищем услуги со старыми кодами
    old_codes = ['D10', 'D11', 'D12', 'D13', 'D14', 'D20', 'D21', 'D22']
    for old_code in old_codes:
        cursor.execute("SELECT id, name, service_code, category_code FROM services WHERE service_code = ?", (old_code,))
        service = cursor.fetchone()
        if service:
            print(f"  ❌ {old_code}: ID {service[0]} - {service[1]} (категория: {service[3]})")
        else:
            print(f"  ✅ {old_code}: не найден")
    
    # Проверяем новые коды
    print(f"\n🔍 ПРОВЕРКА НОВЫХ КОДОВ:")
    print("-" * 30)
    
    new_codes = ['P01', 'P02', 'P03', 'P04', 'P05', 'D_PROC01', 'D_PROC02', 'D_PROC03']
    for new_code in new_codes:
        cursor.execute("SELECT id, name, service_code, category_code FROM services WHERE service_code = ?", (new_code,))
        service = cursor.fetchone()
        if service:
            print(f"  ✅ {new_code}: ID {service[0]} - {service[1]} (категория: {service[3]})")
        else:
            print(f"  ❌ {new_code}: не найден")
    
    conn.close()

if __name__ == "__main__":
    check_services_by_id()
