#!/usr/bin/env python3
"""
Проверка услуг в базе данных
"""

import sqlite3

def check_services_in_db():
    """Проверяем услуги в базе данных"""
    conn = sqlite3.connect('clinic.db')
    cursor = conn.cursor()
    
    print("🔍 ПРОВЕРКА УСЛУГ В БАЗЕ ДАННЫХ")
    print("=" * 50)
    
    # Проверяем физиотерапию
    print("\n📋 ФИЗИОТЕРАПИЯ (P01-P05):")
    cursor.execute("SELECT service_code, name, category_code FROM services WHERE service_code LIKE 'P%' ORDER BY service_code")
    physio_services = cursor.fetchall()
    for service in physio_services:
        print(f"  {service[0]} - {service[1]} (категория: {service[2]})")
    
    # Проверяем дерматологические процедуры
    print("\n🔬 ДЕРМАТОЛОГИЧЕСКИЕ ПРОЦЕДУРЫ (D_PROC01-D_PROC03):")
    cursor.execute("SELECT service_code, name, category_code FROM services WHERE service_code LIKE 'D_PROC%' ORDER BY service_code")
    derm_proc_services = cursor.fetchall()
    for service in derm_proc_services:
        print(f"  {service[0]} - {service[1]} (категория: {service[2]})")
    
    # Проверяем косметологию
    print("\n💄 КОСМЕТОЛОГИЯ (C01-C08):")
    cursor.execute("SELECT service_code, name, category_code FROM services WHERE service_code LIKE 'C%' ORDER BY service_code")
    cosmo_services = cursor.fetchall()
    for service in cosmo_services:
        print(f"  {service[0]} - {service[1]} (категория: {service[2]})")
    
    # Проверяем все услуги с кодами процедур
    print("\n🎯 ВСЕ УСЛУГИ ДЛЯ ВКЛАДКИ 'ПРОЦЕДУРЫ':")
    cursor.execute("""
        SELECT service_code, name, category_code 
        FROM services 
        WHERE category_code IN ('P', 'C', 'D_PROC') 
        ORDER BY category_code, service_code
    """)
    all_procedures = cursor.fetchall()
    for service in all_procedures:
        print(f"  {service[0]} - {service[1]} (категория: {service[2]})")
    
    print(f"\n📊 ИТОГО: {len(all_procedures)} услуг для вкладки 'Процедуры'")
    
    conn.close()

if __name__ == "__main__":
    check_services_in_db()
