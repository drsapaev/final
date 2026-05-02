"""
Тестирование получения реальных номеров очереди из queue_entries
"""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.models.queue_old import QueueEntry
from app.models.visit import Visit
from datetime import date

def test_queue_entries():
    db = SessionLocal()
    today = date.today()

    print(f"=== Тестирование queue_entries на {today} ===\n")

    # 1. Проверяем все записи в queue_entries
    all_entries = db.query(QueueEntry).all()
    print(f"📊 Всего записей в queue_entries: {len(all_entries)}\n")

    if len(all_entries) == 0:
        print("❌ Таблица queue_entries пустая!\n")
        db.close()
        return

    # 2. Показываем первые 15 записей
    print("📋 Первые 15 записей в queue_entries:")
    for entry in all_entries[:15]:
        print(f"  ID: {entry.id:3d}, Number: {entry.number:2d}, Visit ID: {entry.visit_id or 'None':>5s}, Patient ID: {entry.patient_id or 'None'}")

    # 3. Проверяем связь с визитами
    print(f"\n🔍 Проверка связи с визитами:")
    visits_with_queue = db.query(Visit).filter(
        Visit.id.in_([e.visit_id for e in all_entries if e.visit_id is not None])
    ).all()

    print(f"  Визитов с номерами очереди: {len(visits_with_queue)}")

    # 4. Тестируем логику из registrar_integration.py
    print(f"\n🧪 Тестирование логики получения номера для Visit ID 285:")
    test_visit_id = 285
    queue_entry = db.query(QueueEntry).filter(
        QueueEntry.visit_id == test_visit_id
    ).first()

    if queue_entry:
        print(f"  ✅ Найдена запись: Number = {queue_entry.number}")
    else:
        print(f"  ❌ Запись не найдена для Visit {test_visit_id}")

    # 5. Проверяем для всех визитов на сегодня
    print(f"\n🔍 Визиты на сегодня с номерами очереди:")
    today_visits = db.query(Visit).filter(Visit.visit_date == today).all()

    for visit in today_visits[:10]:  # Первые 10
        queue_entry = db.query(QueueEntry).filter(
            QueueEntry.visit_id == visit.id
        ).first()

        if queue_entry:
            print(f"  Visit {visit.id:3d} (Patient {visit.patient_id:3d}): Queue Number = {queue_entry.number}")
        else:
            print(f"  Visit {visit.id:3d} (Patient {visit.patient_id:3d}): ❌ No queue entry")

    db.close()
    print("\n✅ Тест завершён!")

if __name__ == "__main__":
    try:
        test_queue_entries()
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
