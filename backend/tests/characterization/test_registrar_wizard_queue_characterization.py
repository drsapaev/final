from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.crud.clinic import clinic_today
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry, QueueResource
from app.models.payment_invoice import PaymentInvoice
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit


def _create_specialist(
    db_session,
    *,
    username: str,
    email: str,
    full_name: str,
    specialty: str,
) -> Doctor:
    user = User(
        username=username,
        email=email,
        full_name=full_name,
        hashed_password="hashed",
        role="Doctor",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    doctor = Doctor(
        user_id=user.id,
        specialty=specialty,
        active=True,
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return doctor


def _create_service(
    db_session,
    *,
    code: str,
    name: str,
    queue_tag: str,
    requires_doctor: bool = True,
) -> Service:
    service = Service(
        code=code,
        name=name,
        price=100000.00,
        duration_minutes=30,
        active=True,
        requires_doctor=requires_doctor,
        queue_tag=queue_tag,
        is_consultation=requires_doctor,
    )
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)
    return service


def _create_daily_queue(
    db_session,
    *,
    specialist_id: int,
    queue_tag: str,
) -> DailyQueue:
    queue = DailyQueue(
        day=clinic_today(db_session),
        specialist_id=specialist_id,
        queue_tag=queue_tag,
        active=True,
    )
    db_session.add(queue)
    db_session.commit()
    db_session.refresh(queue)
    return queue


def _create_queue_entry(
    db_session,
    *,
    queue_id: int,
    patient_id: int,
    patient_name: str,
    phone: str | None,
    visit_id: int | None,
    number: int,
    status: str,
    source: str,
    queue_time: datetime,
) -> OnlineQueueEntry:
    entry = OnlineQueueEntry(
        queue_id=queue_id,
        patient_id=patient_id,
        patient_name=patient_name,
        phone=phone,
        visit_id=visit_id,
        number=number,
        status=status,
        source=source,
        queue_time=queue_time,
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)
    return entry


def _cart_payload(*, patient_id: int, visits: list[dict]) -> dict:
    return {
        "patient_id": patient_id,
        "discount_mode": "none",
        "payment_method": "cash",
        "visits": visits,
    }


@pytest.fixture(params=[time(18, 59, 59), time(19)], ids=["before-midnight", "at-midnight"])
def cart_clinic_day(request, monkeypatch):
    from app.api.v1.endpoints.registrar_wizard import _cart

    utc_day = datetime.now(UTC).date()
    instant = datetime.combine(utc_day, request.param, tzinfo=UTC)
    clinic_day = instant.astimezone(ZoneInfo("Asia/Tashkent")).date()

    class HostDate(date):
        @classmethod
        def today(cls):
            return utc_day

    # Patch the cart's sources only. Other date/timestamp logic still runs
    # normally, and the route exercises real writes and ticket assignment.
    monkeypatch.setattr(_cart, "date", HostDate)
    monkeypatch.setattr(_cart, "clinic_today", lambda _db: clinic_day, raising=False)
    return clinic_day


@pytest.mark.integration
@pytest.mark.queue
def test_registrar_wizard_characterization_same_day_cart_creates_desk_queue_entry(
    client,
    db_session,
    registrar_auth_headers,
    test_patient,
    test_doctor,
    test_service,
    cart_clinic_day,
):
    test_doctor.cabinet = "6"
    db_session.commit()
    response = client.post(
        "/api/v1/registrar/cart",
        headers=registrar_auth_headers,
        json=_cart_payload(
            patient_id=test_patient.id,
            visits=[
                {
                    "doctor_id": test_doctor.id,
                    "visit_date": cart_clinic_day.isoformat(),
                    "department": "cardiology",
                    "services": [
                        {
                            "service_id": test_service.id,
                            "quantity": 1,
                        }
                    ],
                }
            ],
        ),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert len(payload["visit_ids"]) == 1

    visit_id = payload["visit_ids"][0]
    visit = db_session.query(Visit).filter(Visit.id == visit_id).one()
    entry = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.visit_id == visit_id)
        .one()
    )

    assert visit.status == "open"
    assert entry.source == "desk"
    assert entry.status == "waiting"
    assert entry.queue_time is not None
    assert db_session.get(DailyQueue, entry.queue_id).day == cart_clinic_day
    assert entry.number == 1  # The cabinet is 6, but this queue is empty.
    assert payload["queue_numbers"][str(visit_id)][0]["number"] == entry.number
    assert payload["queue_numbers"][str(visit_id)][0]["queue_cabinet"] == "6"


@pytest.mark.integration
@pytest.mark.queue
def test_registrar_wizard_characterization_reuses_existing_same_queue_row(
    client,
    db_session,
    registrar_auth_headers,
    test_patient,
    test_doctor,
    test_service,
):
    daily_queue = _create_daily_queue(
        db_session,
        specialist_id=test_doctor.id,
        queue_tag=test_service.queue_tag,
    )
    preserved_queue_time = datetime.now(ZoneInfo("Asia/Tashkent")).replace(
        microsecond=0
    )
    existing_entry = _create_queue_entry(
        db_session,
        queue_id=daily_queue.id,
        patient_id=test_patient.id,
        patient_name=test_patient.short_name(),
        phone=test_patient.phone,
        visit_id=None,
        number=17,
        status="waiting",
        source="online",
        queue_time=preserved_queue_time,
    )

    response = client.post(
        "/api/v1/registrar/cart",
        headers=registrar_auth_headers,
        json=_cart_payload(
            patient_id=test_patient.id,
            visits=[
                {
                    "doctor_id": test_doctor.id,
                    "visit_date": clinic_today(db_session).isoformat(),
                    "department": "cardiology",
                    "services": [
                        {
                            "service_id": test_service.id,
                            "quantity": 1,
                        }
                    ],
                }
            ],
        ),
    )

    assert response.status_code == 200
    payload = response.json()
    visit_id = payload["visit_ids"][0]

    patient_entries = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.patient_id == test_patient.id)
        .all()
    )
    assert len(patient_entries) == 1
    assert patient_entries[0].id == existing_entry.id
    assert patient_entries[0].number == existing_entry.number
    assert patient_entries[0].queue_time == preserved_queue_time.replace(tzinfo=None)
    assert payload["queue_numbers"][str(visit_id)][0]["number"] == existing_entry.number


@pytest.mark.integration
@pytest.mark.queue
def test_registrar_wizard_characterization_same_specialist_different_queue_tags_share_one_doctor_queue(
    client,
    db_session,
    registrar_auth_headers,
    test_patient,
    test_doctor,
    test_service,
):
    """Workstream A (registrar doctor-services plan, Task 4) — обновлённый пин.

    Прежний characterization («same_specialist_different_queue_tags_create_
    multiple_rows») фиксировал раскол одного бронирования врача на записи
    по тегам: консультация «cardiology_common» + диагностика
    «cardiology_diagnostics» давали 2 очереди/2 записи/2 номера — пациент
    сидел в worklist врача дважды. Канонический контракт плана меняет
    поведение осознанно: услуги одного врача в одном бронировании делят
    ЕДИНУЮ очередь владельца-врача — одна запись, один номер; routing-тег
    записи = тег консультации (причина визита), собственные коды услуг
    сохраняются в payload записи.
    """
    diagnostics_service = _create_service(
        db_session,
        code="WIZ-DIAG-01",
        name="Wizard Diagnostics",
        queue_tag="cardiology_diagnostics",
    )

    response = client.post(
        "/api/v1/registrar/cart",
        headers=registrar_auth_headers,
        json=_cart_payload(
            patient_id=test_patient.id,
            visits=[
                {
                    "doctor_id": test_doctor.id,
                    "visit_date": clinic_today(db_session).isoformat(),
                    "department": "cardiology",
                    "services": [
                        {
                            "service_id": test_service.id,
                            "quantity": 1,
                        },
                        {
                            "service_id": diagnostics_service.id,
                            "quantity": 1,
                        },
                    ],
                }
            ],
        ),
    )

    assert response.status_code == 200
    payload = response.json()
    visit_id = payload["visit_ids"][0]

    visit_entries = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.visit_id == visit_id)
        .all()
    )
    assert (
        len(visit_entries) == 1
    ), "услуги одного врача в одном бронировании — ОДНА запись очереди (один номер)"
    assert len(payload["queue_numbers"][str(visit_id)]) == 1

    entry = visit_entries[0]
    queue = db_session.query(DailyQueue).filter(DailyQueue.id == entry.queue_id).one()
    assert (
        queue.specialist_id == test_doctor.id
    ), "очередь принадлежит врачу, тег — routing-метаданные записи"
    assert (
        queue.queue_tag == "cardiology_common"
    ), "routing-тег единой записи — тег консультации (причины визита)"
    doctor_queues = (
        db_session.query(DailyQueue)
        .filter(
            DailyQueue.day == clinic_today(db_session),
            DailyQueue.specialist_id == test_doctor.id,
            DailyQueue.active.is_(True),
        )
        .all()
    )
    assert (
        len(doctor_queues) == 1
    ), "у врача ОДНА активная очередь дня — теги не раскалывают его ось"


@pytest.mark.integration
@pytest.mark.queue
@pytest.mark.parametrize("department", ["dermatology", "stomatology"])
def test_registrar_wizard_characterization_different_specialists_create_separate_rows(
    client,
    db_session,
    registrar_auth_headers,
    test_patient,
    test_doctor,
    test_service,
    department,
):
    second_doctor = _create_specialist(
        db_session,
        username="wizard_second_doctor",
        email="wizard_second_doctor@test.local",
        full_name="Wizard Second Doctor",
        specialty=department,
    )
    test_doctor.cabinet = "6"
    second_doctor.cabinet = "12"
    second_service = _create_service(
        db_session,
        code="WIZ-DERM-01",
        name="Wizard Dermatology",
        queue_tag=department,
    )

    response = client.post(
        "/api/v1/registrar/cart",
        headers=registrar_auth_headers,
        json=_cart_payload(
            patient_id=test_patient.id,
            visits=[
                {
                    "doctor_id": test_doctor.id,
                    "visit_date": clinic_today(db_session).isoformat(),
                    "department": "cardiology",
                    "services": [
                        {
                            "service_id": test_service.id,
                            "quantity": 1,
                        }
                    ],
                },
                {
                    "doctor_id": second_doctor.id,
                    "visit_date": clinic_today(db_session).isoformat(),
                    "department": department,
                    "services": [
                        {
                            "service_id": second_service.id,
                            "quantity": 1,
                        }
                    ],
                },
            ],
        ),
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["visit_ids"]) == 2

    patient_entries = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.patient_id == test_patient.id)
        .all()
    )
    assert len(patient_entries) == 2
    assert {entry.number for entry in patient_entries} == {1}
    assert {entry.source for entry in patient_entries} == {"desk"}

    assert {entry.visit_id for entry in patient_entries} == set(payload["visit_ids"])
    assert len({entry.queue_id for entry in patient_entries}) == 2
    assert {
        assignment["queue_cabinet"]
        for assignments in payload["queue_numbers"].values()
        for assignment in assignments
    } == {"6", "12"}


@pytest.mark.integration
@pytest.mark.queue
def test_registrar_wizard_rejects_duplicate_same_day_resource_queue_visits_before_writes(
    client,
    db_session,
    monkeypatch,
    registrar_auth_headers,
    test_patient,
):
    queue_tag = "wizard_shared_procedures"
    resource = QueueResource(
        code="wizard-shared-procedures",
        queue_tag=queue_tag,
        display_name="Процедуры",
        active=True,
    )
    first_service = _create_service(
        db_session,
        code="WIZ-PROC-01",
        name="Процедура из отделения A",
        queue_tag=queue_tag,
        requires_doctor=False,
    )
    second_service = _create_service(
        db_session,
        code="WIZ-PROC-02",
        name="Процедура из отделения B",
        queue_tag=queue_tag,
        requires_doctor=False,
    )
    db_session.add(resource)
    db_session.commit()

    from app.crud import visit as visit_crud

    create_visit_calls: list[int] = []
    real_create_visit = visit_crud.create_visit

    def track_create_visit(*args, **kwargs):
        create_visit_calls.append(1)
        return real_create_visit(*args, **kwargs)

    monkeypatch.setattr(visit_crud, "create_visit", track_create_visit)

    before = {
        "visits": db_session.query(Visit)
        .filter(Visit.patient_id == test_patient.id)
        .count(),
        "invoices": db_session.query(PaymentInvoice)
        .filter(PaymentInvoice.patient_id == test_patient.id)
        .count(),
        "queues": db_session.query(DailyQueue)
        .filter(DailyQueue.queue_tag == queue_tag)
        .count(),
        "entries": db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.patient_id == test_patient.id)
        .count(),
    }

    response = client.post(
        "/api/v1/registrar/cart",
        headers=registrar_auth_headers,
        json=_cart_payload(
            patient_id=test_patient.id,
            visits=[
                {
                    "doctor_id": None,
                    "visit_date": clinic_today(db_session).isoformat(),
                    "department": "dermatology",
                    "services": [{"service_id": first_service.id, "quantity": 1}],
                },
                {
                    "doctor_id": None,
                    "visit_date": clinic_today(db_session).isoformat(),
                    "department": "procedures",
                    "services": [{"service_id": second_service.id, "quantity": 1}],
                },
            ],
        ),
    )

    assert response.status_code == 422, response.text
    assert response.json()["detail"] == (
        "Услуги очереди «Процедуры» распределены по нескольким визитам. "
        "Объедините их в один визит и повторите сохранение."
    )
    assert create_visit_calls == []
    db_session.expire_all()
    assert (
        db_session.query(Visit).filter(Visit.patient_id == test_patient.id).count()
        == before["visits"]
    )
    assert (
        db_session.query(PaymentInvoice)
        .filter(PaymentInvoice.patient_id == test_patient.id)
        .count()
        == before["invoices"]
    )
    assert (
        db_session.query(DailyQueue).filter(DailyQueue.queue_tag == queue_tag).count()
        == before["queues"]
    )
    assert (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.patient_id == test_patient.id)
        .count()
        == before["entries"]
    )


@pytest.mark.integration
@pytest.mark.queue
@pytest.mark.parametrize(
    ("queue_tag", "department"),
    [("ecg", "echokg"), ("lab", "lab"), ("wizard_grouped_procedures", "procedures")],
)
def test_registrar_wizard_accepts_same_resource_queue_services_in_one_visit(
    client,
    db_session,
    registrar_auth_headers,
    test_patient,
    queue_tag,
    department,
    cart_clinic_day,
):
    test_patient.birth_date = date(1990, 4, 17)
    test_patient.address = "SYNTHETIC-TEST address"
    db_session.add(
        QueueResource(
            code="wizard-grouped-procedures",
            queue_tag=queue_tag,
            display_name="SYNTHETIC resource",
            default_cabinet="34",
            active=True,
        )
    )
    first_service = _create_service(
        db_session,
        code="WIZ-GROUP-01",
        name="Сгруппированная процедура A",
        queue_tag=queue_tag,
        requires_doctor=False,
    )
    second_service = _create_service(
        db_session,
        code="WIZ-GROUP-02",
        name="Сгруппированная процедура B",
        queue_tag=queue_tag,
        requires_doctor=False,
    )
    db_session.commit()

    response = client.post(
        "/api/v1/registrar/cart",
        headers=registrar_auth_headers,
        json=_cart_payload(
            patient_id=test_patient.id,
            visits=[
                {
                    "doctor_id": None,
                    "visit_date": cart_clinic_day.isoformat(),
                    "department": department,
                    "services": [
                        {"service_id": first_service.id, "quantity": 1},
                        {"service_id": second_service.id, "quantity": 1},
                    ],
                }
            ],
        ),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload["visit_ids"]) == 1
    visit_id = payload["visit_ids"][0]
    entries = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.visit_id == visit_id)
        .all()
    )
    assert len(entries) == 1
    assert db_session.get(DailyQueue, entries[0].queue_id).day == cart_clinic_day
    assignment = payload["queue_numbers"][str(visit_id)][0]
    assert assignment["number"] == entries[0].number == 1
    assert assignment["queue_cabinet"] == "34"
    worklist = client.get(
        "/api/v1/registrar/queues/today",
        params={"target_date": cart_clinic_day.isoformat()},
        headers=registrar_auth_headers,
    )
    assert worklist.status_code == 200, worklist.text
    [row] = [
        row
        for queue in worklist.json()["queues"]
        for row in queue["entries"]
        if row["record_kind"] == "online_queue" and row["id"] == entries[0].id
    ]
    assert row["number"] == 1
    assert row["queue_cabinet"] == "34"
    assert row["patient_birth_year"] == 1990
    assert row["address"] == "SYNTHETIC-TEST address"


@pytest.mark.integration
@pytest.mark.queue
def test_registrar_wizard_characterization_future_day_cart_defers_queue_creation(
    client,
    db_session,
    registrar_auth_headers,
    test_patient,
    test_doctor,
    test_service,
    cart_clinic_day,
):
    tomorrow = cart_clinic_day + timedelta(days=1)

    response = client.post(
        "/api/v1/registrar/cart",
        headers=registrar_auth_headers,
        json=_cart_payload(
            patient_id=test_patient.id,
            visits=[
                {
                    "doctor_id": test_doctor.id,
                    "visit_date": tomorrow.isoformat(),
                    "department": "cardiology",
                    "services": [
                        {
                            "service_id": test_service.id,
                            "quantity": 1,
                        }
                    ],
                }
            ],
        ),
    )

    assert response.status_code == 200
    payload = response.json()
    visit_id = payload["visit_ids"][0]
    visit = db_session.query(Visit).filter(Visit.id == visit_id).one()
    entry = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.visit_id == visit_id)
        .first()
    )

    assert payload["queue_numbers"] == {}
    assert entry is None
    assert visit.status == "confirmed"
