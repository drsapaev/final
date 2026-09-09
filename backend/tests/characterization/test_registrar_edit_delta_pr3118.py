"""Codex R10 PR 3118 — фиксы decrease-гарда edit-delta.

Находки:
  - P1 :521 — инициализированный провайдерский платёж (Click/PayMe/Kaspi)
    остаётся pending с фиксированной суммой и платёжной ссылкой; редукция
    вычитала только PENDING-счёт, Payment.amount/payment_url оставались на
    старое количество — пациент доплатил бы по ссылке за уменьшенную услугу.
    Фикс: гвард блокирует снижение при pending-Payment визита.
  - P1 :467 — сериализация снижения с созданием платежа (runtime-доказательство
    блокировки Visit FOR UPDATE — см. tests/integration/test_gate_d.py,
    здесь портативный source-контракт: гвард обязан читать визит под
    блокировкой строки).

Каждый сохраняющий кейс проверяет СОСТОЯНИЕ повторным чтением DB.
Данные синтетические; production DB не используется.
"""
from __future__ import annotations

import inspect
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.payment import Payment
from app.models.payment_invoice import PaymentInvoice
from app.models.service import Service
from app.models.visit import Visit, VisitService
from app.services.payment_invariant_service import PaymentInvariantService
from app.services.registrar_edit_delta_service import RegistrarEditDeltaService

TZ = ZoneInfo("Asia/Tashkent")


def _create_service(db_session, *, code: str, price: int) -> Service:
    service = Service(
        code=code,
        service_code=code,
        name=f"R3118 {code}",
        price=Decimal(price),
        active=True,
        requires_doctor=False,
        queue_tag="laboratory_general",
        department_key="laboratory_general",
        is_consultation=False,
    )
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)
    return service


def _create_queue(db_session, *, specialist_id: int, queue_tag: str, day: date) -> DailyQueue:
    queue = DailyQueue(day=day, specialist_id=specialist_id, queue_tag=queue_tag, active=True)
    db_session.add(queue)
    db_session.commit()
    db_session.refresh(queue)
    return queue


def _create_visit_with_row(
    db_session, *, patient, doctor_id: int, department: str, service: Service, qty: int, price: int
) -> Visit:
    visit = Visit(
        patient_id=patient.id,
        doctor_id=doctor_id,
        visit_date=date.today(),
        visit_time=None,
        department=department,
        discount_mode="none",
        approval_status="approved",
        status="open",
        source="desk",
    )
    db_session.add(visit)
    db_session.flush()
    db_session.add(
        VisitService(
            visit_id=visit.id,
            service_id=service.id,
            code=service.service_code,
            name=service.name,
            qty=qty,
            price=Decimal(price),
            currency="UZS",
        )
    )
    db_session.commit()
    db_session.refresh(visit)
    return visit


def _create_entry(
    db_session,
    *,
    queue: DailyQueue,
    patient,
    service: Service,
    quantity: int,
    unit_price: int,
    total_amount: int,
    visit_id: int,
) -> OnlineQueueEntry:
    payload = {
        "id": service.id,
        "service_id": service.id,
        "code": service.service_code,
        "name": service.name,
        "quantity": quantity,
        "price": unit_price,
        "unit_price": unit_price,
    }
    entry = OnlineQueueEntry(
        queue_id=queue.id,
        number=9,
        patient_id=patient.id,
        patient_name=patient.short_name(),
        phone=patient.phone,
        visit_id=visit_id,
        source="desk",
        status="waiting",
        queue_time=datetime.now(TZ).replace(microsecond=0),
        services=[payload],
        service_codes=[service.service_code],
        total_amount=total_amount,
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)
    return entry


def _create_invoice(db_session, *, patient, visit, amount: int, status: str = "pending") -> PaymentInvoice:
    from app.models.payment_invoice import PaymentInvoiceVisit

    invoice = PaymentInvoice(
        patient_id=patient.id,
        total_amount=Decimal(amount),
        currency="UZS",
        status=status,
        payment_method="click",
        notes="r3118-test",
    )
    db_session.add(invoice)
    db_session.flush()
    db_session.add(
        PaymentInvoiceVisit(invoice_id=invoice.id, visit_id=visit.id, visit_amount=Decimal(amount))
    )
    db_session.commit()
    db_session.refresh(invoice)
    return invoice


def _post_edit_delta(client, registrar_auth_headers, *, patient_id, services, entry_ids):
    payload = {
        "patient_id": patient_id,
        "target_date": date.today().isoformat(),
        "payment_method": "cash",
        "discount_mode": "none",
        "all_free": False,
        "services": services,
        "existing_queue_entry_ids": entry_ids,
    }
    return client.post(
        "/api/v1/registrar/cart/edit-delta",
        headers=registrar_auth_headers,
        json=payload,
    )


def _reread_visit_service(db_session, visit_id: int, service_id: int) -> VisitService:
    db_session.expire_all()
    return (
        db_session.query(VisitService)
        .filter(VisitService.visit_id == visit_id, VisitService.service_id == service_id)
        .first()
    )


# ===================== P1 :521 — pending-платёж блокирует снижение =====================


@pytest.mark.integration
@pytest.mark.queue
def test_decrease_blocked_while_provider_payment_pending(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    """Провайдерский платёж инициализирован (pending, фиксированная сумма и
    payment_url), счёт ещё pending. Снижение 3→1 обязано быть ЗАБЛОКИРОВАНО:
    редукция уменьшила бы счёт, а платёжная ссылка осталась бы на старую
    сумму 300 — пациент доплатил бы по ней за уменьшенную услугу."""
    service = _create_service(db_session, code="R3118-PP-01", price=100)
    queue = _create_queue(db_session, specialist_id=test_doctor.id, queue_tag="laboratory_general", day=date.today())
    visit = _create_visit_with_row(
        db_session, patient=test_patient, doctor_id=test_doctor.id,
        department="laboratory_general", service=service, qty=3, price=100,
    )
    entry = _create_entry(
        db_session, queue=queue, patient=test_patient, service=service,
        quantity=3, unit_price=100, total_amount=300, visit_id=visit.id,
    )
    invoice = _create_invoice(db_session, patient=test_patient, visit=visit, amount=300)

    # Канонический путь инициализации онлайн-платежа (как PaymentInitService)
    payment = PaymentInvariantService(db_session).create_pending_payment(
        visit_id=visit.id,
        amount=Decimal("300"),
        currency="UZS",
        method="online",
        provider="click",
        note="r3118-pending",
        current_user=type("UserRef", (), {"id": None})(),
    )
    assert payment.status == "pending"
    assert payment.amount == Decimal("300")

    response = _post_edit_delta(
        client, registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": service.id, "quantity": 1, "specialist_id": None, "queue_entry_id": entry.id}],
        entry_ids=[entry.id],
    )

    assert response.status_code == 400, response.text
    assert "неоплаченный онлайн-платёж" in response.json()["detail"]

    # Состояние НЕ изменено: счёт, очередь, визит — как до попытки
    db_session.expire_all()
    db_session.refresh(invoice)
    assert invoice.total_amount == Decimal("300")
    db_session.refresh(entry)
    assert entry.services[0]["quantity"] == 3
    assert entry.total_amount == 300
    row = _reread_visit_service(db_session, visit.id, service.id)
    assert row.qty == 3

    # Платёж не тронут (сумма и ссылка на старое количество сохранены для
    # честной отмены/завершения, а не «уменьшены» молча)
    db_session.refresh(payment)
    assert payment.status == "pending"
    assert payment.amount == Decimal("300")


@pytest.mark.integration
@pytest.mark.queue
def test_decrease_allowed_after_pending_payment_cancelled(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    """Негативный контроль против переблокировки: после ОТМЕНЫ pending-платежа
    снижение снова доступно (terminated-статусы не блокируют)."""
    service = _create_service(db_session, code="R3118-PP-02", price=100)
    queue = _create_queue(db_session, specialist_id=test_doctor.id, queue_tag="laboratory_general", day=date.today())
    visit = _create_visit_with_row(
        db_session, patient=test_patient, doctor_id=test_doctor.id,
        department="laboratory_general", service=service, qty=3, price=100,
    )
    entry = _create_entry(
        db_session, queue=queue, patient=test_patient, service=service,
        quantity=3, unit_price=100, total_amount=300, visit_id=visit.id,
    )
    invoice = _create_invoice(db_session, patient=test_patient, visit=visit, amount=300)

    payment = PaymentInvariantService(db_session).create_pending_payment(
        visit_id=visit.id,
        amount=Decimal("300"),
        currency="UZS",
        method="online",
        provider="click",
        note="r3118-cancelled",
        current_user=type("UserRef", (), {"id": None})(),
    )
    payment.status = "cancelled"  # платёж отменён (касса/админ)
    db_session.commit()

    response = _post_edit_delta(
        client, registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": service.id, "quantity": 1, "specialist_id": None, "queue_entry_id": entry.id}],
        entry_ids=[entry.id],
    )

    assert response.status_code == 200, response.text

    db_session.expire_all()
    db_session.refresh(invoice)
    assert invoice.total_amount == Decimal("100")
    db_session.refresh(entry)
    assert entry.services[0]["quantity"] == 1
    row = _reread_visit_service(db_session, visit.id, service.id)
    assert row.qty == 1


# ===================== P1 :467 — Visit FOR UPDATE (source-контракт) =====================


def test_decrease_guard_locks_visit_row_source_contract():
    """Портативный source-контракт сериализационного фикса: гвард снижения
    читает визит ПОД блокировкой строки (SELECT ... FOR UPDATE) — иначе
    платёжный поток сериализуется на Visit-блокировке, а гвард — нет, и окно
    «после проверки, до коммита» открывает гонку с кассой/провайдером.
    Runtime-доказательство на реальных блокировках PostgreSQL:
    tests/integration/test_gate_d.py::test_edit_delta_decrease_guard_serializes_with_payment_creation."""
    source = inspect.getsource(RegistrarEditDeltaService._assert_decrease_allowed)
    assert "with_for_update" in source
    assert 'Payment.status == "pending"' in source
