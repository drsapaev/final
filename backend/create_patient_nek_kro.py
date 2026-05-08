#!/usr/bin/env python3
"""
Создание пациента "нек кро" с дерматологическими услугами
Данные пациента:
- ФИО: нек кро
- Возраст: 33 года (год рождения 1992)
- Телефон: +998 (92) 365-86-63
- Адрес: ждлорпа 654
- Услуги: D01, D12 (дерматологические)
- Тип: Платный
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import date
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def require_patient_creation_confirmation():
    if os.getenv("CONFIRM_CREATE_PATIENT_NEK_KRO") != "1":
        raise RuntimeError(
            "Refusing to run manual patient creation script. "
            "Set CONFIRM_CREATE_PATIENT_NEK_KRO=1 only for an explicit local data setup run."
        )


def require_postgres_database_url():
    from app.core.config import settings

    database_url = str(settings.DATABASE_URL).strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL must be set before creating manual patient data.")
    if database_url.lower().startswith("sqlite"):
        raise RuntimeError(
            "create_patient_nek_kro.py requires PostgreSQL; SQLite is not allowed."
        )


def create_patient_nek_kro():
    """Создание пациента и записи на приём"""
    require_patient_creation_confirmation()
    require_postgres_database_url()

    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.db.session import _get_db_url_from_env_or_settings
        from app.models.appointment import Appointment
        from app.models.patient import Patient
        from app.models.service import Service

        # Создаем подключение к базе данных
        db_url = _get_db_url_from_env_or_settings()
        engine = create_engine(db_url)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        with SessionLocal() as db:
            logger.info("🚀 Начинаем создание пациента 'нек кро'...")

            # Данные пациента
            patient_data = {
                'first_name': 'Нек',
                'last_name': 'Кро',
                'middle_name': None,
                'birth_date': date(1992, 1, 1),  # 33 года
                'phone': '+998923658663',
                'address': 'ждлорпа 654',
                'doc_type': 'passport',
                'doc_number': 'НЕИЗВЕСТЕН'
            }

            # Проверяем, существует ли пациент
            existing_patient = db.query(Patient).filter(
                Patient.first_name == patient_data['first_name'],
                Patient.last_name == patient_data['last_name'],
                Patient.phone == patient_data['phone']
            ).first()

            if existing_patient:
                logger.info(f"✅ Пациент уже существует: ID={existing_patient.id}")
                patient = existing_patient
            else:
                # Создаем нового пациента
                patient = Patient(**patient_data)
                db.add(patient)
                db.commit()
                db.refresh(patient)
                logger.info(f"✅ Создан пациент: ID={patient.id}, {patient.short_name()}")

            # Получаем дерматологические услуги
            services = db.query(Service).filter(
                Service.service_code.in_(['D01', 'D12']),
                Service.active == True
            ).all()

            if not services:
                logger.warning("❌ Не найдены услуги с кодами D01, D12. Сначала запустите seed_services.py")
                return False

            logger.info(f"✅ Найдены услуги: {[s.name for s in services]}")

            # Создаем запись на приём
            appointment_data = {
                'patient_id': patient.id,
                'department': 'dermatology',
                'appointment_date': date.today(),
                'appointment_time': '10:00',  # Можно изменить на нужное время
                'status': 'scheduled',
                'visit_type': 'paid',  # Платный
                'payment_type': 'cash',
                'services': [s.name for s in services],  # Названия услуг
                'payment_amount': sum(s.price or 0 for s in services),
                'payment_currency': 'UZS',
                'notes': 'Создано через скрипт для пациента нек кро'
            }

            # Проверяем, есть ли уже запись на сегодня
            existing_appointment = db.query(Appointment).filter(
                Appointment.patient_id == patient.id,
                Appointment.appointment_date == date.today(),
                Appointment.department == 'dermatology'
            ).first()

            if existing_appointment:
                logger.info(f"✅ Запись на приём уже существует: ID={existing_appointment.id}")
                appointment = existing_appointment
            else:
                # Создаем новую запись
                appointment = Appointment(**appointment_data)
                db.add(appointment)
                db.commit()
                db.refresh(appointment)
                logger.info(f"✅ Создана запись на приём: ID={appointment.id}")

            # Выводим итоговую информацию
            logger.info("📊 Итоговая информация:")
            logger.info(f"  👤 Пациент: {patient.short_name()} (ID: {patient.id})")
            logger.info(f"  📞 Телефон: {patient.phone}")
            logger.info(f"  📍 Адрес: {patient.address}")
            logger.info(f"  🏥 Отделение: {appointment.department}")
            logger.info(f"  📅 Дата: {appointment.appointment_date}")
            logger.info(f"  ⏰ Время: {appointment.appointment_time}")
            logger.info(f"  💰 Сумма: {appointment.payment_amount} {appointment.payment_currency}")
            logger.info(f"  🏷️ Услуги: {', '.join(appointment.services)}")
            logger.info(f"  💳 Тип оплаты: {appointment.visit_type}")

            return True

    except Exception as e:
        logger.error(f"❌ Ошибка при создании пациента: {e}")
        return False

if __name__ == "__main__":
    success = create_patient_nek_kro()
    sys.exit(0 if success else 1)
