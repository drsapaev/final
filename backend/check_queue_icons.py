"""
Проверка данных queue_entries для иконок очереди
"""
import sqlite3
from datetime import date

def check_queue_entries():
    conn = sqlite3.connect("clinic.db")
    cursor = conn.cursor()

    print("=== Проверка queue_entries ===\n")

    # 1. Количество записей
    cursor.execute("SELECT COUNT(*) FROM queue_entries")
    total = cursor.fetchone()[0]
    print(f"📊 Всего записей в queue_entries: {total}\n")

    if total == 0:
        print("❌ Таблица queue_entries пустая!")
        conn.close()
        return

    # 2. Первые 20 записей
    cursor.execute("""
        SELECT id, number, visit_id, patient_id, created_at
        FROM queue_entries
        ORDER BY id DESC
        LIMIT 20
    """)

    print("📋 Последние 20 записей:")
    for row in cursor.fetchall():
        entry_id, number, visit_id, patient_id, created_at = row
        visit_str = str(visit_id) if visit_id else 'None'
        patient_str = str(patient_id) if patient_id else 'None'
        print(f"  ID: {entry_id:3d}, Number: {number:2d}, Visit: {visit_str:>5s}, Patient: {patient_str:>5s}")

    # 3. Проверка связи с визитами на сегодня
    today = date.today().strftime('%Y-%m-%d')
    cursor.execute("""
        SELECT v.id, v.patient_id, v.department, qe.number, qe.id as queue_entry_id
        FROM visits v
        LEFT JOIN queue_entries qe ON qe.visit_id = v.id
        WHERE v.visit_date = ?
        ORDER BY v.id DESC
        LIMIT 15
    """, (today,))

    print(f"\n🔍 Визиты на сегодня ({today}) и их номера очереди:")
    rows = cursor.fetchall()

    if not rows:
        print("  ⚠️  Нет визитов на сегодня")
    else:
        for row in rows:
            visit_id, patient_id, department, queue_number, queue_entry_id = row
            if queue_number:
                print(f"  ✅ Visit {visit_id:3d} (Patient {patient_id:3d}, {department:12s}): Queue #{queue_number} (entry_id: {queue_entry_id})")
            else:
                print(f"  ❌ Visit {visit_id:3d} (Patient {patient_id:3d}, {department:12s}): No queue entry")

    # 4. Статистика по номерам
    cursor.execute("""
        SELECT number, COUNT(*) as count
        FROM queue_entries
        GROUP BY number
        ORDER BY number
    """)

    print(f"\n📊 Распределение номеров очереди:")
    for row in cursor.fetchall():
        number, count = row
        print(f"  Номер {number}: {count} записей")

    conn.close()
    print("\n✅ Проверка завершена!")

if __name__ == "__main__":
    try:
        check_queue_entries()
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
