#!/usr/bin/env python3
"""
Проверка распределения процедур по категориям
"""

import sqlite3

def check_procedures_distribution():
    """Проверяем текущее распределение процедур"""
    conn = sqlite3.connect('clinic.db')
    cursor = conn.cursor()
    
    print("🔍 Услуги для вкладки Процедуры:")
    print("=" * 50)
    
    # Физиотерапия (P01-P05)
    print("\n📋 ФИЗИОТЕРАПИЯ (P01-P05):")
    cursor.execute("""
        SELECT service_code, name, category_code 
        FROM services 
        WHERE service_code LIKE 'P%' 
        ORDER BY service_code
    """)
    physio_services = cursor.fetchall()
    for service in physio_services:
        print(f"  {service[0]} - {service[1]} (категория: {service[2]})")
    
    # Косметология (C01-C12)
    print("\n💄 КОСМЕТОЛОГИЯ (C01-C12):")
    cursor.execute("""
        SELECT service_code, name, category_code 
        FROM services 
        WHERE service_code LIKE 'C%' 
        ORDER BY service_code
    """)
    cosmo_services = cursor.fetchall()
    for service in cosmo_services:
        print(f"  {service[0]} - {service[1]} (категория: {service[2]})")
    
    # Дерматологические процедуры (D_PROC01-D_PROC04)
    print("\n🔬 ДЕРМАТОЛОГИЧЕСКИЕ ПРОЦЕДУРЫ (D_PROC01-D_PROC04):")
    cursor.execute("""
        SELECT service_code, name, category_code 
        FROM services 
        WHERE service_code LIKE 'D_PROC%' 
        ORDER BY service_code
    """)
    derm_proc_services = cursor.fetchall()
    for service in derm_proc_services:
        print(f"  {service[0]} - {service[1]} (категория: {service[2]})")
    
    # Проверяем, есть ли дерматологические процедуры с кодами D01-D99
    print("\n⚠️ ПРОВЕРКА: Дерматологические процедуры с кодами D01-D99:")
    cursor.execute("""
        SELECT service_code, name, category_code 
        FROM services 
        WHERE service_code LIKE 'D%' AND service_code NOT LIKE 'D_PROC%'
        ORDER BY service_code
    """)
    derm_services = cursor.fetchall()
    for service in derm_services:
        print(f"  {service[0]} - {service[1]} (категория: {service[2]})")
    
    conn.close()
    
    print(f"\n📊 ИТОГО:")
    print(f"  Физиотерапия: {len(physio_services)} услуг")
    print(f"  Косметология: {len(cosmo_services)} услуг") 
    print(f"  Дерматологические процедуры: {len(derm_proc_services)} услуг")
    print(f"  Дерматология (консультации): {len(derm_services)} услуг")

if __name__ == "__main__":
    check_procedures_distribution()
