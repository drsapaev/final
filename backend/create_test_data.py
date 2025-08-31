#!/usr/bin/env python3
"""
Скрипт для создания тестовых данных
"""

from app.db.session import SessionLocal
from app.models.service import Service
from app.models.patient import Patient
from app.models.user import User
from app.core.security import get_password_hash
from datetime import datetime

def create_test_data():
    """Создание тестовых данных"""
    db = SessionLocal()
    try:
        # Создаём тестовые услуги
        services = [
            Service(
                code="CONS",
                name="Консультация врача",
                department="Терапия",
                unit="консультация",
                price=50000.0,
                active=True
            ),
            Service(
                code="ANAL",
                name="Анализ крови",
                department="Лаборатория",
                unit="анализ",
                price=25000.0,
                active=True
            ),
            Service(
                code="USI",
                name="УЗИ",
                department="Диагностика",
                unit="исследование",
                price=80000.0,
                active=True
            )
        ]
        
        for service in services:
            db.add(service)
        
        # Создаём тестового пациента
        patient = Patient(
            last_name="Иванов",
            first_name="Иван",
            middle_name="Иванович",
            birth_date=datetime(1990, 1, 1).date(),
            sex="M",  # Это будет автоматически преобразовано в gender
            phone="+998901234567",
            document_no="AA1234567"
        )
        db.add(patient)
        
        # Обновляем пользователя admin, чтобы связать его с пациентом
        admin_user = db.query(User).filter(User.username == "admin").first()
        if admin_user:
            admin_user.patient_id = 1  # ID пациента, который мы создали
        
        db.commit()
        print("✅ Тестовые данные успешно созданы")
        
    except Exception as e:
        print(f"❌ Ошибка при создании тестовых данных: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_test_data()
