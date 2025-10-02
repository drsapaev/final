#!/usr/bin/env python3
"""
Обновление записей в очереди для объединения процедур
"""

import sqlite3

def update_queue_entries():
    """Обновляем записи в очереди для объединения процедур"""
    conn = sqlite3.connect('clinic.db')
    cursor = conn.cursor()
    
    print("🔧 ОБНОВЛЯЕМ ЗАПИСИ В ОЧЕРЕДИ")
    print("=" * 50)
    
    # Проверяем таблицы очередей
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%queue%'")
    queue_tables = cursor.fetchall()
    print(f"📋 Таблицы очередей: {[t[0] for t in queue_tables]}")
    
    # Проверяем таблицу daily_queues
    try:
        cursor.execute("SELECT id, specialty, created_at FROM daily_queues ORDER BY created_at DESC LIMIT 10")
        daily_queues = cursor.fetchall()
        print(f"\n📅 ПОСЛЕДНИЕ ОЧЕРЕДИ ({len(daily_queues)} найдено):")
        for queue in daily_queues:
            print(f"  ID {queue[0]}: {queue[1]} (создана: {queue[2]})")
    except Exception as e:
        print(f"❌ Ошибка при чтении daily_queues: {e}")
    
    # Проверяем таблицу online_queue_entries
    try:
        cursor.execute("SELECT id, queue_id, services, service_codes FROM online_queue_entries ORDER BY created_at DESC LIMIT 10")
        entries = cursor.fetchall()
        print(f"\n📋 ПОСЛЕДНИЕ ЗАПИСИ В ОЧЕРЕДИ ({len(entries)} найдено):")
        for entry in entries:
            print(f"  ID {entry[0]}: очередь {entry[1]}, услуги: {entry[2]}, коды: {entry[3]}")
    except Exception as e:
        print(f"❌ Ошибка при чтении online_queue_entries: {e}")
    
    # Проверяем, есть ли записи с процедурами в разных очередях
    print(f"\n🔍 ПРОВЕРЯЕМ ЗАПИСИ С ПРОЦЕДУРАМИ:")
    print("-" * 40)
    
    try:
        # Ищем записи с процедурами
        cursor.execute("""
            SELECT oqe.id, oqe.queue_id, dq.specialty, oqe.services, oqe.service_codes
            FROM online_queue_entries oqe
            JOIN daily_queues dq ON oqe.queue_id = dq.id
            WHERE oqe.service_codes IS NOT NULL
            ORDER BY oqe.created_at DESC
            LIMIT 10
        """)
        entries_with_services = cursor.fetchall()
        
        for entry in entries_with_services:
            entry_id, queue_id, specialty, services, service_codes = entry
            print(f"\n  Запись {entry_id} (очередь: {specialty}):")
            print(f"    Услуги: {services}")
            print(f"    Коды: {service_codes}")
            
            # Проверяем, есть ли процедуры в кодах
            if service_codes:
                import json
                try:
                    codes = json.loads(service_codes) if isinstance(service_codes, str) else service_codes
                    procedure_codes = []
                    for code in codes:
                        if (code.startswith('P') and code[1:].isdigit()) or \
                           (code.startswith('C') and code[1:].isdigit()) or \
                           (code.startswith('D_PROC') and code[6:].isdigit()) or \
                           code.startswith('PHYS_') or \
                           code.startswith('COSM_') or \
                           code.startswith('DERM_'):
                            procedure_codes.append(code)
                    
                    if procedure_codes:
                        print(f"    🎯 Процедуры: {procedure_codes}")
                        if specialty != 'procedures':
                            print(f"    ⚠️ ПРОБЛЕМА: Процедуры в очереди '{specialty}', должны быть в 'procedures'")
                except Exception as e:
                    print(f"    ❌ Ошибка обработки кодов: {e}")
    
    except Exception as e:
        print(f"❌ Ошибка при проверке записей: {e}")
    
    conn.close()

if __name__ == "__main__":
    update_queue_entries()
