#!/usr/bin/env python3
"""
Создание тестовых данных для EMR
"""
import sys
import os
import json
from datetime import datetime

# Добавляем корневую директорию проекта в sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'app')))

def require_test_emr_data_confirmation():
    if os.getenv("CONFIRM_CREATE_TEST_EMR_DATA") != "1":
        raise RuntimeError(
            "Refusing to create EMR test data. "
            "Set CONFIRM_CREATE_TEST_EMR_DATA=1 only for an explicit local seed run."
        )


def require_postgres_database_url():
    from app.core.config import settings

    database_url = str(settings.DATABASE_URL).strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL must be set before creating EMR test data.")
    if database_url.lower().startswith("sqlite"):
        raise RuntimeError("create_test_emr_data.py requires PostgreSQL; SQLite is not allowed.")


def create_test_data():
    require_test_emr_data_confirmation()
    require_postgres_database_url()

    from app.db.session import SessionLocal
    from app.models.emr import EMR
    from app.models.emr_version import EMRVersion
    from app.models.lab import LabOrder, LabResult

    """Создать тестовые данные для EMR"""
    print("🔄 СОЗДАНИЕ ТЕСТОВЫХ ДАННЫХ ДЛЯ EMR")
    print("=" * 40)
    
    try:
        db = SessionLocal()
        
        # Создаем тестовый EMR
        print("1. Создание тестового EMR...")
        test_emr = EMR(
            appointment_id=1,
            complaints="боль в груди, одышка",
            anamnesis="Жалобы на боли в области сердца в течение 2 недель",
            examination="ЧСС 82, АД 140/90, дыхание везикулярное",
            diagnosis="Стенокардия",
            icd10="I20.9",
            recommendations="Контроль АД, консультация кардиолога",
            procedures=json.dumps([{"name": "ЭКГ", "status": "выполнено"}]),
            attachments=json.dumps([]),
            vital_signs=json.dumps({
                "blood_pressure": "140/90",
                "heart_rate": 82,
                "temperature": 36.6,
                "weight": 75.0
            }),
            lab_results=json.dumps({}),
            imaging_results=json.dumps({}),
            medications=json.dumps([]),
            allergies=json.dumps([]),
            family_history=json.dumps({}),
            social_history=json.dumps({}),
            ai_suggestions=json.dumps({}),
            ai_confidence=0.85,
            template_id=1,
            specialty="cardiology",
            is_draft=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            saved_at=datetime.utcnow()
        )
        
        db.add(test_emr)
        db.flush()
        emr_id = test_emr.id
        print(f"   ✅ EMR создан с ID: {emr_id}")
        
        # Создаем тестовые версии EMR
        print("2. Создание тестовых версий...")
        version1 = EMRVersion(
            emr_id=emr_id,
            version_number=1,
            data=json.dumps({
                "complaints": "усталость",
                "diagnosis": "астения"
            }),
            change_type="created",
            change_description="Первичная запись",
            changed_by=1,
            is_current=False,
            created_at=datetime.utcnow()
        )
        
        version2 = EMRVersion(
            emr_id=emr_id,
            version_number=2,
            data=json.dumps({
                "complaints": "боль в груди",
                "diagnosis": "стенокардия",
                "icd10": "I20.9"
            }),
            change_type="updated",
            change_description="Обновление диагноза",
            changed_by=1,
            is_current=True,
            created_at=datetime.utcnow()
        )
        
        db.add(version1)
        db.add(version2)
        print(f"   ✅ Версии созданы")
        
        # Создаем тестовые лабораторные заказы и результаты
        print("3. Создание тестовых лабораторных данных...")
        lab_order = LabOrder(
            patient_id=1,
            status="done",
            notes="Биохимический анализ крови",
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow()
        )
        
        db.add(lab_order)
        db.flush()
        order_id = lab_order.id
        
        # Создаем результаты анализов
        lab_results = [
            LabResult(
                order_id=order_id,
                test_code="glucose",
                test_name="Глюкоза",
                value="6.2",
                unit="mmol/L",
                ref_range="3.9-5.6",
                abnormal=True,
                notes="Повышен, требует контроля",
                created_at=datetime.utcnow()
            ),
            LabResult(
                order_id=order_id,
                test_code="cholesterol",
                test_name="Холестерин общий",
                value="4.8",
                unit="mmol/L",
                ref_range="0-5.2",
                abnormal=False,
                notes="В пределах нормы",
                created_at=datetime.utcnow()
            ),
            LabResult(
                order_id=order_id,
                test_code="hemoglobin",
                test_name="Гемоглобин",
                value="110",
                unit="g/L",
                ref_range="120-160",
                abnormal=True,
                notes="Снижен, анемия",
                created_at=datetime.utcnow()
            )
        ]
        
        for result in lab_results:
            db.add(result)
        
        print(f"   ✅ Лабораторные данные созданы")
        
        # Сохраняем все изменения
        db.commit()
        print("✅ Все тестовые данные успешно созданы")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка создания тестовых данных: {e}")
        db.rollback()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    success = create_test_data()
    sys.exit(0 if success else 1)
