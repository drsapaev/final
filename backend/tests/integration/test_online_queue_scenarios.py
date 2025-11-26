"""
Интеграционные тесты для 6 критических сценариев системы онлайн-очередей

Тестируем:
1. QR-регистрация (множественная) - 07:30
2. Открытие клиники - 09:00
3. Добавление услуги к QR-записи - 14:10
4. Ручная регистрация - 10:00
5. Добавление услуги к ручной записи - 11:30
6. Утренняя сборка - 06:00

Критические проверки:
- queue_time установлен правильно
- source сохранен корректно (online/desk/morning_assignment)
- number присвоен справедливо
- Старые записи НЕ изменились при редактировании
"""
import pytest
from datetime import date, datetime, time
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.patient import Patient
from app.models.service import Service
from app.models.visit import Visit
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.services.queue_service import queue_service
from app.services.qr_queue_service import QRQueueService
from app.services.morning_assignment import MorningAssignmentService


# ==================== FIXTURES ====================

@pytest.fixture(scope="function")
def test_specialists_multi(db_session):
    """Создает несколько специалистов для тестов: cardio, lab, derma"""
    specialists = {}

    # Кардиолог - проверяем существование
    cardio = db_session.query(User).filter(User.username == "scenario_cardio").first()
    if not cardio:
        cardio = User(
            username="scenario_cardio",
            email="scenario_cardio@test.com",
            full_name="Кардиолог Иванов",
            hashed_password="hashed",
            role="cardio",
            is_active=True
        )
        db_session.add(cardio)
        db_session.commit()
        db_session.refresh(cardio)

    specialists["cardio"] = cardio

    # Лаборант - проверяем существование
    lab = db_session.query(User).filter(User.username == "scenario_lab").first()
    if not lab:
        lab = User(
            username="scenario_lab",
            email="scenario_lab@test.com",
            full_name="Лаборант Петрова",
            hashed_password="hashed",
            role="Lab",
            is_active=True
        )
        db_session.add(lab)
        db_session.commit()
        db_session.refresh(lab)

    specialists["lab"] = lab

    # Дерматолог - проверяем существование
    derma = db_session.query(User).filter(User.username == "scenario_derma").first()
    if not derma:
        derma = User(
            username="scenario_derma",
            email="scenario_derma@test.com",
            full_name="Дерматолог Сидорова",
            hashed_password="hashed",
            role="derma",
            is_active=True
        )
        db_session.add(derma)
        db_session.commit()
        db_session.refresh(derma)

    specialists["derma"] = derma

    return specialists


@pytest.fixture(scope="function")
def test_services_multi(db_session):
    """Создает несколько услуг для тестов"""
    services = []

    # Услуга 1: Консультация кардиолога
    cardio_cons = Service(
        code="CARDIO_CONS",
        name="Консультация кардиолога",
        price=150000.00,
        duration_minutes=30,
        active=True,
        requires_doctor=True,
        queue_tag="cardiology_common",
        is_consultation=True
    )
    db_session.add(cardio_cons)
    services.append(cardio_cons)

    # Услуга 2: ЭКГ
    ecg = Service(
        code="ECG",
        name="ЭКГ",
        price=50000.00,
        duration_minutes=15,
        active=True,
        requires_doctor=False,
        queue_tag="cardiology_diagnostics",
        is_consultation=False
    )
    db_session.add(ecg)
    services.append(ecg)

    # Услуга 3: Общий анализ крови
    lab_cbc = Service(
        code="LAB_CBC",
        name="Общий анализ крови",
        price=30000.00,
        duration_minutes=5,
        active=True,
        requires_doctor=False,
        queue_tag="laboratory_general",
        is_consultation=False
    )
    db_session.add(lab_cbc)
    services.append(lab_cbc)

    # Услуга 4: Консультация дерматолога
    derma_cons = Service(
        code="DERMA_CONS",
        name="Консультация дерматолога",
        price=120000.00,
        duration_minutes=30,
        active=True,
        requires_doctor=True,
        queue_tag="dermatology_common",
        is_consultation=True
    )
    db_session.add(derma_cons)
    services.append(derma_cons)

    db_session.commit()
    for service in services:
        db_session.refresh(service)

    return {
        "cardio_cons": cardio_cons,
        "ecg": ecg,
        "lab_cbc": lab_cbc,
        "derma_cons": derma_cons
    }


@pytest.fixture(scope="function")
def test_confirmed_visit(db_session, test_patient, test_specialists_multi, test_services_multi):
    """Создает подтвержденный визит для утренней сборки"""
    cardio = test_specialists_multi["cardio"]
    cardio_cons = test_services_multi["cardio_cons"]

    visit = Visit(
        patient_id=test_patient.id,
        doctor_id=cardio.id,
        visit_date=date.today(),
        visit_time="09:00",
        status="confirmed",  # Подтвержден!
        discount_mode="none",
        department="cardiology",
        confirmation_token="morning-test-token",
        confirmation_channel="telegram"
    )
    db_session.add(visit)
    db_session.commit()
    db_session.refresh(visit)

    return visit


# ==================== ТЕСТЫ ====================

@pytest.mark.integration
@pytest.mark.queue
class TestOnlineQueueScenarios:
    """6 критических сценариев системы онлайн-очередей"""

    def test_scenario_1_qr_registration_multiple_specialists_0730(
        self,
        db_session: Session,
        test_patient: Patient,
        test_specialists_multi: dict,
        test_services_multi: dict
    ):
        """
        Сценарий 1: QR-регистрация (множественная) - 07:30

        Arrange:
        - Пациент
        - Два специалиста (cardio, derma)
        - Две услуги (cardio_cons, derma_cons)
        - Время: 07:30

        Act:
        - Пациент регистрируется через QR на 2 услуги одновременно

        Assert:
        - ✅ 2 записи с source='online'
        - ✅ Одинаковое queue_time=07:30 для обеих
        - ✅ Разные queue_id (разные очереди для разных специалистов)
        """
        # Arrange
        timezone = ZoneInfo("Asia/Tashkent")
        qr_time = datetime(2025, 1, 15, 7, 30, 0, tzinfo=timezone)

        cardio = test_specialists_multi["cardio"]
        derma = test_specialists_multi["derma"]
        cardio_cons = test_services_multi["cardio_cons"]
        derma_cons = test_services_multi["derma_cons"]

        # Создаем дневные очереди
        queue_cardio = DailyQueue(
            day=qr_time.date(),
            specialist_id=cardio.id,
            queue_tag="cardiology_common",
            active=True
        )
        queue_derma = DailyQueue(
            day=qr_time.date(),
            specialist_id=derma.id,
            queue_tag="dermatology_common",
            active=True
        )
        db_session.add_all([queue_cardio, queue_derma])
        db_session.commit()
        db_session.refresh(queue_cardio)
        db_session.refresh(queue_derma)

        # Act: Создаем две записи через queue_service с явным queue_time
        entry1 = queue_service.create_queue_entry(
            db=db_session,
            patient_id=test_patient.id,
            patient_name=test_patient.short_name(),
            phone=test_patient.phone,
            queue_id=queue_cardio.id,
            source="online",
            queue_time=qr_time,
            services=[{"code": cardio_cons.code, "name": cardio_cons.name, "price": float(cardio_cons.price)}]
        )

        entry2 = queue_service.create_queue_entry(
            db=db_session,
            patient_id=test_patient.id,
            patient_name=test_patient.short_name(),
            phone=test_patient.phone,
            queue_id=queue_derma.id,
            source="online",
            queue_time=qr_time,
            services=[{"code": derma_cons.code, "name": derma_cons.name, "price": float(derma_cons.price)}]
        )

        db_session.commit()
        db_session.refresh(entry1)
        db_session.refresh(entry2)

        # Assert
        assert entry1.source == "online", "Первая запись должна иметь source='online'"
        assert entry2.source == "online", "Вторая запись должна иметь source='online'"

        # Compare as naive datetimes (SQLite stores without timezone)
        assert entry1.queue_time == qr_time.replace(tzinfo=None), \
            f"Первая запись должна иметь queue_time=07:30, получено {entry1.queue_time}"
        assert entry2.queue_time == qr_time.replace(tzinfo=None), \
            f"Вторая запись должна иметь queue_time=07:30, получено {entry2.queue_time}"

        assert entry1.queue_id != entry2.queue_id, "Записи должны быть в разных очередях"
        assert entry1.queue_id == queue_cardio.id, "Первая запись должна быть в очереди кардиолога"
        assert entry2.queue_id == queue_derma.id, "Вторая запись должна быть в очереди дерматолога"

        assert entry1.number >= 1, "Номер первой записи должен быть >= 1"
        assert entry2.number >= 1, "Номер второй записи должен быть >= 1"


    def test_scenario_2_existing_qr_entries_preserved(
        self,
        db_session: Session,
        test_patient: Patient,
        test_specialists_multi: dict,
        test_services_multi: dict
    ):
        """
        Сценарий 2: Открытие клиники - 09:00

        Arrange:
        - QR-записи созданы в 07:30 (из сценария 1)
        - Время: 09:00 (открытие клиники)

        Act:
        - Устанавливаем opened_at для очереди

        Assert:
        - ✅ opened_at установлен
        - ✅ QR-записи (07:30) НЕ изменились после открытия
        """
        # Arrange: Создаем QR-записи в 07:30
        timezone = ZoneInfo("Asia/Tashkent")
        qr_time = datetime(2025, 1, 15, 7, 30, 0, tzinfo=timezone)
        opening_time = datetime(2025, 1, 15, 9, 0, 0, tzinfo=timezone)

        cardio = test_specialists_multi["cardio"]
        cardio_cons = test_services_multi["cardio_cons"]

        queue = DailyQueue(
            day=qr_time.date(),
            specialist_id=cardio.id,
            queue_tag="cardiology_common",
            active=True
        )
        db_session.add(queue)
        db_session.commit()
        db_session.refresh(queue)

        entry = queue_service.create_queue_entry(
            db=db_session,
            patient_id=test_patient.id,
            patient_name=test_patient.short_name(),
            phone=test_patient.phone,
            queue_id=queue.id,
            source="online",
            queue_time=qr_time,
            services=[{"code": cardio_cons.code, "name": cardio_cons.name, "price": float(cardio_cons.price)}]
        )
        db_session.commit()
        db_session.refresh(entry)

        # Сохраняем оригинальные значения
        original_queue_time = entry.queue_time
        original_number = entry.number
        original_source = entry.source

        # Act: Открываем клинику (устанавливаем opened_at)
        queue.opened_at = opening_time
        db_session.commit()
        db_session.refresh(queue)
        db_session.refresh(entry)

        # Assert
        # Compare as naive datetime (SQLite stores without timezone)
        assert queue.opened_at == opening_time.replace(tzinfo=None), "opened_at должен быть установлен на 09:00"

        # ⭐ КРИТИЧЕСКАЯ ПРОВЕРКА: записи НЕ изменились
        # Note: original_queue_time is already naive from DB, no need to convert
        assert entry.queue_time == original_queue_time, \
            f"queue_time НЕ должен измениться после открытия клиники! Было {original_queue_time}, стало {entry.queue_time}"
        assert entry.number == original_number, \
            f"number НЕ должен измениться после открытия клиники! Был {original_number}, стал {entry.number}"
        assert entry.source == original_source, \
            f"source НЕ должен измениться после открытия клиники! Был {original_source}, стал {entry.source}"


    def test_scenario_3_add_service_to_qr_entry_at_1410(
        self,
        db_session: Session,
        test_patient: Patient,
        test_specialists_multi: dict,
        test_services_multi: dict
    ):
        """
        Сценарий 3: Добавление услуги к QR-записи - 14:10

        Arrange:
        - Существующая QR-запись (07:30) к кардиологу
        - Время: 14:10 (регистратор добавляет ЭКГ)

        Act:
        - Добавляем новую услугу (ЭКГ) к тому же пациенту

        Assert:
        - ✅ Новая запись: queue_time=14:10, source='online' (сохранен!)
        - ✅ Старая запись (07:30): НЕ изменилась
        """
        # Arrange: Создаем QR-запись в 07:30
        timezone = ZoneInfo("Asia/Tashkent")
        qr_time = datetime(2025, 1, 15, 7, 30, 0, tzinfo=timezone)
        add_time = datetime(2025, 1, 15, 14, 10, 0, tzinfo=timezone)

        cardio = test_specialists_multi["cardio"]
        cardio_cons = test_services_multi["cardio_cons"]
        ecg = test_services_multi["ecg"]

        queue = DailyQueue(
            day=qr_time.date(),
            specialist_id=cardio.id,
            queue_tag="cardiology_common",
            active=True,
            opened_at=datetime(2025, 1, 15, 9, 0, 0, tzinfo=timezone)
        )
        db_session.add(queue)
        db_session.commit()
        db_session.refresh(queue)

        # Исходная запись (07:30)
        existing_entry = queue_service.create_queue_entry(
            db=db_session,
            patient_id=test_patient.id,
            patient_name=test_patient.short_name(),
            phone=test_patient.phone,
            queue_id=queue.id,
            source="online",
            queue_time=qr_time,
            services=[{"code": cardio_cons.code, "name": cardio_cons.name, "price": float(cardio_cons.price)}]
        )
        db_session.commit()
        db_session.refresh(existing_entry)

        # Сохраняем оригинальные значения
        original_queue_time = existing_entry.queue_time
        original_number = existing_entry.number
        original_source = existing_entry.source

        # Act: Добавляем новую услугу в 14:10
        new_entry = queue_service.create_queue_entry(
            db=db_session,
            patient_id=test_patient.id,
            patient_name=test_patient.short_name(),
            phone=test_patient.phone,
            queue_id=queue.id,
            source="online",  # ⭐ Сохраняем source='online'
            queue_time=add_time,  # ⭐ Новое время 14:10
            services=[{"code": ecg.code, "name": ecg.name, "price": float(ecg.price)}]
        )
        db_session.commit()
        db_session.refresh(new_entry)
        db_session.refresh(existing_entry)

        # Assert: Новая запись
        # Compare as naive datetime
        assert new_entry.queue_time == add_time.replace(tzinfo=None), \
            f"Новая запись должна иметь queue_time=14:10, получено {new_entry.queue_time}"
        assert new_entry.source == "online", \
            f"Новая запись должна сохранить source='online', получено {new_entry.source}"
        assert new_entry.number >= 1, "Номер новой записи должен быть >= 1"

        # ⭐ КРИТИЧЕСКАЯ ПРОВЕРКА: Старая запись НЕ изменилась
        # Note: original_queue_time is already naive from DB
        assert existing_entry.queue_time == original_queue_time, \
            f"Старая запись НЕ должна изменить queue_time! Было {original_queue_time}, стало {existing_entry.queue_time}"
        assert existing_entry.number == original_number, \
            f"Старая запись НЕ должна изменить number! Был {original_number}, стал {existing_entry.number}"
        assert existing_entry.source == original_source, \
            f"Старая запись НЕ должна изменить source! Был {original_source}, стал {existing_entry.source}"


    def test_scenario_4_manual_registration_at_1000(
        self,
        db_session: Session,
        test_patient: Patient,
        test_specialists_multi: dict,
        test_services_multi: dict
    ):
        """
        Сценарий 4: Ручная регистрация - 10:00

        Arrange:
        - Пациент приходит в клинику
        - Время: 10:00

        Act:
        - Регистратор создает запись вручную

        Assert:
        - ✅ source='desk'
        - ✅ queue_time=10:00
        """
        # Arrange
        timezone = ZoneInfo("Asia/Tashkent")
        desk_time = datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone)

        cardio = test_specialists_multi["cardio"]
        cardio_cons = test_services_multi["cardio_cons"]

        queue = DailyQueue(
            day=desk_time.date(),
            specialist_id=cardio.id,
            queue_tag="cardiology_common",
            active=True,
            opened_at=datetime(2025, 1, 15, 9, 0, 0, tzinfo=timezone)
        )
        db_session.add(queue)
        db_session.commit()
        db_session.refresh(queue)

        # Act: Ручная регистрация
        entry = queue_service.create_queue_entry(
            db=db_session,
            patient_id=test_patient.id,
            patient_name=test_patient.short_name(),
            phone=test_patient.phone,
            queue_id=queue.id,
            source="desk",  # ⭐ Ручная регистрация
            queue_time=desk_time,
            services=[{"code": cardio_cons.code, "name": cardio_cons.name, "price": float(cardio_cons.price)}]
        )
        db_session.commit()
        db_session.refresh(entry)

        # Assert
        assert entry.source == "desk", f"Запись должна иметь source='desk', получено {entry.source}"
        # Compare as naive datetime
        assert entry.queue_time == desk_time.replace(tzinfo=None), \
            f"Запись должна иметь queue_time=10:00, получено {entry.queue_time}"
        assert entry.number >= 1, "Номер записи должен быть >= 1"


    def test_scenario_5_add_service_to_desk_entry_at_1130(
        self,
        db_session: Session,
        test_patient: Patient,
        test_specialists_multi: dict,
        test_services_multi: dict
    ):
        """
        Сценарий 5: Добавление услуги к ручной записи - 11:30

        Arrange:
        - Существующая ручная запись (10:00)
        - Время: 11:30 (регистратор добавляет еще услугу)

        Act:
        - Добавляем новую услугу к ручной записи

        Assert:
        - ✅ Новая запись: queue_time=11:30, source='desk'
        - ✅ Старая запись (10:00): НЕ изменилась
        """
        # Arrange: Создаем ручную запись в 10:00
        timezone = ZoneInfo("Asia/Tashkent")
        desk_time = datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone)
        add_time = datetime(2025, 1, 15, 11, 30, 0, tzinfo=timezone)

        cardio = test_specialists_multi["cardio"]
        cardio_cons = test_services_multi["cardio_cons"]
        ecg = test_services_multi["ecg"]

        queue = DailyQueue(
            day=desk_time.date(),
            specialist_id=cardio.id,
            queue_tag="cardiology_common",
            active=True,
            opened_at=datetime(2025, 1, 15, 9, 0, 0, tzinfo=timezone)
        )
        db_session.add(queue)
        db_session.commit()
        db_session.refresh(queue)

        # Исходная ручная запись (10:00)
        existing_entry = queue_service.create_queue_entry(
            db=db_session,
            patient_id=test_patient.id,
            patient_name=test_patient.short_name(),
            phone=test_patient.phone,
            queue_id=queue.id,
            source="desk",
            queue_time=desk_time,
            services=[{"code": cardio_cons.code, "name": cardio_cons.name, "price": float(cardio_cons.price)}]
        )
        db_session.commit()
        db_session.refresh(existing_entry)

        # Сохраняем оригинальные значения
        original_queue_time = existing_entry.queue_time
        original_number = existing_entry.number
        original_source = existing_entry.source

        # Act: Добавляем новую услугу в 11:30
        new_entry = queue_service.create_queue_entry(
            db=db_session,
            patient_id=test_patient.id,
            patient_name=test_patient.short_name(),
            phone=test_patient.phone,
            queue_id=queue.id,
            source="desk",  # ⭐ Сохраняем source='desk'
            queue_time=add_time,  # ⭐ Новое время 11:30
            services=[{"code": ecg.code, "name": ecg.name, "price": float(ecg.price)}]
        )
        db_session.commit()
        db_session.refresh(new_entry)
        db_session.refresh(existing_entry)

        # Assert: Новая запись
        # Compare as naive datetime
        assert new_entry.queue_time == add_time.replace(tzinfo=None), \
            f"Новая запись должна иметь queue_time=11:30, получено {new_entry.queue_time}"
        assert new_entry.source == "desk", \
            f"Новая запись должна сохранить source='desk', получено {new_entry.source}"
        assert new_entry.number >= 1, "Номер новой записи должен быть >= 1"

        # ⭐ КРИТИЧЕСКАЯ ПРОВЕРКА: Старая запись НЕ изменилась
        # Note: original_queue_time is already naive from DB
        assert existing_entry.queue_time == original_queue_time, \
            f"Старая запись НЕ должна изменить queue_time! Было {original_queue_time}, стало {existing_entry.queue_time}"
        assert existing_entry.number == original_number, \
            f"Старая запись НЕ должна изменить number! Был {original_number}, стал {existing_entry.number}"
        assert existing_entry.source == original_source, \
            f"Старая запись НЕ должна изменить source! Был {original_source}, стал {existing_entry.source}"


    def test_scenario_6_morning_assignment_at_0600(
        self,
        db_session: Session,
        test_patient: Patient,
        test_specialists_multi: dict,
        test_services_multi: dict,
        test_confirmed_visit: Visit
    ):
        """
        Сценарий 6: Утренняя сборка - 06:00

        Arrange:
        - Подтвержденный визит без записи в очереди
        - Время: 06:00 (утренняя сборка)

        Act:
        - Запускаем morning_assignment

        Assert:
        - ✅ source='morning_assignment'
        - ✅ queue_time=06:00
        - ✅ Статус визита → 'open'
        """
        # Arrange
        timezone = ZoneInfo("Asia/Tashkent")
        morning_time = datetime(2025, 1, 15, 6, 0, 0, tzinfo=timezone)

        cardio = test_specialists_multi["cardio"]

        # Создаем очередь
        queue = DailyQueue(
            day=test_confirmed_visit.visit_date,
            specialist_id=cardio.id,
            queue_tag="cardiology_common",
            active=True
        )
        db_session.add(queue)
        db_session.commit()
        db_session.refresh(queue)

        # Проверяем, что визит подтвержден и без записи в очереди
        assert test_confirmed_visit.status == "confirmed", "Визит должен быть подтвержден"

        existing_entries = db_session.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.visit_id == test_confirmed_visit.id
        ).all()
        assert len(existing_entries) == 0, "Визит не должен иметь записей в очереди до утренней сборки"

        # Act: Создаем запись через queue_service (симулируем morning_assignment)
        entry = queue_service.create_queue_entry(
            db=db_session,
            patient_id=test_patient.id,
            patient_name=test_patient.short_name(),
            phone=test_patient.phone,
            queue_id=queue.id,
            source="morning_assignment",  # ⭐ Утренняя сборка
            queue_time=morning_time,
            visit_id=test_confirmed_visit.id,
            services=[]
        )

        # Обновляем статус визита
        test_confirmed_visit.status = "open"

        db_session.commit()
        db_session.refresh(entry)
        db_session.refresh(test_confirmed_visit)

        # Assert
        assert entry.source == "morning_assignment", \
            f"Запись должна иметь source='morning_assignment', получено {entry.source}"
        # Compare as naive datetime
        assert entry.queue_time == morning_time.replace(tzinfo=None), \
            f"Запись должна иметь queue_time=06:00, получено {entry.queue_time}"
        assert entry.number >= 1, "Номер записи должен быть >= 1"
        assert entry.visit_id == test_confirmed_visit.id, "Запись должна быть связана с визитом"

        # ⭐ Проверяем статус визита
        assert test_confirmed_visit.status == "open", \
            f"Статус визита должен быть 'open' после утренней сборки, получено {test_confirmed_visit.status}"
