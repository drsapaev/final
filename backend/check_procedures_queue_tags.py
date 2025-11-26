#!/usr/bin/env python3
"""
Проверка queue_tag для всех процедур
"""

import sqlite3

def check_procedures_queue_tags():
    """Проверяем queue_tag для всех процедур"""
    conn = sqlite3.connect('clinic.db')
    cursor = conn.cursor()
    
    print("🔍 ПРОВЕРКА QUEUE_TAG ДЛЯ ПРОЦЕДУР")
    print("=" * 50)
    
    # Проверяем все процедуры
    categories = ['P', 'C', 'D_PROC']
    
    for category in categories:
        print(f"\n📋 КАТЕГОРИЯ {category}:")
        cursor.execute("""
            SELECT id, name, service_code, category_code, queue_tag 
            FROM services 
            WHERE category_code = ? 
            ORDER BY service_code
        """, (category,))
        services = cursor.fetchall()
        
        print(f"Найдено услуг: {len(services)}")
        for service in services:
            print(f"  ID {service[0]}: {service[1]} (код: {service[2]}, очередь: {service[4]})")
    
    # Проверяем уникальные queue_tag
    print(f"\n📊 УНИКАЛЬНЫЕ QUEUE_TAG:")
    print("-" * 30)
    
    cursor.execute("SELECT DISTINCT queue_tag FROM services WHERE category_code IN ('P', 'C', 'D_PROC')")
    queue_tags = cursor.fetchall()
    
    for tag in queue_tags:
        tag_name = tag[0] if tag[0] else 'NULL'
        cursor.execute("SELECT COUNT(*) FROM services WHERE queue_tag = ? AND category_code IN ('P', 'C', 'D_PROC')", (tag[0],))
        count = cursor.fetchone()[0]
        print(f"  {tag_name}: {count} процедур")
    
    conn.close()

if __name__ == "__main__":
    check_procedures_queue_tags()
