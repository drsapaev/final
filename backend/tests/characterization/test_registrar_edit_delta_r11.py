"""Codex R11 #3115 — две P1-находки:

1. Явный queue_entry_id — СТРОГИЙ селектор: устаревшая идентичность даёт
   громкий 400 вместо тихого выбора другой записи (entries[0]) или тихого
   создания новой. Зеркало гейта в edit-квоте (strict там же).
2. Рост pending-счёта под блокировкой строки: гонка с init_invoice_payment
   (pending → processing) даёт 400 и НЕ меняет счёт (зеркало R10-фикса
   снижения).

Каждый кейс проверяет СОСТОЯНИЕ (повторное чтение DB), а не только код.
Все данные синтетические; production DB не используется.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.payment_invoice import PaymentInvoice
from app.models.service import Service
from app.models.visit import Visit, VisitService
from app.services.registrar_edit_delta_service import RegistrarEditDeltaService

TZ = ZoneInfo("Asia/Tashkent")


def _create_service(db_session, *, code: str, price: int) -> Service:
    service = Service(
        code=code,
        service_code=code,
        name=f"R11 {code}",
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
    visit_id: int | None = None,
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
        notes="r11-test",
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


# ===================== P1: СТРОГИЙ ЯВНЫЙ queue_entry_id =====================


@pytest.mark.integration
@pytest.mark.queue
def test_explicit_queue_entry_id_mismatch_is_a_loud_400_not_a_silent_retarg(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    """Codex R11 #3115 (P1): когда явный queue_entry_id больше не матчит
    активную запись (статус/дата изменились, агрегированный резолвер дал
    чужой ID), прежний код оставлял ПОЛНЫЙ список кандидатов и выбирал
    entries[0] — команда мутировала и выставляла счёт по ЧУЖОЙ строке
    очереди вместо отказа по устаревшей идентичности. Явно названный ID
    обязан быть строгим селектором."""
    service = _create_service(db_session, code="R11-STRICT-1", price=100)
    queue = _create_queue(db_session, specialist_id=test_doctor.id, queue_tag="laboratory_general", day=date.today())
    # Активная запись пациента с той же услугой (qty=1) — единственный
    # кандидат в этом queue_tag.
    _create_entry(
        db_session, queue=queue, patient=test_patient, service=service,
        quantity=1, unit_price=100, total_amount=100,
    )

    # Клиент ссылается на НЕСУЩЕСТВУЮЩУЮ запись: прежний код падал в
    # entries[0] и молча правил существующую запись (200, qty 1 → 3).
    response = _post_edit_delta(
        client, registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": service.id, "quantity": 3, "specialist_id": None, "queue_entry_id": 999999}],
        entry_ids=[],
    )

    assert response.status_code == 400, response.text
    assert "999999" in response.json()["detail"], response.text

    # Состояние НЕ изменено: существующая запись не мутировала, дублей нет.
    db_session.expire_all()
    entries = (
        db_session.query(OnlineQueueEntry)
        .filter(
            OnlineQueueEntry.patient_id == test_patient.id,
            OnlineQueueEntry.queue_id == queue.id,
        )
        .all()
    )
    assert len(entries) == 1
    assert entries[0].services[0]["quantity"] == 1
    assert entries[0].total_amount == 100


@pytest.mark.integration
@pytest.mark.queue
def test_explicit_queue_entry_id_without_active_entry_rejects_instead_of_requeue(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    """Второе крыло того же P1: явный ID не матчит ни одну активную запись,
    активных записей НЕТ — прежний код проваливался в _create_new_queue_entry
    и тихо ставил пациента в очередь заново (тихая ре-регистрация под видом
    правки). Явная устаревшая идентичность — 400, создание запрещено."""
    service = _create_service(db_session, code="R11-STRICT-2", price=100)
    queue = _create_queue(db_session, specialist_id=test_doctor.id, queue_tag="laboratory_general", day=date.today())

    response = _post_edit_delta(
        client, registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": service.id, "quantity": 2, "specialist_id": None, "queue_entry_id": 999999}],
        entry_ids=[],
    )

    assert response.status_code == 400, response.text
    assert "999999" in response.json()["detail"], response.text

    db_session.expire_all()
    created = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.patient_id == test_patient.id, OnlineQueueEntry.queue_id == queue.id)
        .count()
    )
    assert created == 0, "устаревший явный ID не должен создавать запись"


@pytest.mark.integration
@pytest.mark.queue
def test_quote_mirrors_strict_identity_rejection(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    """Зеркало в квоте: edit-квота с устаревшим явным queue_entry_id
    возвращает 400 ДО выпуска токена (прежний код токенизировал дельту,
    посчитанную по чужой записи)."""
    service = _create_service(db_session, code="R11-STRICT-3", price=100)
    queue = _create_queue(db_session, specialist_id=test_doctor.id, queue_tag="laboratory_general", day=date.today())
    _create_entry(
        db_session, queue=queue, patient=test_patient, service=service,
        quantity=1, unit_price=100, total_amount=100,
    )

    response = client.post(
        "/api/v1/registrar/cart/quote",
        headers=registrar_auth_headers,
        json={
            "items": [
                {
                    "service_id": service.id,
                    "quantity": 3,
                    "specialist_id": None,
                    "queue_entry_id": 999999,
                }
            ],
            "discount_mode": "none",
            "all_free": False,
            "pricing_mode": "edit_delta",
            "patient_id": test_patient.id,
            "target_date": date.today().isoformat(),
            "preferred_entry_ids": [],
        },
    )

    assert response.status_code == 400, response.text
    assert "999999" in response.json()["detail"], response.text


# ===================== P1: РОСТ СЧЁТА ПОД БЛОКИРОВКОЙ =====================


@pytest.mark.integration
@pytest.mark.queue
def test_increase_revalidates_invoice_status_under_lock(
    client, db_session, registrar_auth_headers, test_patient, test_doctor, monkeypatch
):
    """Codex R11 #3115 (P1, тело ревью): гонка «pending → processing» на пути
    РОСТА — _increase_pending_invoice читал pending-счёт БЕЗ FOR UPDATE:
    init_invoice_payment успевал выставить счёт провайдеру, а рост
    доначислял total_amount уже ОБРАБАТЫВАЕМОМУ счёту (провайдер соберёт
    старую сумму, визит/очередь уже содержат рост). Зеркало R10-фикса
    снижения: блокировка строки + ревалидация статуса → 400, состояние
    не изменено.

    Симуляция окна гонки: (как коммит параллельного init-payment) счёт
    переводится в processing ПОСЛЕ guard-фазы и ДО чтения счёта ростом."""
    service = _create_service(db_session, code="R11-LK-01", price=100)
    queue = _create_queue(db_session, specialist_id=test_doctor.id, queue_tag="laboratory_general", day=date.today())
    visit = _create_visit_with_row(
        db_session, patient=test_patient, doctor_id=test_doctor.id,
        department="laboratory_general", service=service, qty=1, price=100,
    )
    entry = _create_entry(
        db_session, queue=queue, patient=test_patient, service=service,
        quantity=1, unit_price=100, total_amount=100, visit_id=visit.id,
    )
    invoice = _create_invoice(db_session, patient=test_patient, visit=visit, amount=100)

    original_apply = RegistrarEditDeltaService._apply_invoice_delta

    def apply_then_concurrent_init(self, **kwargs):
        # ...в этот момент коммитит параллельный init_invoice_payment:
        row_invoice = (
            self.db.query(PaymentInvoice).filter(PaymentInvoice.id == invoice.id).first()
        )
        row_invoice.status = "processing"  # как init-payment после ответа провайдера
        return original_apply(self, **kwargs)

    monkeypatch.setattr(
        RegistrarEditDeltaService, "_apply_invoice_delta", apply_then_concurrent_init
    )

    response = _post_edit_delta(
        client, registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": service.id, "quantity": 3, "specialist_id": None, "queue_entry_id": entry.id}],
        entry_ids=[entry.id],
    )

    assert response.status_code == 400, response.text
    assert "уже обрабатывается" in response.json()["detail"], response.text

    # Состояние НЕ изменено: счёт не доначислен, очередь/визит — как до попытки.
    db_session.expire_all()
    db_session.refresh(invoice)
    assert invoice.total_amount == Decimal("100")
    db_session.refresh(entry)
    assert entry.services[0]["quantity"] == 1
    assert entry.total_amount == 100
    row = (
        db_session.query(VisitService)
        .filter(VisitService.visit_id == visit.id, VisitService.service_id == service.id)
        .first()
    )
    assert row.qty == 1
