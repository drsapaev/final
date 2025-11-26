#!/usr/bin/env python3
"""
Обновление department в записях для объединения процедур
"""

import sqlite3
import json

def update_appointments_department():
    """Обновляем department в записях для объединения процедур"""
    conn = sqlite3.connect('clinic.db')
    cursor = conn.cursor()
    
    print("🔧 ОБНОВЛЯЕМ DEPARTMENT В ЗАПИСЯХ")
    print("=" * 50)
    
    # Проверяем таблицы
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('visits', 'appointments')")
    tables = cursor.fetchall()
    print(f"📋 Найдены таблицы: {[t[0] for t in tables]}")
    
    # Проверяем appointments
    if ('appointments',) in tables:
        print(f"\n📋 ПРОВЕРЯЕМ APPOINTMENTS:")
        print("-" * 30)
        
        # Получаем записи с процедурами
        cursor.execute("""
            SELECT id, patient_id, services, service_codes, department, created_at
            FROM appointments 
            WHERE services IS NOT NULL 
            ORDER BY created_at DESC 
            LIMIT 10
        """)
        appointments = cursor.fetchall()
        
        print(f"Найдено записей: {len(appointments)}")
        
        for appt in appointments:
            appt_id, patient_id, services_json, service_codes_json, department, created_at = appt
            print(f"\n  Запись {appt_id} (пациент {patient_id}, отдел: {department}):")
            print(f"    Услуги: {services_json}")
            print(f"    Коды: {service_codes_json}")
            print(f"    Создана: {created_at}")
            
            # Проверяем, есть ли процедуры
            has_procedures = False
            if service_codes_json:
                try:
                    codes = json.loads(service_codes_json) if isinstance(service_codes_json, str) else service_codes_json
                    procedure_codes = []
                    for code in codes:
                        if (code.startswith('P') and code[1:].isdigit()) or \
                           (code.startswith('C') and code[1:].isdigit()) or \
                           (code.startswith('D_PROC') and code[6:].isdigit()) or \
                           code.startswith('PHYS_') or \
                           code.startswith('COSM_') or \
                           code.startswith('DERM_'):
                            procedure_codes.append(code)
                            has_procedures = True
                    
                    if has_procedures:
                        print(f"    🎯 Процедуры: {procedure_codes}")
                        if department != 'procedures':
                            print(f"    ⚠️ ПРОБЛЕМА: Процедуры в отделе '{department}', должны быть в 'procedures'")
                            
                            # Обновляем department
                            cursor.execute("UPDATE appointments SET department = 'procedures' WHERE id = ?", (appt_id,))
                            print(f"    ✅ Обновлено: department = 'procedures'")
                except Exception as e:
                    print(f"    ❌ Ошибка обработки кодов: {e}")
    
    # Проверяем visits
    if ('visits',) in tables:
        print(f"\n📋 ПРОВЕРЯЕМ VISITS:")
        print("-" * 30)
        
        # Получаем записи с процедурами
        cursor.execute("""
            SELECT id, patient_id, services, service_codes, department, created_at
            FROM visits 
            WHERE services IS NOT NULL 
            ORDER BY created_at DESC 
            LIMIT 10
        """)
        visits = cursor.fetchall()
        
        print(f"Найдено записей: {len(visits)}")
        
        for visit in visits:
            visit_id, patient_id, services_json, service_codes_json, department, created_at = visit
            print(f"\n  Визит {visit_id} (пациент {patient_id}, отдел: {department}):")
            print(f"    Услуги: {services_json}")
            print(f"    Коды: {service_codes_json}")
            print(f"    Создан: {created_at}")
            
            # Проверяем, есть ли процедуры
            has_procedures = False
            if service_codes_json:
                try:
                    codes = json.loads(service_codes_json) if isinstance(service_codes_json, str) else service_codes_json
                    procedure_codes = []
                    for code in codes:
                        if (code.startswith('P') and code[1:].isdigit()) or \
                           (code.startswith('C') and code[1:].isdigit()) or \
                           (code.startswith('D_PROC') and code[6:].isdigit()) or \
                           code.startswith('PHYS_') or \
                           code.startswith('COSM_') or \
                           code.startswith('DERM_'):
                            procedure_codes.append(code)
                            has_procedures = True
                    
                    if has_procedures:
                        print(f"    🎯 Процедуры: {procedure_codes}")
                        if department != 'procedures':
                            print(f"    ⚠️ ПРОБЛЕМА: Процедуры в отделе '{department}', должны быть в 'procedures'")
                            
                            # Обновляем department
                            cursor.execute("UPDATE visits SET department = 'procedures' WHERE id = ?", (visit_id,))
                            print(f"    ✅ Обновлено: department = 'procedures'")
                except Exception as e:
                    print(f"    ❌ Ошибка обработки кодов: {e}")
    
    # Сохраняем изменения
    conn.commit()
    
    # Проверяем результат
    print(f"\n📊 РЕЗУЛЬТАТ:")
    print("-" * 30)
    
    if ('appointments',) in tables:
        cursor.execute("SELECT COUNT(*) FROM appointments WHERE department = 'procedures'")
        appt_procedures = cursor.fetchone()[0]
        print(f"Appointments с department = 'procedures': {appt_procedures}")
    
    if ('visits',) in tables:
        cursor.execute("SELECT COUNT(*) FROM visits WHERE department = 'procedures'")
        visit_procedures = cursor.fetchone()[0]
        print(f"Visits с department = 'procedures': {visit_procedures}")
    
    conn.close()
    print(f"\n🎉 Обновление завершено!")

if __name__ == "__main__":
    update_appointments_department()
