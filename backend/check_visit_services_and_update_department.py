#!/usr/bin/env python3
"""
Проверка услуг в визитах и обновление department
"""

import sqlite3
import json
from datetime import date

def check_visit_services_and_update_department():
    """Проверяем услуги в визитах и обновляем department"""
    conn = sqlite3.connect('clinic.db')
    cursor = conn.cursor()
    
    today = date.today()
    print(f"🔧 ПРОВЕРКА УСЛУГ В ВИЗИТАХ И ОБНОВЛЕНИЕ DEPARTMENT")
    print("=" * 70)
    
    # Проверяем структуру таблицы visit_services
    print(f"\n📋 СТРУКТУРА ТАБЛИЦЫ VISIT_SERVICES:")
    print("-" * 40)
    
    try:
        cursor.execute("PRAGMA table_info(visit_services)")
        columns = cursor.fetchall()
        
        for col in columns:
            print(f"  {col[1]} ({col[2]}) - {'NOT NULL' if col[3] else 'NULL'}")
        
        # Проверяем несколько записей
        cursor.execute("SELECT * FROM visit_services LIMIT 3")
        records = cursor.fetchall()
        
        if records:
            print(f"\n  Примеры записей:")
            for i, record in enumerate(records):
                print(f"    Запись {i+1}: {record}")
        else:
            print(f"\n  Таблица пуста")
    except Exception as e:
        print(f"❌ Ошибка при проверке visit_services: {e}")
        return
    
    # Проверяем визиты на сегодня
    print(f"\n📋 ВИЗИТЫ НА СЕГОДНЯ С УСЛУГАМИ:")
    print("-" * 50)
    
    cursor.execute("""
        SELECT v.id, v.patient_id, v.department, v.created_at
        FROM visits v
        WHERE v.visit_date = ?
        ORDER BY v.created_at DESC
    """, (today,))
    visits = cursor.fetchall()
    
    updated_count = 0
    
    for visit in visits:
        visit_id, patient_id, department, created_at = visit
        print(f"\n  Визит {visit_id} (пациент {patient_id}, отдел: {department}):")
        
        # Получаем услуги визита
        cursor.execute("""
            SELECT vs.name, vs.code, vs.price, vs.qty
            FROM visit_services vs
            WHERE vs.visit_id = ?
        """, (visit_id,))
        visit_services = cursor.fetchall()
        
        if visit_services:
            print(f"    Услуги:")
            has_procedures = False
            
            for service in visit_services:
                name, code, price, qty = service
                print(f"      - {name} (код: {code}, цена: {price}, кол-во: {qty})")
                
                # Проверяем, является ли услуга процедурой
                if code:
                    if (code.startswith('P') and code[1:].isdigit()) or \
                       (code.startswith('C') and code[1:].isdigit()) or \
                       (code.startswith('D_PROC') and code[6:].isdigit()) or \
                       code.startswith('PHYS_') or \
                       code.startswith('COSM_') or \
                       code.startswith('DERM_'):
                        has_procedures = True
                        print(f"        🎯 Процедура!")
                
                # Также проверяем по названию
                if name:
                    name_lower = name.lower()
                    if any(word in name_lower for word in [
                        'дарсонваль', 'уфо', 'диодная маска', 'биоптрон', 'эксимер лазер',
                        'плазмолифтинг', 'чистка лица', 'блефаропластика', 'жировик', 'татуировок', 'пилинг',
                        'криодеструкция', 'бородавок', 'папиллом', 'мезотерапия', 'рубцов'
                    ]):
                        has_procedures = True
                        print(f"        🎯 Процедура по названию!")
            
            # Если есть процедуры и отдел не procedures, обновляем
            if has_procedures and department != 'procedures':
                print(f"    ⚠️ ПРОБЛЕМА: Процедуры в отделе '{department}', обновляем на 'procedures'")
                cursor.execute("UPDATE visits SET department = 'procedures' WHERE id = ?", (visit_id,))
                updated_count += 1
                print(f"    ✅ Обновлено: department = 'procedures'")
            elif has_procedures:
                print(f"    ✅ Процедуры уже в правильном отделе 'procedures'")
            else:
                print(f"    ℹ️ Нет процедур, отдел '{department}' корректен")
        else:
            print(f"    ❌ Нет услуг в визите")
    
    # Сохраняем изменения
    conn.commit()
    
    # Проверяем результат
    print(f"\n📊 РЕЗУЛЬТАТ:")
    print("-" * 30)
    print(f"Обновлено визитов: {updated_count}")
    
    # Статистика по отделам после обновления
    cursor.execute("""
        SELECT department, COUNT(*) 
        FROM visits 
        WHERE visit_date = ?
        GROUP BY department
        ORDER BY COUNT(*) DESC
    """, (today,))
    departments_after = cursor.fetchall()
    
    print(f"\n📋 СТАТИСТИКА ПО ОТДЕЛАМ ПОСЛЕ ОБНОВЛЕНИЯ:")
    for dept, count in departments_after:
        print(f"  {dept}: {count} записей")
    
    conn.close()
    print(f"\n🎉 Обновление завершено!")

if __name__ == "__main__":
    check_visit_services_and_update_department()
