#!/usr/bin/env python3
"""
Исправление распределения процедур по категориям
"""

import sqlite3

def fix_procedures_distribution():
    """Исправляем распределение процедур"""
    conn = sqlite3.connect('clinic.db')
    cursor = conn.cursor()
    
    print("🔧 Исправляем распределение процедур...")
    print("=" * 50)
    
    # 1. Перемещаем физиотерапию из D10-D14 в P01-P05
    print("\n📋 ШАГ 1: Перемещаем физиотерапию D10-D14 → P01-P05")
    
    physio_mapping = [
        ('D10', 'P01', 'Дарсонваль'),
        ('D11', 'P02', 'УФО терапия'),
        ('D12', 'P03', 'Диодная маска лица'),
        ('D13', 'P04', 'Биоптрон - светотерапия'),
        ('D14', 'P05', 'Эксимер лазер')
    ]
    
    for old_code, new_code, name in physio_mapping:
        # Проверяем, существует ли старая услуга
        cursor.execute("SELECT id FROM services WHERE service_code = ?", (old_code,))
        old_service = cursor.fetchone()
        
        if old_service:
            # Обновляем код и категорию
            cursor.execute("""
                UPDATE services 
                SET service_code = ?, category_code = 'P', department = 'physiotherapy'
                WHERE service_code = ?
            """, (new_code, old_code))
            print(f"  ✅ {old_code} → {new_code}: {name}")
        else:
            print(f"  ⚠️ Услуга {old_code} не найдена")
    
    # 2. Перемещаем дерматологические процедуры из D20-D22 в D_PROC01-D_PROC03
    print("\n🔬 ШАГ 2: Перемещаем дерматологические процедуры D20-D22 → D_PROC01-D_PROC03")
    
    derm_proc_mapping = [
        ('D20', 'D_PROC01', 'Криодеструкция бородавок'),
        ('D21', 'D_PROC02', 'Криодеструкция папиллом'),
        ('D22', 'D_PROC03', 'Мезотерапия келлоидных рубцов')
    ]
    
    for old_code, new_code, name in derm_proc_mapping:
        # Проверяем, существует ли старая услуга
        cursor.execute("SELECT id FROM services WHERE service_code = ?", (old_code,))
        old_service = cursor.fetchone()
        
        if old_service:
            # Обновляем код и категорию
            cursor.execute("""
                UPDATE services 
                SET service_code = ?, category_code = 'D_PROC', department = 'dermatology'
                WHERE service_code = ?
            """, (new_code, old_code))
            print(f"  ✅ {old_code} → {new_code}: {name}")
        else:
            print(f"  ⚠️ Услуга {old_code} не найдена")
    
    # Сохраняем изменения
    conn.commit()
    
    # Проверяем результат
    print("\n📊 РЕЗУЛЬТАТ:")
    print("=" * 30)
    
    # Физиотерапия
    cursor.execute("SELECT service_code, name FROM services WHERE category_code = 'P' ORDER BY service_code")
    physio_services = cursor.fetchall()
    print(f"\n📋 ФИЗИОТЕРАПИЯ ({len(physio_services)} услуг):")
    for service in physio_services:
        print(f"  {service[0]} - {service[1]}")
    
    # Косметология
    cursor.execute("SELECT service_code, name FROM services WHERE category_code = 'C' ORDER BY service_code")
    cosmo_services = cursor.fetchall()
    print(f"\n💄 КОСМЕТОЛОГИЯ ({len(cosmo_services)} услуг):")
    for service in cosmo_services:
        print(f"  {service[0]} - {service[1]}")
    
    # Дерматологические процедуры
    cursor.execute("SELECT service_code, name FROM services WHERE category_code = 'D_PROC' ORDER BY service_code")
    derm_proc_services = cursor.fetchall()
    print(f"\n🔬 ДЕРМАТОЛОГИЧЕСКИЕ ПРОЦЕДУРЫ ({len(derm_proc_services)} услуг):")
    for service in derm_proc_services:
        print(f"  {service[0]} - {service[1]}")
    
    # Дерматология (только консультации)
    cursor.execute("SELECT service_code, name FROM services WHERE category_code = 'D' ORDER BY service_code")
    derm_services = cursor.fetchall()
    print(f"\n👨‍⚕️ ДЕРМАТОЛОГИЯ - КОНСУЛЬТАЦИИ ({len(derm_services)} услуг):")
    for service in derm_services:
        print(f"  {service[0]} - {service[1]}")
    
    conn.close()
    print(f"\n🎉 Исправление завершено!")
    print(f"📊 ИТОГО для вкладки 'Процедуры': {len(physio_services) + len(cosmo_services) + len(derm_proc_services)} услуг")

if __name__ == "__main__":
    fix_procedures_distribution()
