"""
Тестирование очереди ЭКГ
"""
import sys
sys.path.insert(0, './backend')

from datetime import date
from backend.app.core.database import SessionLocal
from backend.app.models.visit import Visit, VisitService
from backend.app.models.service import Service

db = SessionLocal()
today = date.today()

print(f"=== Проверка Visit 285 ===")
visit = db.query(Visit).filter(Visit.id == 285).first()
if not visit:
    print("ERROR: Visit 285 не найден!")
    sys.exit(1)

print(f"Visit ID: {visit.id}")
print(f"Patient ID: {visit.patient_id}")
print(f"Department: {visit.department}")
print(f"Visit Date: {visit.visit_date}")
print(f"Сегодня: {today}")
print(f"Совпадает с сегодня: {visit.visit_date == today}")

# Получаем услуги
visit_services = db.query(VisitService).filter(VisitService.visit_id == visit.id).all()
print(f"\nУслуги ({len(visit_services)}):")
for vs in visit_services:
    service = db.query(Service).filter(Service.id == vs.service_id).first()
    if service:
        print(f"  - {service.name} (code: {service.service_code}, queue_tag: {service.queue_tag})")

        # Проверяем логику распознавания ЭКГ
        is_ecg = False
        if service.queue_tag == 'ecg':
            is_ecg = True
            print(f"    ✅ ЭКГ по queue_tag")
        elif service.name and ('экг' in service.name.lower() or 'ecg' in service.name.lower()):
            is_ecg = True
            print(f"    ✅ ЭКГ по названию")
        elif service.service_code and ('ECG' in service.service_code.upper() or 'ЭКГ' in service.service_code):
            is_ecg = True
            print(f"    ✅ ЭКГ по service_code")

        if not is_ecg:
            print(f"    ❌ НЕ ЭКГ")

db.close()
print("\nГотово!")
