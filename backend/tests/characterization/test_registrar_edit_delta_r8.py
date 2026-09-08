"""Codex R8 #3115 — исправления: line-total снижение, processing-счета,
идентичность записи позиции, зеркало снижения в квоте.

Каждый кейс проверяет СОСТОЯНИЕ (повторное чтение DB/API), не только HTTP 200.
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
from app.models.visit import Visit

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
    queue = DailyQueue(day=day, specialist_id=specialist_id, queue_tag=queue_tag, active=True)
    db_session.add(queue)
    db_session.commit()
    db_session.refresh(queue)
    return queue


def _create_visit(db_session, *, patient, doctor_id, department: str) -> Visit:
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
    price: int,
    total_amount: int,
    visit_id: int | None = None,
    with_unit_price_field: bool = False,
) -> OnlineQueueEntry:
    """Прямое управление payload: полнота конвенций (unit / line-total)."""
    payload = {
        "id": service.id,
        "service_id": service.id,
        "code": service.service_code,
        "name": service.name,
        "quantity": quantity,
        "price": price,
    }
    if with_unit_price_field:
        payload["unit_price"] = price
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


def _create_invoice(db_session, *, patient, visit: Visit, amount: int, status: str) -> PaymentInvoice:
    invoice = PaymentInvoice(
        patient_id=patient.id,
        total_amount=Decimal(amount),
        currency="UZS",
        status=status,
        payment_method="click",
        notes="r8-test",
    )
    db_session.add(invoice)
    db_session.flush()
    db_session.add(
        PaymentInvoiceVisit(invoice_id=invoice.id, visit_id=visit.id, visit_amount=Decimal(amount))
    )
    db_session.commit()
    db_session.refresh(invoice)
    return invoice


def _post_edit_delta(client, registrar_auth_headers, *, patient_id, services, target_date=None, entry_ids=None):
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


def _quote_edit_delta(client, registrar_auth_headers, *, patient_id, services, preferred_entry_ids, target_date=None):
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


def _payload(db_session, entry_id: int) -> dict:
    db_session.expire_all()
    entry = db_session.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).first()
    assert entry is not None
    return entry.services[0]


# ===================== LINE-TOTAL СНИЖЕНИЕ (item 1 + item 5) =====================


@pytest.mark.integration
@pytest.mark.queue
def test_decrease_full_update_line_total_row_subtracts_unit_charge(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    """Full-update строка (qty 3, price=300 line-total, total=300): снижение
    3→1 списывает 200 (2×100 unit), а не 600 (повторное умножение total)."""
    service = _create_service(
        db_session, code="R8-LT-01", name="R8 LineTotal", queue_tag="laboratory_general"
    )
    queue = _create_queue(
        db_session, specialist_id=test_doctor.id, queue_tag="laboratory_general", day=date.today()
    )
    visit = _create_visit(db_session, patient=test_patient, doctor_id=test_doctor.id, department="laboratory_general")
    entry = _create_entry(
        db_session, queue=queue, patient=test_patient, service=service,
        quantity=3, price=300, total_amount=300, visit_id=visit.id,
    )
    _create_invoice(db_session, patient=test_patient, visit=visit, amount=300, status="pending")

    response = _post_edit_delta(
        client, registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": service.id, "quantity": 1}],
        entry_ids=[entry.id],
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert Decimal(str(body["total_amount"])) == Decimal("-200")  # не −600

    payload = _payload(db_session, entry.id)
    assert payload["quantity"] == 1
    db_session.expire_all()
    db_session.refresh(entry)
    assert entry.total_amount == 100  # 300 − 200


@pytest.mark.integration
@pytest.mark.queue
def test_decrease_quote_mirrors_recorded_charge_not_catalog(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    """Зеркало снижения: цена каталога изменилась (25000 → 300), записанная
    строка unit-конвенции (price=100, qty=3, total=300) → квота снижения
    3→1 = −200 (записанная цена), а не −450 (каталог 150×... в т.ч. рост)."""
    service = _create_service(
        db_session, code="R8-MIR-01", name="R8 Mirror", queue_tag="laboratory_general"
    )
    # Каталог «изменился после записи»: записано 100/усл., каталог теперь 150
    service.price = Decimal("150")
    db_session.commit()

    queue = _create_queue(
        db_session, specialist_id=test_doctor.id, queue_tag="laboratory_general", day=date.today()
    )
    visit = _create_visit(db_session, patient=test_patient, doctor_id=test_doctor.id, department="laboratory_general")
    entry = _create_entry(
        db_session, queue=queue, patient=test_patient, service=service,
        quantity=3, price=100, total_amount=300, visit_id=visit.id,
    )

    quote = _quote_edit_delta(
        client, registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": service.id, "quantity": 1}],
        preferred_entry_ids=[entry.id],
    )

    item = quote["items"][0]
    assert int(item["quantity"]) == -2  # дельта снижения
    assert Decimal(str(item["final_price"])) == Decimal("-200.00")  # 2 × записанные 100, не 2 × 150
    assert Decimal(str(quote["total_amount"])) == Decimal("-200.00")


# ===================== PROCESSING-СЧЁТ (item 2) =====================


@pytest.mark.integration
@pytest.mark.queue
def test_decrease_blocked_for_processing_invoice(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    """Счёт в processing (платёж у провайдера): снижение запрещено с явной
    причиной — иначе очередь/визит уменьшились бы, а счёт остался прежним."""
    service = _create_service(
        db_session, code="R8-PROC-01", name="R8 Processing", queue_tag="laboratory_general"
    )
    queue = _create_queue(
        db_session, specialist_id=test_doctor.id, queue_tag="laboratory_general", day=date.today()
    )
    visit = _create_visit(db_session, patient=test_patient, doctor_id=test_doctor.id, department="laboratory_general")
    entry = _create_entry(
        db_session, queue=queue, patient=test_patient, service=service,
        quantity=2, price=25000, total_amount=50000, visit_id=visit.id,
    )
    _create_invoice(db_session, patient=test_patient, visit=visit, amount=50000, status="processing")

    response = _post_edit_delta(
        client, registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": service.id, "quantity": 1}],
        entry_ids=[entry.id],
    )

    assert response.status_code == 400, response.text
    assert "обработка платежа" in response.json()["detail"]
    payload = _payload(db_session, entry.id)
    assert payload["quantity"] == 2  # состояние не изменено


# ===================== ИДЕНТИЧНОСТЬ ЗАПИСИ (item 3) =====================


@pytest.mark.integration
@pytest.mark.queue
def test_queue_entry_id_routes_mutation_to_named_entry(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    """Один service_id в ДВУХ записях одного дня (агрегированная правка):
    правка с явным queue_entry_id мутирует названную запись B, а не
    «ближайшую» A из глобального preferred-набора."""
    service = _create_service(
        db_session, code="R8-IDT-01", name="R8 Identity", queue_tag="laboratory_general"
    )
    queue = _create_queue(
        db_session, specialist_id=test_doctor.id, queue_tag="laboratory_general", day=date.today()
    )
    # A создана раньше (меньший id) — глобальный preferred выбрал бы её
    entry_a = _create_entry(
        db_session, queue=queue, patient=test_patient, service=service,
        quantity=1, price=25000, total_amount=25000,
    )
    entry_b = _create_entry(
        db_session, queue=queue, patient=test_patient, service=service,
        quantity=5, price=25000, total_amount=125000,
    )
    assert entry_a.id < entry_b.id

    # Правим позицию, называя запись B; глобальный preferred содержит ОБЕ
    response = _post_edit_delta(
        client, registrar_auth_headers,
        patient_id=test_patient.id,
        services=[
            {"service_id": service.id, "quantity": 7, "queue_entry_id": entry_b.id}
        ],
        entry_ids=[entry_a.id, entry_b.id],
    )

    assert response.status_code == 200, response.text
    payload_a = _payload(db_session, entry_a.id)
    assert payload_a["quantity"] == 1  # A не тронута
    payload_b = _payload(db_session, entry_b.id)
    assert payload_b["quantity"] == 7  # B выросла до целевого количества


@pytest.mark.integration
@pytest.mark.queue
def test_quote_routes_by_item_queue_entry_id(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    """Квота биллит дельту ПО именованной записи: запись B имеет 5 позиций,
    запрошено 6 → дельта +1, а не +5 (как посчитала бы ближайшая запись A)."""
    service = _create_service(
        db_session, code="R8-IDQ-01", name="R8 IdQuote", queue_tag="laboratory_general"
    )
    queue = _create_queue(
        db_session, specialist_id=test_doctor.id, queue_tag="laboratory_general", day=date.today()
    )
    entry_a = _create_entry(
        db_session, queue=queue, patient=test_patient, service=service,
        quantity=1, price=25000, total_amount=25000,
    )
    entry_b = _create_entry(
        db_session, queue=queue, patient=test_patient, service=service,
        quantity=5, price=25000, total_amount=125000,
    )

    quote = _quote_edit_delta(
        client, registrar_auth_headers,
        patient_id=test_patient.id,
        services=[
            {"service_id": service.id, "quantity": 6, "queue_entry_id": entry_b.id}
        ],
        preferred_entry_ids=[entry_a.id, entry_b.id],
    )

    assert Decimal(str(quote["total_amount"])) == PRICE  # дельта 5→6 = 1×цена


# ===================== CODEX R9 PR 3115 =====================


@pytest.mark.integration
@pytest.mark.queue
def test_decrease_blocked_for_expired_visit(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    """Codex R9 PR 3115 (P1): expired — терминальный статус SSOT
    visit_lifecycle_service. Снижение по визиту с истёкшим подтверждением
    запрещено с явной причиной: мутировать терминальный визит нельзя, а если
    его запись уже не appendable — команда не должна создавать дубликат
    визита для той же услуги и дня."""
    service = _create_service(
        db_session, code="R9-EXP-01", name="R9 Expired", queue_tag="laboratory_general"
    )
    queue = _create_queue(
        db_session, specialist_id=test_doctor.id, queue_tag="laboratory_general", day=date.today()
    )
    visit = _create_visit(db_session, patient=test_patient, doctor_id=test_doctor.id, department="laboratory_general")
    visit.status = "expired"
    db_session.commit()
    entry = _create_entry(
        db_session, queue=queue, patient=test_patient, service=service,
        quantity=2, price=25000, total_amount=50000, visit_id=visit.id,
    )

    response = _post_edit_delta(
        client, registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": service.id, "quantity": 1}],
        entry_ids=[entry.id],
    )

    assert response.status_code == 400, response.text
    assert "выполнена или отменена" in response.json()["detail"]
    payload = _payload(db_session, entry.id)
    assert payload["quantity"] == 2  # состояние не изменено


@pytest.mark.parametrize("payment_status", ["paid", "processing", "completed"])
@pytest.mark.integration
@pytest.mark.queue
def test_decrease_blocked_by_canonical_payment_row_without_synced_invoice(
    client, db_session, registrar_auth_headers, test_patient, test_doctor, payment_status
):
    """Codex R9 PR 3115 (P1): кассовые потоки коммитят Payment (paid/completed)
    БЕЗ синхронной PaymentInvoice — счёт отсутствует или остаётся pending.
    Гард, проверяющий только PaymentInvoice.status, пропускал снижение и
    уменьшение устаревшего pending-счёта без возврата денег. Канонические
    строки Payment блокируют снижение так же, как оплаченный счёт."""
    from app.models.payment import Payment

    service = _create_service(
        db_session, code=f"R9-PAY-{payment_status[:3].upper()}", name="R9 Payment", queue_tag="laboratory_general"
    )
    queue = _create_queue(
        db_session, specialist_id=test_doctor.id, queue_tag="laboratory_general", day=date.today()
    )
    visit = _create_visit(db_session, patient=test_patient, doctor_id=test_doctor.id, department="laboratory_general")
    db_session.add(Payment(visit_id=visit.id, amount=Decimal("50000"), currency="UZS", method="cash", status=payment_status))
    db_session.commit()
    entry = _create_entry(
        db_session, queue=queue, patient=test_patient, service=service,
        quantity=2, price=25000, total_amount=50000, visit_id=visit.id,
    )

    response = _post_edit_delta(
        client, registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": service.id, "quantity": 1}],
        entry_ids=[entry.id],
    )

    assert response.status_code == 400, response.text
    assert "зарегистрирована оплата" in response.json()["detail"]
    payload = _payload(db_session, entry.id)
    assert payload["quantity"] == 2  # состояние не изменено


@pytest.mark.integration
@pytest.mark.queue
def test_decrease_on_visit_only_record_rejected_not_duplicated(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    """Codex R9 PR 3118 (P1): visit-only строка (визит есть, записи очереди
    нет). Раньше edit-delta не находил активную запись и вызывал
    _create_new_queue_entry — второй визит с целевым количеством при
    нетронутом исходном VisitService. Теперь — громкий отказ: правка
    количества позиции на активном визите дня выполняется через
    корректировку визита, а не через редактирование корзины."""
    from app.models.visit import VisitService

    service = _create_service(
        db_session, code="R9-VONLY-1", name="R9 VisitOnly", queue_tag="laboratory_general"
    )
    visit = _create_visit(db_session, patient=test_patient, doctor_id=test_doctor.id, department="laboratory_general")
    db_session.add(
        VisitService(
            visit_id=visit.id,
            service_id=service.id,
            code=service.service_code,
            name=service.name,
            qty=2,
            price=PRICE,
            currency="UZS",
        )
    )
    db_session.commit()

    response = _post_edit_delta(
        client, registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": service.id, "quantity": 1}],
        entry_ids=[],
    )

    assert response.status_code == 400, response.text
    assert "привязана к визиту" in response.json()["detail"]
    db_session.expire_all()
    vs = (
        db_session.query(VisitService)
        .filter(VisitService.visit_id == visit.id, VisitService.service_id == service.id)
        .one()
    )
    assert vs.qty == 2  # исходная позиция не изменена
    visits = (
        db_session.query(Visit)
        .filter(Visit.patient_id == test_patient.id)
        .count()
    )
    assert visits == 1  # дублирующий визит НЕ создан


@pytest.mark.integration
@pytest.mark.queue
def test_adding_new_service_to_visit_only_record_still_works(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    """Легитимный путь не сломан: добавление НОВОЙ услуги (не привязанной к
    визитам дня) в visit-only запись по-прежнему создаёт позицию."""
    existing = _create_service(
        db_session, code="R9-VONLY-E", name="R9 Existing", queue_tag="laboratory_general"
    )
    fresh = _create_service(
        db_session, code="R9-VONLY-N", name="R9 New", queue_tag="laboratory_general"
    )
    _create_queue(
        db_session, specialist_id=test_doctor.id, queue_tag="laboratory_general", day=date.today()
    )
    visit = _create_visit(db_session, patient=test_patient, doctor_id=test_doctor.id, department="laboratory_general")
    from app.models.visit import VisitService

    db_session.add(
        VisitService(
            visit_id=visit.id,
            service_id=existing.id,
            code=existing.service_code,
            name=existing.name,
            qty=1,
            price=PRICE,
            currency="UZS",
        )
    )
    db_session.commit()

    response = _post_edit_delta(
        client, registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": fresh.id, "quantity": 1}],
        entry_ids=[],
    )

    assert response.status_code == 200, response.text
