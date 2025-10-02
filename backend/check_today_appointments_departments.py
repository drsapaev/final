#!/usr/bin/env python3
"""
Проверка записей на сегодня и их department
"""

import sqlite3
import json
from datetime import date

def check_today_appointments_departments():
    """Проверяем department записей на сегодня"""
    conn = sqlite3.connect('clinic.db')
    cursor = conn.cursor()
    
    today = date.today()
    print(f"🔍 ПРОВЕРКА ЗАПИСЕЙ НА СЕГОДНЯ ({today})")
    print("=" * 60)
    
    # Проверяем appointments на сегодня
    print(f"\n📋 APPOINTMENTS НА СЕГОДНЯ:")
    print("-" * 40)
    
    cursor.execute("""
        SELECT id, patient_id, department, services, created_at
        FROM appointments 
        WHERE appointment_date = ?
        ORDER BY created_at DESC
    """, (today,))
    appointments = cursor.fetchall()
    
    print(f"Найдено записей: {len(appointments)}")
    
    departments = {}
    for appt in appointments:
        appt_id, patient_id, department, services_json, created_at = appt
        print(f"\n  Запись {appt_id} (пациент {patient_id}):")
        print(f"    Отдел: {department}")
        print(f"    Услуги: {services_json}")
        print(f"    Создана: {created_at}")
        
        # Анализируем услуги
        if services_json:
            try:
                services = json.loads(services_json) if isinstance(services_json, str) else services_json
                print(f"    Услуги (JSON): {services}")
                
                # Проверяем, есть ли процедуры в названиях услуг
                procedure_names = []
                for service in services:
                    if isinstance(service, str):
                        service_lower = service.lower()
                        if any(word in service_lower for word in [
                            'дарсонваль', 'уфо', 'диодная маска', 'биоптрон', 'эксимер лазер',
                            'плазмолифтинг', 'чистка лица', 'блефаропластика', 'жировик', 'татуировок', 'пилинг',
                            'криодеструкция', 'бородавок', 'папиллом', 'мезотерапия', 'рубцов'
                        ]):
                            procedure_names.append(service)
                
                if procedure_names:
                    print(f"    🎯 Процедуры: {procedure_names}")
                    if department != 'procedures':
                        print(f"    ⚠️ ПРОБЛЕМА: Процедуры в отделе '{department}', должны быть в 'procedures'")
            except Exception as e:
                print(f"    ❌ Ошибка обработки услуг: {e}")
        
        # Подсчитываем по отделам
        if department not in departments:
            departments[department] = 0
        departments[department] += 1
    
    # Проверяем visits на сегодня
    print(f"\n📋 VISITS НА СЕГОДНЯ:")
    print("-" * 40)
    
    cursor.execute("""
        SELECT id, patient_id, department, created_at
        FROM visits 
        WHERE visit_date = ?
        ORDER BY created_at DESC
    """, (today,))
    visits = cursor.fetchall()
    
    print(f"Найдено визитов: {len(visits)}")
    
    for visit in visits:
        visit_id, patient_id, department, created_at = visit
        print(f"\n  Визит {visit_id} (пациент {patient_id}):")
        print(f"    Отдел: {department}")
        print(f"    Создан: {created_at}")
        
        # Подсчитываем по отделам
        if department not in departments:
            departments[department] = 0
        departments[department] += 1
    
    # Итоговая статистика
    print(f"\n📊 СТАТИСТИКА ПО ОТДЕЛАМ:")
    print("-" * 30)
    
    for dept, count in departments.items():
        print(f"  {dept}: {count} записей")
    
    conn.close()

if __name__ == "__main__":
    check_today_appointments_departments()
