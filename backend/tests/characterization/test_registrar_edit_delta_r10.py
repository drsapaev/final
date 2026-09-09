"""Codex R10 #3115 — исправления P1: forward queue_entry_id (адаптер —
frontend-тест), сохранение записанной стоимости при росте (средневзвешенная
цена), блокировка счёта при снижении.

Каждый кейс проверяет СОСТОЯНИЕ (повторное чтение DB), а не только HTTP-код.
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
from app.services.payment_invariant_service import PaymentInvariantService
from app.services.registrar_edit_delta_service import RegistrarEditDeltaService

TZ = ZoneInfo("Asia/Tashkent")


def _create_service(db_session, *, code: str, price: int) -> Service:
    service = Service(
        code=code,
        service_code=code,
        name=f"R10 {code}",
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
    """Desk-конвенция новой записи: явный unit_price (канонический источник)."""
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
        notes="r10-test",
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


# ===================== P1: РОСТ СОХРАНЯЕТ ЗАПИСАННУЮ СТОИМОСТЬ =====================


@pytest.mark.integration
@pytest.mark.queue
def test_increase_with_catalog_change_blends_recorded_and_delta_cost(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    """Визит записан 1×100, каталог изменился на 150, рост 1→2:
    счёт выставляет только дельту (+150) → итог 250. VisitService-строка и
    entry-пейлоад обязаны представлять ту же сумму (2×125=250), иначе
    PaymentInvariantService.compute_total_cost считал бы 300 канонической
    стоимостью и собирал бы лишние 50."""
    service = _create_service(db_session, code="R10-BL-01", price=100)
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

    # Каталог изменился ПОСЛЕ записи
    service.price = Decimal("150")
    db_session.commit()

    response = _post_edit_delta(
        client, registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": service.id, "quantity": 2, "specialist_id": None, "queue_entry_id": entry.id}],
        entry_ids=[entry.id],
    )
    assert response.status_code == 200, response.text
    assert Decimal(str(response.json()["total_amount"])) == Decimal("150")  # дельта по каталогу

    # Повторное чтение: строка, пейлоад, entry, invoice согласованы
    row = _reread_visit_service(db_session, visit.id, service.id)
    assert row.qty == 2
    assert Decimal(str(row.price)) == Decimal("125.00")  # (100 + 150) / 2
    assert Decimal(str(row.price)) * row.qty == Decimal("250")

    db_session.expire_all()
    db_session.refresh(entry)
    payload = entry.services[0]
    assert payload["quantity"] == 2
    assert Decimal(str(payload["unit_price"])) == Decimal("125.00")
    assert entry.total_amount == 250

    db_session.refresh(invoice)
    assert invoice.total_amount == Decimal("250")
    assert invoice.status == "pending"

    # Каноническая стоимость визита == сумма счёта — лишнего долга нет
    invariant = PaymentInvariantService(db_session).compute_total_cost(visit)
    assert invariant == Decimal("250")


@pytest.mark.integration
@pytest.mark.queue
def test_increase_without_catalog_change_keeps_catalog_price(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    """Без изменения цены рост ведёт себя как раньше: строка/пейлоад —
    каталоговая цена, счёт — дельта (1×100 → 2: итог 200 = 2×100)."""
    service = _create_service(db_session, code="R10-BL-02", price=100)
    queue = _create_queue(db_session, specialist_id=test_doctor.id, queue_tag="laboratory_general", day=date.today())
    visit = _create_visit_with_row(
        db_session, patient=test_patient, doctor_id=test_doctor.id,
        department="laboratory_general", service=service, qty=1, price=100,
    )
    entry = _create_entry(
        db_session, queue=queue, patient=test_patient, service=service,
        quantity=1, unit_price=100, total_amount=100, visit_id=visit.id,
    )
    _create_invoice(db_session, patient=test_patient, visit=visit, amount=100)

    response = _post_edit_delta(
        client, registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": service.id, "quantity": 2, "specialist_id": None, "queue_entry_id": entry.id}],
        entry_ids=[entry.id],
    )
    assert response.status_code == 200, response.text

    row = _reread_visit_service(db_session, visit.id, service.id)
    assert row.qty == 2
    assert Decimal(str(row.price)) == Decimal("100.00")
    db_session.expire_all()
    db_session.refresh(entry)
    assert entry.total_amount == 200
    assert Decimal(str(entry.services[0]["unit_price"])) == Decimal("100.00")


@pytest.mark.integration
@pytest.mark.queue
def test_decrease_after_blend_subtracts_blended_unit_and_representations_agree(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    """Последующее снижение после средневзвешенного роста списывает записанную
    (средневзвешенную) цену: строка, пейлоад, entry и счёт остаются согласованы
    (250 → 125 при снижении 2→1)."""
    service = _create_service(db_session, code="R10-BL-03", price=100)
    queue = _create_queue(db_session, specialist_id=test_doctor.id, queue_tag="laboratory_general", day=date.today())
    visit = _create_visit_with_row(
        db_session, patient=test_patient, doctor_id=test_doctor.id,
        department="laboratory_general", service=service, qty=1, price=100,
    )
    entry = _create_entry(
        db_session, queue=queue, patient=test_patient, service=service,
        quantity=1, unit_price=100, total_amount=100, visit_id=visit.id,
    )
    _create_invoice(db_session, patient=test_patient, visit=visit, amount=100)

    service.price = Decimal("150")
    db_session.commit()
    up = _post_edit_delta(
        client, registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": service.id, "quantity": 2, "specialist_id": None, "queue_entry_id": entry.id}],
        entry_ids=[entry.id],
    )
    assert up.status_code == 200, up.text

    down = _post_edit_delta(
        client, registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": service.id, "quantity": 1, "specialist_id": None, "queue_entry_id": entry.id}],
        entry_ids=[entry.id],
    )
    assert down.status_code == 200, down.text
    assert Decimal(str(down.json()["total_amount"])) == Decimal("-125")

    row = _reread_visit_service(db_session, visit.id, service.id)
    assert row.qty == 1
    assert Decimal(str(row.price)) == Decimal("125.00")
    db_session.expire_all()
    db_session.refresh(entry)
    assert entry.total_amount == 125
    assert Decimal(str(entry.services[0]["unit_price"])) == Decimal("125.00")

    db_session.expire_all()
    invoice = (
        db_session.query(PaymentInvoice)
        .filter(PaymentInvoice.patient_id == test_patient.id, PaymentInvoice.status == "pending")
        .first()
    )
    assert invoice is not None
    assert invoice.total_amount == Decimal("125")


# ===================== P1: БЛОКИРОВКА СЧЁТА ПРИ СНИЖЕНИИ =====================


@pytest.mark.integration
@pytest.mark.queue
def test_decrease_revalidates_invoice_status_under_lock(
    client, db_session, registrar_auth_headers, test_patient, test_doctor, monkeypatch
):
    """Гонка «pending → processing» между guard'ом и мутацией: init_invoice_payment
    успел выставить счёт провайдеру между проверкой guard'а и снижением.
    Ревалидация статуса ПОД блокировкой строки (Codex R10 #3115 P1) даёт громкий
    400 и НЕ меняет ни счёт, ни очередь, ни визит.

    Симуляция окна гонки: guard (_assert_decrease_allowed) проходит при pending,
    затем (как коммит параллельного init-payment) счёт переводится в processing,
    и только после этого выполняется заблокированное чтение _reduce..."""
    service = _create_service(db_session, code="R10-LK-01", price=100)
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

    original_guard = RegistrarEditDeltaService._assert_decrease_allowed

    def guard_then_concurrent_init(self, *, entry):
        original_guard(self, entry=entry)  # guard видит pending — пропускает
        # ...в этот момент коммитит параллельный init_invoice_payment:
        row_invoice = (
            self.db.query(PaymentInvoice).filter(PaymentInvoice.id == invoice.id).first()
        )
        row_invoice.status = "processing"  # как init-payment после ответа провайдера

    monkeypatch.setattr(
        RegistrarEditDeltaService, "_assert_decrease_allowed", guard_then_concurrent_init
    )

    response = _post_edit_delta(
        client, registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": service.id, "quantity": 1, "specialist_id": None, "queue_entry_id": entry.id}],
        entry_ids=[entry.id],
    )

    assert response.status_code == 400, response.text
    assert "уже обрабатывается" in response.json()["detail"]

    # Состояние НЕ изменено: счёт, очередь, визит — как до попытки
    db_session.expire_all()
    db_session.refresh(invoice)
    assert invoice.total_amount == Decimal("300")
    db_session.refresh(entry)
    assert entry.services[0]["quantity"] == 3
    assert entry.total_amount == 300
    row = _reread_visit_service(db_session, visit.id, service.id)
    assert row.qty == 3


@pytest.mark.integration
@pytest.mark.queue
def test_init_invoice_payment_locks_the_invoice_row_source_contract():
    """Координация второй стороны гонки: init_invoice_payment читает счёт
    FOR UPDATE — сериализуется со снижением edit-delta (кто первый взял
    блокировку, второй видит закоммиченное состояние)."""
    import inspect
    from pathlib import Path

    import app.api.v1.endpoints.registrar_wizard._invoice as invoice_module

    source = Path(inspect.getsourcefile(invoice_module)).read_text(encoding="utf-8")
    assert ".with_for_update()" in source
    # Блокировка стоит на ЧТЕНИИ счёта, до проверки статуса и вызова провайдера
    read_block = source[source.index("invoice = (") : source.index('if invoice.status != "pending"')]
    assert "with_for_update" in read_block
