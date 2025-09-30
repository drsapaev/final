#!/usr/bin/env python3
"""
Скрипт для создания тестовых записей в базе данных для демонстрации работы панели регистратуры
"""

import sys
import os
sys.path.append('backend')

from datetime import date, datetime, time
from app.db.session import SessionLocal
from app.models.patient import Patient
from app.models.visit import Visit, VisitService
from app.models.service import Service
from app.models.user import User
from app.models.clinic import Doctor

def create_test_data():
    """Создает тестовые данные для демонстрации"""
    db = SessionLocal()

    try:
        # Создаем тестового пациента если его нет
        patient = db.query(Patient).filter(Patient.phone == "+998901234567").first()
        if not patient:
            patient = Patient(
                first_name="Иван",
                last_name="Иванов",
                middle_name="Иванович",
                phone="+998901234567",
                birth_date=date(1985, 5, 15),
                address="ул. Навои, д. 15, кв. 23"
            )
            db.add(patient)
            db.commit()
            db.refresh(patient)
            print(f"✅ Создан пациент: {patient.short_name()}")

        # Создаем тестового врача если его нет
        doctor_user = db.query(User).filter(User.username == "doctor_cardio").first()
        if not doctor_user:
            doctor_user = User(
                username="doctor_cardio",
                email="doctor@example.com",
                hashed_password="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LeehfX3VSPQMSrQe",  # password
                full_name="Доктор Кардиолог",
                is_active=True
            )
            db.add(doctor_user)
            db.commit()
            db.refresh(doctor_user)

            doctor = Doctor(
                user_id=doctor_user.id,
                specialty="cardiology",
                cabinet="101",
                price_default=50000
            )
            db.add(doctor)
            db.commit()
            print(f"✅ Создан врач: {doctor.user.full_name}")

        # Получаем врача
        doctor = db.query(Doctor).filter(Doctor.user_id == doctor_user.id).first()
        if not doctor:
            print("❌ Не найден врач")
            return

        # Создаем тестовые услуги если их нет
        cardio_service = db.query(Service).filter(Service.name == "Консультация кардиолога").first()
        if not cardio_service:
            cardio_service = Service(
                name="Консультация кардиолога",
                code="K01",
                price=50000,
                category_code="K",
                queue_tag="cardiology_common"
            )
            db.add(cardio_service)
            db.commit()
            db.refresh(cardio_service)
            print(f"✅ Создана услуга: {cardio_service.name}")

        # Создаем тестовые записи на сегодня
        today = date.today()

        # Запись 1: Подтвержденная онлайн-запись
        visit1 = Visit(
            patient_id=patient.id,
            doctor_id=doctor.id,
            department="cardiology",
            visit_date=today,
            visit_time=time(10, 0),
            status="confirmed",
            discount_mode="paid",
            confirmed_at=datetime.now(),
            confirmed_by="telegram_123456"
        )
        db.add(visit1)
        db.commit()
        db.refresh(visit1)

        # Добавляем услугу к визиту
        visit_service1 = VisitService(
            visit_id=visit1.id,
            service_id=cardio_service.id,
            qty=1,
            price=50000
        )
        db.add(visit_service1)
        db.commit()

        print(f"✅ Создана подтвержденная запись на сегодня: {visit1.id}")

        # Запись 2: Ожидает подтверждения
        visit2 = Visit(
            patient_id=patient.id,
            doctor_id=doctor.id,
            department="cardiology",
            visit_date=today,
            visit_time=time(11, 0),
            status="pending_confirmation",
            discount_mode="paid"
        )
        db.add(visit2)
        db.commit()
        db.refresh(visit2)

        visit_service2 = VisitService(
            visit_id=visit2.id,
            service_id=cardio_service.id,
            qty=1,
            price=50000
        )
        db.add(visit_service2)
        db.commit()

        print(f"✅ Создана запись ожидающая подтверждения: {visit2.id}")

        # Создаем еще одного пациента для разнообразия
        patient2 = Patient(
            first_name="Мария",
            last_name="Петрова",
            middle_name="Сергеевна",
            phone="+998909876543",
            birth_date=date(1990, 8, 20),
            address="ул. Амира Темура, д. 45"
        )
        db.add(patient2)
        db.commit()
        db.refresh(patient2)

        # Запись 3: От другого пациента
        visit3 = Visit(
            patient_id=patient2.id,
            doctor_id=doctor.id,
            department="cardiology",
            visit_date=today,
            visit_time=time(14, 0),
            status="confirmed",
            discount_mode="paid",
            confirmed_at=datetime.now(),
            confirmed_by="registrar_1"
        )
        db.add(visit3)
        db.commit()
        db.refresh(visit3)

        visit_service3 = VisitService(
            visit_id=visit3.id,
            service_id=cardio_service.id,
            qty=1,
            price=50000
        )
        db.add(visit_service3)
        db.commit()

        print(f"✅ Создана запись от другого пациента: {visit3.id}")

        print("✅ Тестовые данные созданы успешно!")
        print(f"Всего записей на сегодня: {len(db.query(Visit).filter(Visit.visit_date == today).all())}")

    except Exception as e:
        print(f"❌ Ошибка создания тестовых данных: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_test_data()
