"""
Комплексный скрипт для создания тестовых данных для всех флоу системы.
Создает: пользователей, врачей, отделения, услуги, пациентов, визиты, записи, EMR, платежи, очереди.
"""
import os
import sys
from datetime import date, datetime, timedelta, time
from decimal import Decimal

# Add backend to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from sqlalchemy import select
from app.db.session import SessionLocal
from app.models.user import User
from app.models.patient import Patient
from app.models.clinic import Doctor
from app.models.department import Department
from app.models.service import Service
from app.models.clinic import ServiceCategory
from app.models.appointment import Appointment
from app.models.visit import Visit
from app.models.emr import EMR
from app.models.payment import Payment
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.core.security import get_password_hash

def create_test_data():
    """Создание комплексных тестовых данных"""
    db = SessionLocal()
    
    try:
        print("=" * 80)
        print("СОЗДАНИЕ ТЕСТОВЫХ ДАННЫХ")
        print("=" * 80)
        print()
        
        # 1. Создание пользователей (врачи, регистратура, кассир)
        print("1. Создание пользователей...")
        users_data = [
            {"username": "doctor1", "email": "doctor1@clinic.com", "full_name": "Доктор Терапевт", "role": "Doctor"},
            {"username": "doctor2", "email": "doctor2@clinic.com", "full_name": "Доктор Кардиолог", "role": "cardio"},
            {"username": "doctor3", "email": "doctor3@clinic.com", "full_name": "Доктор Дерматолог", "role": "derma"},
            {"username": "registrar", "email": "registrar@clinic.com", "full_name": "Регистратор", "role": "Registrar"},
            {"username": "cashier", "email": "cashier@clinic.com", "full_name": "Кассир", "role": "Cashier"},
        ]
        
        created_users = {}
        for user_data in users_data:
            existing = db.execute(select(User).where(User.username == user_data["username"])).scalars().first()
            if not existing:
                user = User(
                    username=user_data["username"],
                    email=user_data["email"],
                    full_name=user_data["full_name"],
                    role=user_data["role"],
                    is_active=True,
                    hashed_password=get_password_hash("test123"),
                )
                db.add(user)
                db.flush()
                created_users[user_data["username"]] = user
                print(f"   ✅ Создан пользователь: {user_data['username']} ({user_data['role']})")
            else:
                created_users[user_data["username"]] = existing
                print(f"   ⚠️  Пользователь уже существует: {user_data['username']}")
        
        db.commit()
        print()
        
        # 2. Создание отделений (если модель существует)
        print("2. Создание отделений...")
        created_departments = {}
        
        if Department is None:
            print("   ⚠️  Модель Department не найдена, пропускаем создание отделений")
        else:
            departments_data = [
                {"name_ru": "Терапия", "name_uz": "Terapiya", "key": "therapy"},
                {"name_ru": "Кардиология", "name_uz": "Kardiologiya", "key": "cardiology"},
                {"name_ru": "Дерматология", "name_uz": "Dermatologiya", "key": "dermatology"},
            ]
            
            try:
                for dept_data in departments_data:
                    existing = db.execute(select(Department).where(Department.key == dept_data["key"])).scalars().first()
                    if not existing:
                        dept = Department(
                            name_ru=dept_data["name_ru"],
                            name_uz=dept_data["name_uz"],
                            key=dept_data["key"],
                            active=True,
                        )
                        db.add(dept)
                        db.flush()
                        created_departments[dept_data["key"]] = dept
                        print(f"   ✅ Создано отделение: {dept_data['name_ru']}")
                    else:
                        created_departments[dept_data["key"]] = existing
                        print(f"   ⚠️  Отделение уже существует: {dept_data['name_ru']}")
                db.commit()
            except Exception as e:
                print(f"   ⚠️  Не удалось создать отделения: {e}")
        print()
        
        # 3. Создание врачей
        print("3. Создание врачей...")
        doctors_data = [
            {"user": created_users.get("doctor1"), "specialty": "therapy", "department_key": "therapy"},
            {"user": created_users.get("doctor2"), "specialty": "cardiology", "department_key": "cardiology"},
            {"user": created_users.get("doctor3"), "specialty": "dermatology", "department_key": "dermatology"},
        ]
        
        created_doctors = []
        for doc_data in doctors_data:
            if not doc_data["user"]:
                continue
            existing = db.execute(select(Doctor).where(Doctor.user_id == doc_data["user"].id)).scalars().first()
            if not existing:
                dept = created_departments.get(doc_data["department_key"])
                dept_id = dept.id if dept else None
                doctor = Doctor(
                    user_id=doc_data["user"].id,
                    department_id=dept_id,
                    specialty=doc_data["specialty"],
                    cabinet="101",
                    price_default=Decimal("50000.00"),
                    auto_close_time=time(9, 0),  # 09:00
                    active=True,
                )
                db.add(doctor)
                db.flush()
                created_doctors.append(doctor)
                print(f"   ✅ Создан врач: {doc_data['user'].full_name} ({doc_data['specialty']})")
            else:
                created_doctors.append(existing)
                print(f"   ⚠️  Врач уже существует: {doc_data['user'].full_name}")
        
        db.commit()
        print()
        
        # 4. Создание категорий услуг
        print("4. Создание категорий услуг...")
        categories_data = [
            {"code": "K", "name_ru": "Консультации", "specialty": "therapy"},
            {"code": "C", "name_ru": "Кардиология", "specialty": "cardiology"},
            {"code": "D", "name_ru": "Дерматология", "specialty": "dermatology"},
        ]
        
        created_categories = {}
        for cat_data in categories_data:
            existing = db.execute(select(ServiceCategory).where(ServiceCategory.code == cat_data["code"])).scalars().first()
            if not existing:
                category = ServiceCategory(
                    code=cat_data["code"],
                    name_ru=cat_data["name_ru"],
                    specialty=cat_data["specialty"],
                    active=True,
                )
                db.add(category)
                db.flush()
                created_categories[cat_data["code"]] = category
                print(f"   ✅ Создана категория: {cat_data['name_ru']}")
            else:
                created_categories[cat_data["code"]] = existing
                print(f"   ⚠️  Категория уже существует: {cat_data['name_ru']}")
        
        db.commit()
        print()
        
        # 5. Создание услуг
        print("5. Создание услуг...")
        services_data = [
            {"code": "K01", "name": "Консультация терапевта", "category_code": "K", "price": 50000, "doctor": created_doctors[0] if created_doctors else None},
            {"code": "C01", "name": "Консультация кардиолога", "category_code": "C", "price": 80000, "doctor": created_doctors[1] if len(created_doctors) > 1 else None},
            {"code": "D01", "name": "Консультация дерматолога", "category_code": "D", "price": 70000, "doctor": created_doctors[2] if len(created_doctors) > 2 else None},
        ]
        
        created_services = []
        for svc_data in services_data:
            existing = db.execute(select(Service).where(Service.service_code == svc_data["code"])).scalars().first()
            if not existing:
                category = created_categories.get(svc_data["category_code"])
                service = Service(
                    code=svc_data["code"],
                    service_code=svc_data["code"],
                    name=svc_data["name"],
                    category_id=category.id if category else None,
                    category_code=svc_data["category_code"],
                    price=Decimal(str(svc_data["price"])),
                    currency="UZS",
                    doctor_id=svc_data["doctor"].id if svc_data["doctor"] else None,
                    active=True,
                )
                db.add(service)
                db.flush()
                created_services.append(service)
                print(f"   ✅ Создана услуга: {svc_data['name']} ({svc_data['code']})")
            else:
                created_services.append(existing)
                print(f"   ⚠️  Услуга уже существует: {svc_data['name']}")
        
        db.commit()
        print()
        
        # 6. Создание пациентов
        print("6. Создание пациентов...")
        patients_data = [
            {"last_name": "Иванов", "first_name": "Иван", "middle_name": "Иванович", "phone": "+998901234567"},
            {"last_name": "Петрова", "first_name": "Мария", "middle_name": "Сергеевна", "phone": "+998901234568"},
            {"last_name": "Сидоров", "first_name": "Петр", "middle_name": "Александрович", "phone": "+998901234569"},
        ]
        
        created_patients = []
        for pat_data in patients_data:
            existing = db.execute(select(Patient).where(Patient.phone == pat_data["phone"])).scalars().first()
            if not existing:
                patient = Patient(
                    last_name=pat_data["last_name"],
                    first_name=pat_data["first_name"],
                    middle_name=pat_data["middle_name"],
                    phone=pat_data["phone"],
                    birth_date=date(1990, 1, 1),
                    sex="M",
                )
                db.add(patient)
                db.flush()
                created_patients.append(patient)
                print(f"   ✅ Создан пациент: {pat_data['last_name']} {pat_data['first_name']}")
            else:
                created_patients.append(existing)
                print(f"   ⚠️  Пациент уже существует: {pat_data['last_name']} {pat_data['first_name']}")
        
        db.commit()
        print()
        
        # 7. Создание визитов
        print("7. Создание визитов...")
        today = date.today()
        created_visits = []
        
        # Получаем реальных пациентов и врачей из БД (используем последние созданные)
        existing_patients = db.execute(select(Patient).order_by(Patient.id.desc()).limit(2)).scalars().all()
        existing_doctors = db.execute(select(Doctor).order_by(Doctor.id.desc()).limit(2)).scalars().all()
        
        if not existing_patients:
            print("   ⚠️  Нет пациентов в БД для создания визитов")
        elif not existing_doctors:
            print("   ⚠️  Нет врачей в БД для создания визитов")
        else:
            for i, patient in enumerate(existing_patients):
                doctor = existing_doctors[i % len(existing_doctors)]
                visit = Visit(
                    patient_id=patient.id,
                    doctor_id=doctor.id,
                    visit_date=today,
                    visit_time="10:00",
                    status="open",
                    discount_mode="none",
                )
                db.add(visit)
                db.flush()
                created_visits.append(visit)
                print(f"   ✅ Создан визит для пациента: {patient.last_name} (врач ID: {doctor.id})")
            
            db.commit()
        print()
        
        # 8. Создание записей (appointments)
        print("8. Создание записей...")
        created_appointments = []
        
        # Используем реальных пациентов и врачей
        if not existing_patients:
            print("   ⚠️  Нет пациентов в БД для создания записей")
        else:
            for i, patient in enumerate(existing_patients):
                doctor_id = existing_doctors[i % len(existing_doctors)].id if existing_doctors else None
                appointment = Appointment(
                    patient_id=patient.id,
                    doctor_id=doctor_id,
                    appointment_date=today + timedelta(days=i+1),
                    appointment_time="14:00",
                    status="scheduled",
                )
                db.add(appointment)
                db.flush()
                created_appointments.append(appointment)
                print(f"   ✅ Создана запись для пациента: {patient.last_name}")
            
            db.commit()
        print()
        
        # 9. Создание EMR записей
        print("9. Создание EMR записей...")
        if not created_appointments:
            print("   ⚠️  Нет записей для создания EMR")
        else:
            for i, appointment in enumerate(created_appointments[:2]):
                emr = EMR(
                    appointment_id=appointment.id,
                    complaints="Головная боль",
                    diagnosis="Мигрень",
                    recommendations="Отдых, обезболивающие",
                    is_draft=False,
                )
                db.add(emr)
                print(f"   ✅ Создана EMR запись для записи #{appointment.id}")
            
            db.commit()
        print()
        
        # 10. Создание платежей
        print("10. Создание платежей...")
        if not created_visits:
            print("   ⚠️  Нет визитов для создания платежей")
        else:
            for i, visit in enumerate(created_visits):
                payment = Payment(
                    visit_id=visit.id,
                    amount=Decimal("50000.00"),
                    currency="UZS",
                    method="cash",
                    status="paid",
                    paid_at=datetime.now(),
                )
                db.add(payment)
                print(f"   ✅ Создан платеж для визита #{visit.id}")
            
            db.commit()
        print()
        
        # 11. Создание очередей
        print("11. Создание очередей...")
        if created_doctors:
            for doctor in created_doctors[:2]:
                queue = DailyQueue(
                    day=today,
                    specialist_id=doctor.id,
                    queue_tag=doctor.specialty,
                    active=True,
                    cabinet_number="101",
                )
                db.add(queue)
                db.flush()
                
                # Создание записей в очереди
                for i, patient in enumerate(created_patients[:2]):
                    entry = OnlineQueueEntry(
                        queue_id=queue.id,
                        number=i+1,
                        patient_id=patient.id,
                        patient_name=f"{patient.last_name} {patient.first_name}",
                        phone=patient.phone,
                        status="waiting",
                        queue_time=datetime.now(),
                    )
                    db.add(entry)
                
                print(f"   ✅ Создана очередь для врача: {doctor.specialty}")
        
        db.commit()
        print()
        
        print("=" * 80)
        print("✅ ТЕСТОВЫЕ ДАННЫЕ УСПЕШНО СОЗДАНЫ")
        print("=" * 80)
        print()
        print("Создано:")
        print(f"  - Пользователей: {len(created_users)}")
        print(f"  - Отделений: {len(created_departments)}")
        print(f"  - Врачей: {len(created_doctors)}")
        print(f"  - Категорий услуг: {len(created_categories)}")
        print(f"  - Услуг: {len(created_services)}")
        print(f"  - Пациентов: {len(created_patients)}")
        print(f"  - Визитов: {len(created_visits)}")
        print(f"  - Записей: {len(created_appointments)}")
        print(f"  - EMR записей: 2")
        print(f"  - Платежей: {len(created_visits)}")
        print(f"  - Очередей: {len(created_doctors[:2]) if created_doctors else 0}")
        print()
        
    except Exception as e:
        print(f"\n❌ Ошибка при создании тестовых данных: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    create_test_data()

