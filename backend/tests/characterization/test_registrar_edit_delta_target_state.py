"""W2-PR1: полноценное редактирование существующих услуг (target-state delta).

Прежняя семантика edit-delta была append-only с max(target − existing, 0):
уменьшение количества, смена врача существующей позиции и правка корзины без
добавления НОВОЙ услуги молча не применялись (сохранение отвечало success).
Эти тесты закрепляют целевую семантику:
  - позиция несёт ПОЛНОЕ целевое количество (рост и снижение);
  - снижение допустимо только для неоплаченных и не выполненных позиций;
  - смена врача существующей позиции отвергается с явной причиной (контракт
    переноса — отдельная операция, wave2 PR2);
  - одинаковое услуга/врач не сливаются только по service_id (ADR-001);
  - отсутствие изменений — настоящий no-op;
  - каждое сохранение проверяется повторным чтением через API
    (/registrar/queues/today), а не только через HTTP 200.

Все данные синтетические; production DB не используется.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.service import Service
from app.models.visit import Visit, VisitService
from app.models.user import User
from app.models.clinic import Doctor
from app.core.security import get_password_hash
from app.services.service_mapping import normalize_service_code

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


def _create_doctor(db_session, *, username: str) -> Doctor:
    """W2-PR2: реальный второй врач — get_or_create_daily_queue проверяет
    существование Doctor (FK-целостность ADR-001), фиктивный id больше не
    проходит."""
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


def _create_visit(
    db_session,
    *,
    patient,
    doctor_id: int | None,
    department: str,
    status: str = "open",
) -> Visit:
    visit = Visit(
        patient_id=patient.id,
        doctor_id=doctor_id,
        visit_date=date.today(),
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


def _attach_visit_service(
    db_session,
    *,
    visit: Visit,
    service: Service,
    quantity: int,
) -> VisitService:
    vs = VisitService(
        visit_id=visit.id,
        service_id=service.id,
        code=service.service_code,
        name=service.name,
        qty=quantity,
        price=service.price,
        currency=service.currency or "UZS",
    )
    db_session.add(vs)
    db_session.commit()
    db_session.refresh(vs)
    return vs


def _create_pending_invoice(
    db_session,
    *,
    patient,
    visit: Visit,
    amount: Decimal,
) -> PaymentInvoice:
    invoice = PaymentInvoice(
        patient_id=patient.id,
        total_amount=amount,
        currency="UZS",
        status="pending",
        payment_method="cash",
        notes="target-state-test",
    )
    db_session.add(invoice)
    db_session.flush()
    db_session.add(
        PaymentInvoiceVisit(
            invoice_id=invoice.id,
            visit_id=visit.id,
            visit_amount=amount,
        )
    )
    db_session.commit()
    db_session.refresh(invoice)
    return invoice


def _post_edit_delta(
    client,
    registrar_auth_headers,
    *,
    patient_id: int,
    services: list[dict],
    target_date: date | None = None,
    entry_ids: list[int] | None = None,
    quote_token: str | None = None,
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
    if quote_token:
        payload["quote_token"] = quote_token
    return client.post(
        "/api/v1/registrar/cart/edit-delta",
        headers=registrar_auth_headers,
        json=payload,
    )


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


def _quote_edit_delta(
    client,
    registrar_auth_headers,
    *,
    patient_id: int,
    services: list[dict],
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
            "target_date": date.today().isoformat(),
            "preferred_entry_ids": [],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


# ===================== РОСТ КОЛИЧЕСТВА =====================


@pytest.mark.integration
@pytest.mark.queue
def test_edit_delta_quantity_increase_1_to_3_persists_everywhere(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    service = _create_service(
        db_session, code="TSQ-INC-01", name="TS Increase", queue_tag="laboratory_general"
    )
    queue = _create_queue(
        db_session, specialist_id=test_doctor.id, queue_tag="laboratory_general", day=date.today()
    )
    visit = _create_visit(
        db_session, patient=test_patient, doctor_id=test_doctor.id, department="laboratory_general"
    )
    vs = _attach_visit_service(db_session, visit=visit, service=service, quantity=1)
    entry = _create_entry(
        db_session, queue=queue, patient=test_patient, service=service, quantity=1, visit_id=visit.id
    )
    invoice = _create_pending_invoice(
        db_session, patient=test_patient, visit=visit, amount=PRICE
    )

    response = _post_edit_delta(
        client,
        registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": service.id, "quantity": 3}],
        entry_ids=[entry.id],
    )

    assert response.status_code == 200, response.text
    assert Decimal(str(response.json()["total_amount"])) == PRICE * 2  # дельта 1→3 = 2×цена

    # Повторное чтение из API: количество реально изменилось во всех местах
    record = _read_today_record(
        client, registrar_auth_headers, patient_id=test_patient.id, target_date=date.today()
    )
    assert record is not None
    detail = next(d for d in record["service_details"] if d["id"] == service.id)
    assert detail["quantity"] == 3

    db_session.refresh(entry)
    db_session.refresh(vs)
    db_session.refresh(invoice)
    payload = next(p for p in entry.services if p.get("service_id") == service.id)
    assert payload["quantity"] == 3
    assert vs.qty == 3
    assert Decimal(str(entry.total_amount)) == PRICE * 3
    assert Decimal(str(invoice.total_amount)) == PRICE * 3


# ===================== СНИЖЕНИЕ КОЛИЧЕСТВА =====================


@pytest.mark.integration
@pytest.mark.queue
def test_edit_delta_quantity_decrease_3_to_1_persists_and_reduces_invoice(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    service = _create_service(
        db_session, code="TSQ-DEC-01", name="TS Decrease", queue_tag="laboratory_general"
    )
    queue = _create_queue(
        db_session, specialist_id=test_doctor.id, queue_tag="laboratory_general", day=date.today()
    )
    visit = _create_visit(
        db_session, patient=test_patient, doctor_id=test_doctor.id, department="laboratory_general"
    )
    vs = _attach_visit_service(db_session, visit=visit, service=service, quantity=3)
    entry = _create_entry(
        db_session, queue=queue, patient=test_patient, service=service, quantity=3, visit_id=visit.id
    )
    invoice = _create_pending_invoice(
        db_session, patient=test_patient, visit=visit, amount=PRICE * 3
    )
    db_session.refresh(entry)
    link = (
        db_session.query(PaymentInvoiceVisit)
        .filter(PaymentInvoiceVisit.invoice_id == invoice.id)
        .first()
    )

    response = _post_edit_delta(
        client,
        registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": service.id, "quantity": 1}],
        entry_ids=[entry.id],
    )

    assert response.status_code == 200, response.text
    # Знаковая дельта: 1 − 3 = −2 → отрицательная сумма в ответе
    assert Decimal(str(response.json()["total_amount"])) == -PRICE * 2

    record = _read_today_record(
        client, registrar_auth_headers, patient_id=test_patient.id, target_date=date.today()
    )
    detail = next(d for d in record["service_details"] if d["id"] == service.id)
    assert detail["quantity"] == 1

    db_session.refresh(entry)
    db_session.refresh(vs)
    db_session.refresh(invoice)
    db_session.refresh(link)
    payload = next(p for p in entry.services if p.get("service_id") == service.id)
    assert payload["quantity"] == 1
    assert vs.qty == 1
    assert Decimal(str(entry.total_amount)) == PRICE
    assert Decimal(str(invoice.total_amount)) == PRICE
    assert Decimal(str(link.visit_amount)) == PRICE
    assert invoice.status == "pending"


@pytest.mark.integration
@pytest.mark.queue
def test_edit_delta_decrease_with_paid_invoice_is_rejected_and_state_unchanged(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    service = _create_service(
        db_session, code="TSQ-PAID-01", name="TS Paid", queue_tag="laboratory_general"
    )
    queue = _create_queue(
        db_session, specialist_id=test_doctor.id, queue_tag="laboratory_general", day=date.today()
    )
    visit = _create_visit(
        db_session, patient=test_patient, doctor_id=test_doctor.id, department="laboratory_general"
    )
    vs = _attach_visit_service(db_session, visit=visit, service=service, quantity=3)
    entry = _create_entry(
        db_session, queue=queue, patient=test_patient, service=service, quantity=3, visit_id=visit.id
    )
    invoice = _create_pending_invoice(
        db_session, patient=test_patient, visit=visit, amount=PRICE * 3
    )
    invoice.status = "paid"
    db_session.commit()
    db_session.refresh(invoice)

    response = _post_edit_delta(
        client,
        registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": service.id, "quantity": 1}],
        entry_ids=[entry.id],
    )

    assert response.status_code == 400, response.text
    assert "оплаченный счёт" in response.json()["detail"]

    # Повторное чтение: состояние НЕ изменилось (нет имитации сохранения)
    db_session.refresh(entry)
    db_session.refresh(vs)
    db_session.refresh(invoice)
    payload = next(p for p in entry.services if p.get("service_id") == service.id)
    assert payload["quantity"] == 3
    assert vs.qty == 3
    assert Decimal(str(invoice.total_amount)) == PRICE * 3


@pytest.mark.integration
@pytest.mark.queue
def test_edit_delta_change_on_completed_visit_is_rejected_without_duplicate(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    """Завершённая позиция дня: «изменение количества» без активной записи
    не должно превращаться в создание дубликата (прежнее поведение)."""
    service = _create_service(
        db_session, code="TSQ-CLOS-01", name="TS Closed", queue_tag="laboratory_general"
    )
    _create_queue(
        db_session, specialist_id=test_doctor.id, queue_tag="laboratory_general", day=date.today()
    )
    visit = _create_visit(
        db_session,
        patient=test_patient,
        doctor_id=test_doctor.id,
        department="laboratory_general",
        status="closed",
    )
    _attach_visit_service(db_session, visit=visit, service=service, quantity=2)

    response = _post_edit_delta(
        client,
        registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": service.id, "quantity": 4}],
    )

    assert response.status_code == 400, response.text
    assert "выполнена или отменена" in response.json()["detail"]

    # Дубликат позиции не создан
    visits = (
        db_session.query(Visit)
        .filter(Visit.patient_id == test_patient.id, Visit.visit_date == date.today())
        .all()
    )
    assert len(visits) == 1


# ===================== СМЕНА ВРАЧА СУЩЕСТВУЮЩЕЙ ПОЗИЦИИ =====================


@pytest.mark.integration
@pytest.mark.queue
def test_edit_delta_doctor_change_of_existing_position_is_rejected_explicitly(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    """Смена врача существующей позиции не игнорируется молча: команда
    отвергается с причиной (контракт переноса — wave2 PR2), состояние
    не меняется."""
    service = _create_service(
        db_session, code="TSQ-DOC-01", name="TS Doctor", queue_tag="laboratory_general"
    )
    other_specialist_id = test_doctor.id + 100  # синтетический «другой врач»
    queue = _create_queue(
        db_session, specialist_id=test_doctor.id, queue_tag="laboratory_general", day=date.today()
    )
    visit = _create_visit(
        db_session, patient=test_patient, doctor_id=test_doctor.id, department="laboratory_general"
    )
    vs = _attach_visit_service(db_session, visit=visit, service=service, quantity=1)
    entry = _create_entry(
        db_session, queue=queue, patient=test_patient, service=service, quantity=1, visit_id=visit.id
    )

    response = _post_edit_delta(
        client,
        registrar_auth_headers,
        patient_id=test_patient.id,
        services=[
            {"service_id": service.id, "quantity": 2, "specialist_id": other_specialist_id}
        ],
        entry_ids=[entry.id],
    )

    assert response.status_code == 400, response.text
    assert "другому врачу" in response.json()["detail"]

    db_session.refresh(entry)
    db_session.refresh(vs)
    payload = next(p for p in entry.services if p.get("service_id") == service.id)
    assert payload["quantity"] == 1
    assert vs.qty == 1


@pytest.mark.integration
@pytest.mark.queue
def test_edit_delta_same_service_from_other_doctor_does_not_merge(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    """Одинаковая услуга у разных врачей не сливается по service_id
    (ADR-001: очередь принадлежит врачу). Позиция врача A не растёт, когда
    услуга явно запрошена у врача B: новая позиция создаётся в очереди B.

    W2-PR2: preferred-записи (existing_queue_entry_ids) определяют день
    редактирования (канонизация resolve_edit_target_day), поэтому сценарий
    «позиция врача B» формируется БЕЗ preferred — день дельты остаётся явно
    названным (target_date), и гарды переноса дня записи не срабатывают.
    """
    service = _create_service(
        db_session, code="TSQ-MRG-01", name="TS Merge", queue_tag="laboratory_general"
    )
    queue_a = _create_queue(
        db_session, specialist_id=test_doctor.id, queue_tag="laboratory_general", day=date.today()
    )
    visit = _create_visit(
        db_session, patient=test_patient, doctor_id=test_doctor.id, department="laboratory_general"
    )
    entry_a = _create_entry(
        db_session,
        queue=queue_a,
        patient=test_patient,
        service=service,
        quantity=1,
        visit_id=visit.id,
    )

    # Врач B: реальный Doctor + своя очередь того же queue_tag
    other_specialist_id = _create_doctor(db_session, username="ts_merge_doctor_b").id
    queue_b = _create_queue(
        db_session,
        specialist_id=other_specialist_id,
        queue_tag="laboratory_general",
        day=date.today() + timedelta(days=1),  # другой день: B-очередь дня дельты одна
    )
    assert queue_b.day != queue_a.day

    # Дельта на завтра (дата очереди B): явный specialist B, preferred НЕ
    # передаются — W2-PR2: preferred означал бы «редактируем запись A» и
    # канонизировал бы день в день записи A.
    target_day = date.today() + timedelta(days=1)
    response = _post_edit_delta(
        client,
        registrar_auth_headers,
        patient_id=test_patient.id,
        services=[
            {"service_id": service.id, "quantity": 1, "specialist_id": other_specialist_id}
        ],
        target_date=target_day,
        entry_ids=[],
    )

    assert response.status_code == 200, response.text

    # Позиция врача A не изменилась
    db_session.refresh(entry_a)
    payload_a = next(p for p in entry_a.services if p.get("service_id") == service.id)
    assert payload_a["quantity"] == 1

    # Новая позиция создана в очереди врача B (не слилась с A)
    new_entries = (
        db_session.query(OnlineQueueEntry)
        .join(DailyQueue, OnlineQueueEntry.queue_id == DailyQueue.id)
        .filter(
            OnlineQueueEntry.patient_id == test_patient.id,
            DailyQueue.day == target_day,
        )
        .all()
    )
    assert len(new_entries) == 1
    assert new_entries[0].queue.specialist_id == other_specialist_id


# ===================== ОТСУТСТВИЕ ИЗМЕНЕНИЙ — НАСТОЯЩИЙ NO-OP =====================


@pytest.mark.integration
@pytest.mark.queue
def test_edit_delta_unchanged_target_is_true_noop(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    """Полная корзина без фактических изменений: ни начислений, ни обновления
    таймстампов/сумм — настоящий no-op."""
    service = _create_service(
        db_session, code="TSQ-NOP-01", name="TS Noop", queue_tag="laboratory_general"
    )
    queue = _create_queue(
        db_session, specialist_id=test_doctor.id, queue_tag="laboratory_general", day=date.today()
    )
    visit = _create_visit(
        db_session, patient=test_patient, doctor_id=test_doctor.id, department="laboratory_general"
    )
    _attach_visit_service(db_session, visit=visit, service=service, quantity=2)
    entry = _create_entry(
        db_session, queue=queue, patient=test_patient, service=service, quantity=2, visit_id=visit.id
    )
    updated_before = entry.updated_at
    total_before = entry.total_amount

    response = _post_edit_delta(
        client,
        registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": service.id, "quantity": 2}],
        entry_ids=[entry.id],
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert Decimal(str(payload["total_amount"])) == 0
    assert payload["invoice_id"] is None

    db_session.expire_all()
    db_session.refresh(entry)
    assert entry.total_amount == total_before
    assert entry.updated_at == updated_before  # таймстамп не тронут

    # Квота edit_delta для неизменённой позиции биллит 0 (зеркало локсеп)
    quote = _quote_edit_delta(
        client,
        registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": service.id, "quantity": 2}],
    )
    assert Decimal(str(quote["total_amount"])) == 0


# ===================== МОДИФИКАЦИЯ + ДОБАВЛЕНИЕ В ОДНОЙ КОМАНДЕ =====================


@pytest.mark.integration
@pytest.mark.queue
def test_edit_delta_modify_existing_and_add_new_in_one_command(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    service = _create_service(
        db_session, code="TSQ-MIX-01", name="TS Mix Old", queue_tag="laboratory_general"
    )
    added = _create_service(
        db_session, code="TSQ-MIX-02", name="TS Mix New", queue_tag="laboratory_general"
    )
    queue = _create_queue(
        db_session, specialist_id=test_doctor.id, queue_tag="laboratory_general", day=date.today()
    )
    visit = _create_visit(
        db_session, patient=test_patient, doctor_id=test_doctor.id, department="laboratory_general"
    )
    vs = _attach_visit_service(db_session, visit=visit, service=service, quantity=1)
    entry = _create_entry(
        db_session, queue=queue, patient=test_patient, service=service, quantity=1, visit_id=visit.id
    )

    response = _post_edit_delta(
        client,
        registrar_auth_headers,
        patient_id=test_patient.id,
        services=[
            {"service_id": service.id, "quantity": 4},
            {"service_id": added.id, "quantity": 2},
        ],
        entry_ids=[entry.id],
    )

    assert response.status_code == 200, response.text
    # Рост 1→4 (3×цена) + добавление 2×цена = 5×цена
    assert Decimal(str(response.json()["total_amount"])) == PRICE * 5

    record = _read_today_record(
        client, registrar_auth_headers, patient_id=test_patient.id, target_date=date.today()
    )
    quantities = {d["id"]: d["quantity"] for d in record["service_details"]}
    assert quantities[service.id] == 4
    assert quantities[added.id] == 2

    db_session.refresh(entry)
    db_session.refresh(vs)
    payload_old = next(p for p in entry.services if p.get("service_id") == service.id)
    payload_new = next(p for p in entry.services if p.get("service_id") == added.id)
    assert payload_old["quantity"] == 4
    assert payload_new["quantity"] == 2
    assert vs.qty == 4
    assert Decimal(str(entry.total_amount)) == PRICE * (4 + 2)


# ===================== КВОТА — ЗЕРКАЛО КОМАНДЫ (lockstep) =====================


@pytest.mark.integration
@pytest.mark.queue
def test_edit_delta_quote_mirrors_signed_delta_and_token_is_accepted(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    """Квота edit_delta биллит ту же знаковую дельту, что и команда, и токен
    от квоты принимается командой (пере-проверка без ложного 409)."""
    service = _create_service(
        db_session, code="TSQ-LS-01", name="TS Lockstep", queue_tag="laboratory_general"
    )
    queue = _create_queue(
        db_session, specialist_id=test_doctor.id, queue_tag="laboratory_general", day=date.today()
    )
    visit = _create_visit(
        db_session, patient=test_patient, doctor_id=test_doctor.id, department="laboratory_general"
    )
    _attach_visit_service(db_session, visit=visit, service=service, quantity=3)
    entry = _create_entry(
        db_session, queue=queue, patient=test_patient, service=service, quantity=3, visit_id=visit.id
    )

    # Снижение 3→1: квота показывает −2×цена
    quote = _quote_edit_delta(
        client,
        registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": service.id, "quantity": 1}],
    )
    assert Decimal(str(quote["total_amount"])) == -PRICE * 2

    # Токен подтверждённой квоты принимается командой с той же дельтой
    response = _post_edit_delta(
        client,
        registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": service.id, "quantity": 1}],
        entry_ids=[entry.id],
        quote_token=quote["quote_token"],
    )
    assert response.status_code == 200, response.text
    assert Decimal(str(response.json()["total_amount"])) == -PRICE * 2


# ===================== READ-MODEL: quantity в service_details =====================


@pytest.mark.integration
@pytest.mark.queue
def test_read_model_service_details_include_quantity(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    """Без quantity в read-модели мастер не знал исходного количества позиции
    и не мог детектировать ни рост, ни снижение."""
    service = _create_service(
        db_session, code="TSQ-RM-01", name="TS ReadModel", queue_tag="laboratory_general"
    )
    _create_queue(
        db_session, specialist_id=test_doctor.id, queue_tag="laboratory_general", day=date.today()
    )
    visit = _create_visit(
        db_session, patient=test_patient, doctor_id=test_doctor.id, department="laboratory_general"
    )
    _attach_visit_service(db_session, visit=visit, service=service, quantity=5)

    record = _read_today_record(
        client, registrar_auth_headers, patient_id=test_patient.id, target_date=date.today()
    )
    assert record is not None
    detail = next(d for d in record["service_details"] if d["id"] == service.id)
    assert detail["quantity"] == 5
