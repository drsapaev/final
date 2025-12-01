from app.database import get_db
from app.models.online_queue import OnlineQueueEntry, DailyQueue
from datetime import date
from sqlalchemy import and_

def check_db_data():
    db = next(get_db())
    today = date(2025, 12, 1)

    print('=== ПРЯМАЯ ПРОВЕРКА ДАННЫХ В БАЗЕ ДАННЫХ ===')

    # Получаем все записи из онлайн-очереди на сегодня
    online_entries = db.query(OnlineQueueEntry).join(DailyQueue, OnlineQueueEntry.queue_id == DailyQueue.id).filter(
        DailyQueue.day == today,
        OnlineQueueEntry.status.in_(['waiting', 'called']),
    ).all()

    print(f'Всего записей онлайн-очереди на {today}: {len(online_entries)}')

    # Группируем по patient_id
    patient_entries = {}
    for entry in online_entries:
        pid = entry.patient_id
        if pid not in patient_entries:
            patient_entries[pid] = []
        patient_entries[pid].append({
            'id': entry.id,
            'number': entry.number,
            'specialist_id': entry.specialist_id,
            'patient_name': entry.patient_name,
            'queue_time': entry.queue_time,
            'created_at': entry.created_at
        })

    print('\nГруппировка по patient_id:')
    for patient_id, entries in patient_entries.items():
        print(f'Patient {patient_id}: {len(entries)} записей')
        for entry in entries:
            print(f'  - ID {entry["id"]}: specialist {entry["specialist_id"]}, number {entry["number"]}, name: {entry["patient_name"]}')

    # Теперь проверим, что возвращает endpoint get_today_queues
    print('\n=== ПРОВЕРКА ЛОГИКИ get_today_queues ===')

    # Имитируем логику из get_today_queues
    from app.models.appointment import Appointment
    from app.models.clinic import Doctor
    from app.models.patient import Patient
    from app.models.visit import Visit

    # Получаем все визиты на сегодня
    visits = db.query(Visit).filter(Visit.visit_date == today).all()
    print(f'Визитов на сегодня: {len(visits)}')

    # Получаем все appointments на сегодня
    appointments = db.query(Appointment).filter(Appointment.appointment_date == today).all()
    print(f'Appointments на сегодня: {len(appointments)}')

    # Получаем онлайн-записи (уже получили выше)
    print(f'Онлайн-записей на сегодня: {len(online_entries)}')

    # Группируем по специальности как в endpoint
    queues_by_specialty = {}
    seen_patient_specialty_date = set()

    # Обрабатываем онлайн-записи
    for online_entry in online_entries:
        daily_queue = db.query(DailyQueue).filter(DailyQueue.id == online_entry.queue_id).first()
        if not daily_queue:
            continue

        doctor = db.query(Doctor).filter(Doctor.user_id == daily_queue.specialist_id).first()

        specialty = None
        if daily_queue.queue_tag:
            specialty = daily_queue.queue_tag.lower()
        elif doctor and doctor.specialty:
            specialty = doctor.specialty.lower()
        elif doctor and doctor.department:
            specialty = doctor.department.lower()
        else:
            specialty = "general"

        # Маппинг specialty
        specialty_mapping = {
            "cardio": "cardiology",
            "cardiology": "cardiology",
            "derma": "dermatology",
            "dermatology": "dermatology",
            "dentist": "stomatology",
            "stomatology": "stomatology",
            "lab": "laboratory",
            "laboratory": "laboratory",
            "ecg": "echokg",
            "echokg": "echokg",
        }
        specialty = specialty_mapping.get(specialty, specialty)

        if specialty not in queues_by_specialty:
            queues_by_specialty[specialty] = {
                "entries": [],
                "doctor": doctor,
                "doctor_id": daily_queue.specialist_id,
            }

        entry_time = online_entry.queue_time if online_entry.queue_time else online_entry.created_at

        queues_by_specialty[specialty]["entries"].append({
            "type": "online_queue",
            "data": online_entry,
            "created_at": online_entry.created_at,
            "queue_time": entry_time,
        })

    print(f'\\nСгруппировано по специальностям: {len(queues_by_specialty)} очередей')
    for specialty, queue_data in queues_by_specialty.items():
        entries = queue_data["entries"]
        print(f'  {specialty}: {len(entries)} записей')
        for i, entry in enumerate(entries):
            online_entry = entry["data"]
            print(f'    Запись {i+1}: ID={online_entry.id}, patient_id={online_entry.patient_id}, patient_name={online_entry.patient_name}')

    db.close()

if __name__ == '__main__':
    check_db_data()
