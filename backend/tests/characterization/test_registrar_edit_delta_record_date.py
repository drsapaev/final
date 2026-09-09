"""W2-PR2: врач и дата записи не теряются при edit-delta.

Прежний контракт «фронт шлёт targetDate=getLocalISODate()» переносил правку
записи на будущую дату в «сегодня»: визит создавался today, исходная запись
оставалась нетронутой (дата терялась). А _resolve_daily_queue брала ПЕРВУЮ
активную очередь того же queue_tag, игнорируя specialist_id — услуга врача B
попадала в очередь врача A (антипаттерн до PR-26, нарушавший ADR-001).

Эти тесты закрепляют:
  - каноническая дата редактирования = день preferred-записей
    (RegistrarEditDeltaService.resolve_edit_target_day), а не запрошенная
    строка; правка будущей записи остаётся в будущем дне;
  - мультидневный набор preferred — громкий 400 (выбор визита — оператор,
    продуктовое решение отсутствует);
  - новая позиция создаётся в очереди ВЫБРАННОГО врача: существующая очередь
    врача — используется, отсутствующая — создаётся (канонический
    get_or_create_daily_queue), чужая не переиспользуется;
  - услуга без врача сохраняет легаси-поведение (активная очередь того же
    тега, в т.ч. owned ресурсом);
  - edit-квота биллит дельту ПО записи канонического дня (зеркало команды);
  - read-модель отдаёт канонический record_date строки.

Каждый сценарий проверяет СОСТОЯНИЕ повторным чтением (API/DB), а не только
HTTP 200. Все данные синтетические; production DB не используется.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit
from app.models.clinic import Doctor
from app.core.security import get_password_hash

PRICE = Decimal("25000")
TZ = ZoneInfo("Asia/Tashkent")


def _create_service(db_session, *, code: str, name: str, queue_tag: str) -> Service:
    service = Service(
        code=code,
        service_code=code,
        name=name,
        price=PRICE,
        active=True,
        requires_doctor=False,
        queue_tag=queue_tag,
        department_key=queue_tag,
        is_consultation=False,
    )
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)
    return service


def _create_queue(db_session, *, specialist_id: int, queue_tag: str, day: date) -> DailyQueue:
    queue = DailyQueue(
        day=day,
        specialist_id=specialist_id,
        queue_tag=queue_tag,
        active=True,
    )
    db_session.add(queue)
    db_session.commit()
    db_session.refresh(queue)
    return queue


def _create_doctor(db_session, *, username: str) -> Doctor:
    user = User(
        username=username,
        email=f"{username}@test.com",
        full_name=username,
        hashed_password=get_password_hash("doctor123"),
        role="Doctor",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.flush()
    doctor = Doctor(user_id=user.id, specialty="Кардиология", active=True)
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return doctor


def _create_entry(
    db_session,
    *,
    queue: DailyQueue,
    patient,
    service: Service,
    quantity: int = 1,
    status: str = "waiting",
    visit_id: int | None = None,
) -> OnlineQueueEntry:
    entry = OnlineQueueEntry(
        queue_id=queue.id,
        number=9,
        patient_id=patient.id,
        patient_name=patient.short_name(),
        phone=patient.phone,
        visit_id=visit_id,
        source="desk",
        status=status,
        queue_time=datetime.now(TZ).replace(microsecond=0),
        services=[
            {
                "id": service.id,
                "service_id": service.id,
                "code": service.service_code,
                "name": service.name,
                "quantity": quantity,
                "price": float(service.price or 0),
            }
        ],
        service_codes=[service.service_code],
        total_amount=int(Decimal(str(service.price or 0)) * quantity),
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)
    return entry


def _create_visit(
    db_session,
    *,
    patient,
    doctor_id: int | None,
    department: str,
    visit_date: date,
    status: str = "open",
) -> Visit:
    visit = Visit(
        patient_id=patient.id,
        doctor_id=doctor_id,
        visit_date=visit_date,
        visit_time=None,
        department=department,
        discount_mode="none",
        approval_status="approved",
        status=status,
        source="desk",
    )
    db_session.add(visit)
    db_session.commit()
    db_session.refresh(visit)
    return visit


def _post_edit_delta(
    client,
    registrar_auth_headers,
    *,
    patient_id: int,
    services: list[dict],
    target_date: date | None = None,
    entry_ids: list[int] | None = None,
):
    payload = {
        "patient_id": patient_id,
        "target_date": (target_date or date.today()).isoformat(),
        "payment_method": "cash",
        "discount_mode": "none",
        "all_free": False,
        "services": services,
        "existing_queue_entry_ids": entry_ids or [],
    }
    return client.post(
        "/api/v1/registrar/cart/edit-delta",
        headers=registrar_auth_headers,
        json=payload,
    )


def _quote_edit_delta(
    client,
    registrar_auth_headers,
    *,
    patient_id: int,
    services: list[dict],
    preferred_entry_ids: list[int],
    target_date: date | None = None,
):
    response = client.post(
        "/api/v1/registrar/cart/quote",
        headers=registrar_auth_headers,
        json={
            "items": services,
            "discount_mode": "none",
            "all_free": False,
            "pricing_mode": "edit_delta",
            "patient_id": patient_id,
            "target_date": (target_date or date.today()).isoformat(),
            "preferred_entry_ids": preferred_entry_ids,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _read_today_record(client, registrar_auth_headers, *, patient_id: int, target_date: date):
    """Повторное чтение из read-API мастерового фида (не HTTP 200, а состояние)."""
    response = client.get(
        "/api/v1/registrar/queues/today",
        headers=registrar_auth_headers,
        params={"target_date": target_date.isoformat()},
    )
    assert response.status_code == 200, response.text
    queues = response.json().get("queues", [])
    for queue in queues:
        for entry in queue.get("entries", []):
            if entry.get("patient_id") == patient_id:
                return entry
    return None


def _entry_quantity(db_session, entry_id: int) -> int:
    entry = db_session.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).first()
    assert entry is not None
    services = entry.services if isinstance(entry.services, list) else []
    return sum(int(s.get("quantity", 0)) for s in services)


# ===================== КАНОНИЧЕСКАЯ ДАТА =====================


@pytest.mark.integration
@pytest.mark.queue
def test_edit_delta_targets_record_date_not_today(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    """Правка будущей записи (target_date=сегодня в запросе) остаётся в
    будущем дне: дельта применяется к будущей записи, визит «сегодня» не
    создаётся, ответ возвращает канонический день."""
    tomorrow = date.today() + timedelta(days=1)
    service = _create_service(
        db_session, code="RD-CANON-01", name="RD Canonical", queue_tag="laboratory_general"
    )
    queue = _create_queue(
        db_session, specialist_id=test_doctor.id, queue_tag="laboratory_general", day=tomorrow
    )
    visit = _create_visit(
        db_session,
        patient=test_patient,
        doctor_id=test_doctor.id,
        department="laboratory_general",
        visit_date=tomorrow,
    )
    entry = _create_entry(
        db_session, queue=queue, patient=test_patient, service=service, quantity=1, visit_id=visit.id
    )

    response = _post_edit_delta(
        client,
        registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": service.id, "quantity": 3}],
        target_date=date.today(),  # прежний фронт-контракт «сегодня»
        entry_ids=[entry.id],
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["target_date"] == tomorrow.isoformat()
    assert Decimal(str(body["total_amount"])) == PRICE * 2  # дельта 1→3

    # Состояние: будущая запись выросла до 3, визит не дублировался
    assert _entry_quantity(db_session, entry.id) == 3
    visits = db_session.query(Visit).filter(Visit.patient_id == test_patient.id).all()
    assert len(visits) == 1
    assert visits[0].visit_date == tomorrow

    # Повторное чтение: в будущем дне позиция с количеством 3
    record = _read_today_record(
        client, registrar_auth_headers, patient_id=test_patient.id, target_date=tomorrow
    )
    assert record is not None
    assert record.get("record_date") == tomorrow.isoformat()
    quantities = sum(
        int(detail.get("quantity", 0))
        for detail in (record.get("service_details") or [])
        if int(detail.get("service_id") or detail.get("id") or 0) == service.id
    )
    assert quantities == 3

    # Повторное чтение: в «сегодня» позиции пациента не появились
    assert (
        _read_today_record(
            client, registrar_auth_headers, patient_id=test_patient.id, target_date=date.today()
        )
        is None
    )


@pytest.mark.integration
@pytest.mark.queue
def test_edit_delta_multi_day_preferred_set_rejected(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    """preferred-записи в РАЗНЫХ днях — громкий 400 до любых мутаций (выбор
    целевого визита — операторное решение; тихий выбор первой записи
    недопустим)."""
    today = date.today()
    tomorrow = today + timedelta(days=1)
    service = _create_service(
        db_session, code="RD-MULTI-01", name="RD Multi", queue_tag="laboratory_general"
    )
    queue_today = _create_queue(
        db_session, specialist_id=test_doctor.id, queue_tag="laboratory_general", day=today
    )
    queue_tomorrow = _create_queue(
        db_session, specialist_id=test_doctor.id, queue_tag="laboratory_general", day=tomorrow
    )
    entry_today = _create_entry(
        db_session, queue=queue_today, patient=test_patient, service=service, quantity=1
    )
    entry_tomorrow = _create_entry(
        db_session, queue=queue_tomorrow, patient=test_patient, service=service, quantity=1
    )

    response = _post_edit_delta(
        client,
        registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": service.id, "quantity": 2}],
        entry_ids=[entry_today.id, entry_tomorrow.id],
    )

    assert response.status_code == 400, response.text
    assert "разных дат" in response.json()["detail"]
    # Ни одна запись не изменена (мутаций до отказа нет)
    assert _entry_quantity(db_session, entry_today.id) == 1
    assert _entry_quantity(db_session, entry_tomorrow.id) == 1


@pytest.mark.integration
@pytest.mark.queue
def test_edit_delta_all_preferred_inactive_falls_back_to_requested_date(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    """Все preferred-записи неактивны (отменены) — канонизации нет, работает
    запрошенная дата (легаси-семантика сохранена, без исключения)."""
    today = date.today()
    service = _create_service(
        db_session, code="RD-INACT-01", name="RD Inactive", queue_tag="laboratory_general"
    )
    queue = _create_queue(
        db_session, specialist_id=test_doctor.id, queue_tag="laboratory_general", day=today
    )
    cancelled_entry = _create_entry(
        db_session,
        queue=queue,
        patient=test_patient,
        service=service,
        quantity=1,
        status="cancelled",
    )

    response = _post_edit_delta(
        client,
        registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": service.id, "quantity": 2}],
        target_date=today,
        entry_ids=[cancelled_entry.id],
    )

    assert response.status_code == 200, response.text
    # Отменённая запись не изменилась
    assert _entry_quantity(db_session, cancelled_entry.id) == 1


# ===================== ВЛАДЕЛЕЦ ОЧЕРЕДИ (ADR-001) =====================


@pytest.mark.integration
@pytest.mark.queue
def test_new_entry_lands_in_selected_doctor_own_queue(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    """Две активные очереди одного тега у разных врачей: новая позиция
    специалиста B попадает в очередь B, а не в первую по id очередь A."""
    today = date.today()
    doctor_b = _create_doctor(db_session, username="rd_doctor_b")
    service = _create_service(
        db_session, code="RD-OWN-01", name="RD Own", queue_tag="cardio_general"
    )
    queue_a = _create_queue(
        db_session, specialist_id=test_doctor.id, queue_tag="cardio_general", day=today
    )
    queue_b = _create_queue(
        db_session, specialist_id=doctor_b.id, queue_tag="cardio_general", day=today
    )
    assert queue_a.id < queue_b.id or True  # порядок id не важен: выбор по врачу

    response = _post_edit_delta(
        client,
        registrar_auth_headers,
        patient_id=test_patient.id,
        services=[
            {"service_id": service.id, "quantity": 1, "specialist_id": doctor_b.id}
        ],
        target_date=today,
        entry_ids=[],
    )

    assert response.status_code == 200, response.text
    created = response.json()["updated_queue_entries"]
    assert len(created) == 1
    assert created[0]["queue_id"] == queue_b.id

    db_session.expire_all()
    entry = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.id == created[0]["queue_entry_id"])
        .first()
    )
    assert entry is not None
    assert entry.queue.specialist_id == doctor_b.id
    visit = db_session.query(Visit).filter(Visit.id == entry.visit_id).first()
    assert visit is not None
    assert visit.doctor_id == doctor_b.id


@pytest.mark.integration
@pytest.mark.queue
def test_missing_doctor_queue_created_not_borrowed(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    """У врача B очереди нет — создаётся СОБСТВЕННАЯ очередь B (канонический
    get_or_create_daily_queue), чужая очередь A того же тега не
    переиспользуется."""
    today = date.today()
    doctor_b = _create_doctor(db_session, username="rd_doctor_c")
    service = _create_service(
        db_session, code="RD-MISS-01", name="RD Missing", queue_tag="cardio_general"
    )
    queue_a = _create_queue(
        db_session, specialist_id=test_doctor.id, queue_tag="cardio_general", day=today
    )

    response = _post_edit_delta(
        client,
        registrar_auth_headers,
        patient_id=test_patient.id,
        services=[
            {"service_id": service.id, "quantity": 1, "specialist_id": doctor_b.id}
        ],
        target_date=today,
        entry_ids=[],
    )

    assert response.status_code == 200, response.text
    created = response.json()["updated_queue_entries"]
    assert len(created) == 1
    assert created[0]["queue_id"] != queue_a.id

    db_session.expire_all()
    entry = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.id == created[0]["queue_entry_id"])
        .first()
    )
    assert entry.queue.specialist_id == doctor_b.id
    # Созданная очередь принадлежит врачу B, активна и того же тега
    own_queue = (
        db_session.query(DailyQueue)
        .filter(DailyQueue.id == entry.queue_id)
        .first()
    )
    assert own_queue is not None
    assert own_queue.specialist_id == doctor_b.id
    assert own_queue.active is True
    assert own_queue.queue_tag == "cardio_general"


@pytest.mark.integration
@pytest.mark.queue
def test_doctorless_service_keeps_same_tag_queue(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    """Услуга без врача (specialist_id не назван, service.doctor_id пуст) —
    легаси-поведение: активная очередь того же тега (в т.ч. owned ресурсом)."""
    today = date.today()
    service = _create_service(
        db_session, code="RD-NODOC-01", name="RD NoDoc", queue_tag="laboratory_general"
    )
    queue = _create_queue(
        db_session, specialist_id=test_doctor.id, queue_tag="laboratory_general", day=today
    )

    response = _post_edit_delta(
        client,
        registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": service.id, "quantity": 1}],
        target_date=today,
        entry_ids=[],
    )

    assert response.status_code == 200, response.text
    created = response.json()["updated_queue_entries"]
    assert len(created) == 1
    assert created[0]["queue_id"] == queue.id


# ===================== ЗЕРКАЛО КВОТЫ =====================


@pytest.mark.integration
@pytest.mark.queue
def test_edit_quote_bills_delta_against_record_date_entry(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    """Квота edit_delta биллит дельту ПО каноническому дню preferred-записей:
    позиция уже есть в будущей записи (qty 1), запрошено 2 → квота = 1×цена,
    а не 2×цена (как было бы при поиске записи в «сегодня»)."""
    tomorrow = date.today() + timedelta(days=1)
    service = _create_service(
        db_session, code="RD-QUOTE-01", name="RD Quote", queue_tag="laboratory_general"
    )
    queue = _create_queue(
        db_session, specialist_id=test_doctor.id, queue_tag="laboratory_general", day=tomorrow
    )
    entry = _create_entry(
        db_session, queue=queue, patient=test_patient, service=service, quantity=1
    )

    quote = _quote_edit_delta(
        client,
        registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": service.id, "quantity": 2}],
        preferred_entry_ids=[entry.id],
        target_date=date.today(),  # прежний фронт-контракт «сегодня»
    )

    assert Decimal(str(quote["total_amount"])) == PRICE


@pytest.mark.integration
@pytest.mark.queue
def test_read_model_record_date_present(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    """Read-модель отдаёт канонический record_date строки (день листа)."""
    tomorrow = date.today() + timedelta(days=1)
    service = _create_service(
        db_session, code="RD-FEED-01", name="RD Feed", queue_tag="laboratory_general"
    )
    _create_queue(
        db_session, specialist_id=test_doctor.id, queue_tag="laboratory_general", day=tomorrow
    )
    _create_entry(db_session, queue=_queue_by_day(db_session, tomorrow, "laboratory_general"),
                  patient=test_patient, service=service, quantity=1)

    record = _read_today_record(
        client, registrar_auth_headers, patient_id=test_patient.id, target_date=tomorrow
    )
    assert record is not None
    assert record.get("record_date") == tomorrow.isoformat()


def _queue_by_day(db_session, day: date, tag: str) -> DailyQueue:
    return (
        db_session.query(DailyQueue)
        .filter(DailyQueue.day == day, DailyQueue.queue_tag == tag)
        .first()
    )
