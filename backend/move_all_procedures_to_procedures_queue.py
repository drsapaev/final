#!/usr/bin/env python3
"""
Перемещение всех процедур в очередь procedures
"""

import sqlite3

def move_all_procedures_to_procedures_queue():
    """Перемещаем все процедуры в очередь procedures"""
    conn = sqlite3.connect('clinic.db')
    cursor = conn.cursor()
    
    print("🔧 ПЕРЕМЕЩАЕМ ВСЕ ПРОЦЕДУРЫ В ОЧЕРЕДЬ 'PROCEDURES'")
    print("=" * 60)
    
    # Перемещаем физиотерапию (P)
    print("\n📋 ШАГ 1: Перемещаем физиотерапию (P)")
    cursor.execute("UPDATE services SET queue_tag = 'procedures' WHERE category_code = 'P'")
    updated_physio = cursor.rowcount
    print(f"✅ Обновлено физиотерапевтических услуг: {updated_physio}")
    
    # Перемещаем дерматологические процедуры (D_PROC)
    print("\n📋 ШАГ 2: Перемещаем дерматологические процедуры (D_PROC)")
    cursor.execute("UPDATE services SET queue_tag = 'procedures' WHERE category_code = 'D_PROC'")
    updated_derm_proc = cursor.rowcount
    print(f"✅ Обновлено дерматологических процедур: {updated_derm_proc}")
    
    # Проверяем результат
    print("\n📊 РЕЗУЛЬТАТ:")
    print("-" * 30)
    
    cursor.execute("SELECT COUNT(*) FROM services WHERE queue_tag = 'procedures' AND category_code IN ('P', 'C', 'D_PROC')")
    total_procedures = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM services WHERE category_code = 'P' AND queue_tag = 'procedures'")
    physio_in_procedures = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM services WHERE category_code = 'C' AND queue_tag = 'procedures'")
    cosmo_in_procedures = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM services WHERE category_code = 'D_PROC' AND queue_tag = 'procedures'")
    derm_proc_in_procedures = cursor.fetchone()[0]
    
    print(f"Всего процедур в очереди 'procedures': {total_procedures}")
    print(f"Физиотерапия (P): {physio_in_procedures}")
    print(f"Косметология (C): {cosmo_in_procedures}")
    print(f"Дерматологические процедуры (D_PROC): {derm_proc_in_procedures}")
    
    # Проверяем, что все процедуры теперь в одной очереди
    cursor.execute("SELECT DISTINCT queue_tag FROM services WHERE category_code IN ('P', 'C', 'D_PROC')")
    queue_tags = cursor.fetchall()
    
    print(f"\n📋 ОЧЕРЕДИ С ПРОЦЕДУРАМИ:")
    print("-" * 30)
    
    for tag in queue_tags:
        tag_name = tag[0] if tag[0] else 'NULL'
        cursor.execute("SELECT COUNT(*) FROM services WHERE queue_tag = ? AND category_code IN ('P', 'C', 'D_PROC')", (tag[0],))
        count = cursor.fetchone()[0]
        print(f"  {tag_name}: {count} процедур")
    
    # Сохраняем изменения
    conn.commit()
    
    if len(queue_tags) == 1 and queue_tags[0][0] == 'procedures':
        print(f"\n🎉 УСПЕХ! Все процедуры теперь в одной очереди 'procedures'!")
    else:
        print(f"\n⚠️ ВНИМАНИЕ! Процедуры все еще разделены по очередям")
    
    conn.close()

if __name__ == "__main__":
    move_all_procedures_to_procedures_queue()
