from app.db.session import SessionLocal
from app.models.service import Service

db = SessionLocal()
services = db.query(Service).filter(Service.name.ilike("%эхо%")).all()
for s in services:
    print(f"ID={s.id}, name={s.name}, code={s.code}, service_code={s.service_code}")

if not services:
    print("No services found with 'эхо'")
    # Search for cardiology services
    cardio_services = db.query(Service).filter(Service.department_key == "cardiology").all()
    print(f"\nCardiology services: {len(cardio_services)}")
    for s in cardio_services:
        print(f"ID={s.id}, name={s.name}, code={s.code}, service_code={s.service_code}")

db.close()
