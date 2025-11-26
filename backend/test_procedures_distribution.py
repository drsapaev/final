#!/usr/bin/env python3
"""
Тестирование распределения процедур после исправления
"""

import sqlite3

def test_procedures_distribution():
    """Тестируем распределение процедур"""
    conn = sqlite3.connect('clinic.db')
    cursor = conn.cursor()
    
    print("🧪 ТЕСТИРОВАНИЕ РАСПРЕДЕЛЕНИЯ ПРОЦЕДУР")
    print("=" * 50)
    
    # Проверяем все услуги и их категории
    cursor.execute("""
        SELECT service_code, name, category_code, department 
        FROM services 
        WHERE service_code LIKE 'P%' OR service_code LIKE 'C%' OR service_code LIKE 'D_PROC%' OR service_code LIKE 'D%'
        ORDER BY service_code
    """)
    all_services = cursor.fetchall()
    
    print("\n📋 ВСЕ УСЛУГИ ПО КАТЕГОРИЯМ:")
    print("-" * 30)
    
    categories = {}
    for service in all_services:
        code, name, category, dept = service
        if category not in categories:
            categories[category] = []
        categories[category].append((code, name, dept))
    
    for category, services in categories.items():
        print(f"\n🏷️ КАТЕГОРИЯ '{category}':")
        for code, name, dept in services:
            print(f"  {code} - {name} (отдел: {dept})")
    
    # Проверяем, что старые коды больше не существуют
    print(f"\n🔍 ПРОВЕРКА СТАРЫХ КОДОВ:")
    print("-" * 30)
    
    old_codes = ['D10', 'D11', 'D12', 'D13', 'D14', 'D20', 'D21', 'D22']
    for old_code in old_codes:
        cursor.execute("SELECT service_code FROM services WHERE service_code = ?", (old_code,))
        result = cursor.fetchone()
        if result:
            print(f"  ❌ {old_code} - СТАРЫЙ КОД ВСЕ ЕЩЕ СУЩЕСТВУЕТ!")
        else:
            print(f"  ✅ {old_code} - старый код удален")
    
    # Проверяем новые коды
    print(f"\n🔍 ПРОВЕРКА НОВЫХ КОДОВ:")
    print("-" * 30)
    
    new_physio_codes = ['P01', 'P02', 'P03', 'P04', 'P05']
    new_derm_proc_codes = ['D_PROC01', 'D_PROC02', 'D_PROC03']
    
    print("Физиотерапия:")
    for code in new_physio_codes:
        cursor.execute("SELECT service_code, category_code FROM services WHERE service_code = ?", (code,))
        result = cursor.fetchone()
        if result:
            print(f"  ✅ {code} - категория: {result[1]}")
        else:
            print(f"  ❌ {code} - НЕ НАЙДЕН!")
    
    print("Дерматологические процедуры:")
    for code in new_derm_proc_codes:
        cursor.execute("SELECT service_code, category_code FROM services WHERE service_code = ?", (code,))
        result = cursor.fetchone()
        if result:
            print(f"  ✅ {code} - категория: {result[1]}")
        else:
            print(f"  ❌ {code} - НЕ НАЙДЕН!")
    
    # Итоговая статистика
    print(f"\n📊 ИТОГОВАЯ СТАТИСТИКА:")
    print("-" * 30)
    
    cursor.execute("SELECT COUNT(*) FROM services WHERE category_code = 'P'")
    physio_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM services WHERE category_code = 'C'")
    cosmo_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM services WHERE category_code = 'D_PROC'")
    derm_proc_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM services WHERE category_code = 'D'")
    derm_count = cursor.fetchone()[0]
    
    print(f"📋 Физиотерапия (P): {physio_count} услуг")
    print(f"💄 Косметология (C): {cosmo_count} услуг")
    print(f"🔬 Дерматологические процедуры (D_PROC): {derm_proc_count} услуг")
    print(f"👨‍⚕️ Дерматология - консультации (D): {derm_count} услуг")
    print(f"🎯 ИТОГО для вкладки 'Процедуры': {physio_count + cosmo_count + derm_proc_count} услуг")
    
    conn.close()

if __name__ == "__main__":
    test_procedures_distribution()
