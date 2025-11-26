"""
Тестирование endpoint get_today_queues без запуска сервера
"""
import sys
from datetime import date
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.visit import Visit, VisitService
from app.models.service import Service
from app.models.patient import Patient
from sqlalchemy import and_

def test_ecg_queue():
    db = SessionLocal()
    today = date.today()

    print(f"=== Тестирование очереди ЭКГ на {today} ===\n")

    # Получаем все визиты на сегодня
    visits = db.query(Visit).filter(Visit.visit_date == today).all()
    print(f"Всего визитов на сегодня: {len(visits)}\n")

    queues_by_specialty = {}
    seen_visit_ids = set()
    seen_patient_specialty_date = set()

    # Обрабатываем Visit (копия логики из endpoint)
    for visit in visits:
        # Пропускаем если уже обработан
        if visit.id in seen_visit_ids:
            continue
        seen_visit_ids.add(visit.id)

        # Проверяем услуги визита
        visit_services = db.query(VisitService).filter(VisitService.visit_id == visit.id).all()
        service_ids = [vs.service_id for vs in visit_services]
        services = db.query(Service).filter(Service.id.in_(service_ids)).all() if service_ids else []

        # Проверяем, есть ли ЭКГ в услугах
        has_ecg = False
        ecg_services_count = 0
        non_ecg_services_count = 0

        print(f"🔍 Visit {visit.id} (patient {visit.patient_id}, dept: {visit.department}):")
        print(f"   Услуг: {len(services)}")

        for service in services:
            is_ecg_service = False
            service_name = service.name or 'N/A'
            service_code_val = service.service_code or service.code or 'N/A'
            queue_tag_val = service.queue_tag or 'N/A'

            # Проверяем по queue_tag
            if service.queue_tag == 'ecg':
                is_ecg_service = True
                print(f"   ✅ ЭКГ по queue_tag: {service_name} (код: {service_code_val})")
            # Проверяем по названию услуги
            elif service.name:
                service_name_lower = str(service.name).lower()
                if 'экг' in service_name_lower or 'ecg' in service_name_lower:
                    is_ecg_service = True
                    print(f"   ✅ ЭКГ по названию: {service_name} (код: {service_code_val})")
            # Проверяем по коду услуги
            if not is_ecg_service:
                if service.service_code:
                    service_code_upper = str(service.service_code).upper()
                    if 'ECG' in service_code_upper or 'ЭКГ' in service_code_upper:
                        is_ecg_service = True
                        print(f"   ✅ ЭКГ по service_code: {service_name} (код: {service_code_val})")
                elif service.code:
                    service_code_upper = str(service.code).upper()
                    if 'ECG' in service_code_upper or 'ЭКГ' in service_code_upper:
                        is_ecg_service = True
                        print(f"   ✅ ЭКГ по code: {service_name} (код: {service_code_val})")

            if is_ecg_service:
                has_ecg = True
                ecg_services_count += 1
            else:
                non_ecg_services_count += 1
                print(f"   ❌ Не ЭКГ: {service_name} (код: {service_code_val}, queue_tag: {queue_tag_val})")

        # Только ЭКГ: если есть ЭКГ услуги и нет не-ЭКГ услуг
        has_only_ecg = has_ecg and non_ecg_services_count == 0
        print(f"   📊 Итог: has_ecg={has_ecg}, has_only_ecg={has_only_ecg}, ЭКГ={ecg_services_count}, не-ЭКГ={non_ecg_services_count}")

        visit_date = visit.visit_date or today
        patient_id = visit.patient_id

        if has_ecg and has_only_ecg:
            # Только ЭКГ - идёт в echokg
            specialty = "echokg"
            patient_specialty_date_key = f"{patient_id}_{specialty}_{visit_date}"

            if patient_specialty_date_key in seen_patient_specialty_date:
                print(f"   ⚠️  Пропущен - дубликат по ключу {patient_specialty_date_key}")
                continue

            seen_patient_specialty_date.add(patient_specialty_date_key)

            if specialty not in queues_by_specialty:
                queues_by_specialty[specialty] = {
                    "entries": [],
                    "doctor": None,
                    "doctor_id": visit.doctor_id
                }

            visit_created_at = visit.confirmed_at or visit.created_at if hasattr(visit, 'confirmed_at') else visit.created_at
            queues_by_specialty[specialty]["entries"].append({
                "type": "visit",
                "data": visit,
                "created_at": visit_created_at,
                "filter_services": False,
                "ecg_only": False
            })
            print(f"   ✅ Добавлен в очередь echokg")

        print()

    # Выводим результаты
    print("\n=== Результаты ===")
    for specialty, data in queues_by_specialty.items():
        entries_count = len(data["entries"])
        print(f"Очередь {specialty}: {entries_count} записей")
        for entry in data["entries"]:
            visit = entry["data"]
            print(f"  - Visit {visit.id}, Patient {visit.patient_id}")

    if 'echokg' not in queues_by_specialty:
        print("\n❌ Очередь echokg НЕ СОЗДАНА!")
    elif len(queues_by_specialty['echokg']['entries']) == 0:
        print("\n❌ Очередь echokg ПУСТАЯ!")
    else:
        print(f"\n✅ Очередь echokg содержит {len(queues_by_specialty['echokg']['entries'])} записей")

    db.close()

if __name__ == "__main__":
    test_ecg_queue()
