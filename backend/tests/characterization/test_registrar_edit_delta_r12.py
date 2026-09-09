"""Codex R12 PR 3118 — исправления: LIFO-представление позиции (P1 :758),
гвард снижения в edit-квоте (P2 :522).

Ключевой сценарий codex (P1): рост 2×100 до 3 при каталоге 101 даёт точную
сумму строки 301. Единая строка VisitService с ценой Numeric(12,2) НЕ МОЖЕТ
представить 301/3: прежнее смешивание хранило 100.33×3 = 300.99 против
entry.total_amount = 301 (INTEGER) и invoice 301 — compute_total_cost видел
300.99, повторные снижения накапливали расхождение. СЛОИ точны при любых
ценах: рост добавляет слой (дельта × каталог, без округления), снижение
потребляет слои с конца, VisitService зеркалит слои payload.

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

TZ = ZoneInfo("Asia/Tashkent")


def _create_service(db_session, *, code: str, price: int) -> Service:
    service = Service(
        code=code,
        service_code=code,
        name=f"R12 {code}",
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
        notes="r12-test",
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


def _quote_edit_delta(client, registrar_auth_headers, *, patient_id, services, preferred_entry_ids):
    """Сырой ответ квоты: коды 200/400 проверяются в кейсах."""
    return client.post(
        "/api/v1/registrar/cart/quote",
        headers=registrar_auth_headers,
        json={
            "items": services,
            "discount_mode": "none",
            "all_free": False,
            "pricing_mode": "edit_delta",
            "patient_id": patient_id,
            "target_date": date.today().isoformat(),
            "preferred_entry_ids": preferred_entry_ids,
        },
    )


def _layers(db_session, entry_id: int) -> list[dict]:
    db_session.expire_all()
    entry = db_session.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).first()
    return list(entry.services or [])


def _layer_totals(db_session, entry_id: int, visit_id: int, service_id: int) -> tuple[Decimal, Decimal, Decimal]:
    """(Σ VisitService-строк, Σ payload-слоёв, entry.total_amount)."""
    db_session.expire_all()
    entry = db_session.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).first()
    visit_total = sum(
        (
            Decimal(str(r.price)) * r.qty
            for r in db_session.query(VisitService)
            .filter(VisitService.visit_id == visit_id, VisitService.service_id == service_id)
            .order_by(VisitService.id.asc())
            .all()
        ),
        Decimal("0"),
    )
    payload_total = sum(
        (
            Decimal(str(p.get("unit_price") if p.get("unit_price") is not None else p.get("price") or 0))
            * int(p.get("quantity") or p.get("qty") or 1)
            for p in (entry.services or [])
        ),
        Decimal("0"),
    )
    return visit_total, payload_total, Decimal(str(entry.total_amount))


# ===================== P1: ТОЧНОСТЬ СЛОЁВ (сценарий codex 301) =====================


@pytest.mark.integration
@pytest.mark.queue
def test_growth_with_indivisible_line_total_stays_exact(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    """Сценарий codex: 2×100 записано, каталог стал 101, рост до 3.
    Точная сумма строки 301 НЕ представима единичной ценой Numeric(12,2)
    (301/3 = 100.33(3)); прежний blend писал 100.33×3 = 300.99 против
    entry/invoice 301. Слои: базовый слой 2×100 сохраняется, добавляется
    слой 1×101 — все представления сходятся к 301."""
    service = _create_service(db_session, code="R12-EX-01", price=100)
    queue = _create_queue(db_session, specialist_id=test_doctor.id, queue_tag="laboratory_general", day=date.today())
    visit = _create_visit_with_row(
        db_session, patient=test_patient, doctor_id=test_doctor.id,
        department="laboratory_general", service=service, qty=2, price=100,
    )
    entry = _create_entry(
        db_session, queue=queue, patient=test_patient, service=service,
        quantity=2, unit_price=100, total_amount=200, visit_id=visit.id,
    )
    invoice = _create_invoice(db_session, patient=test_patient, visit=visit, amount=200)

    service.price = Decimal("101")
    db_session.commit()

    response = _post_edit_delta(
        client, registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": service.id, "quantity": 3, "specialist_id": None, "queue_entry_id": entry.id}],
        entry_ids=[entry.id],
    )
    assert response.status_code == 200, response.text
    assert Decimal(str(response.json()["total_amount"])) == Decimal("101")  # дельта по каталогу, БЕЗ округления

    db_session.expire_all()
    db_session.refresh(entry)
    assert len(entry.services) == 2  # слои: 2×100 + 1×101
    assert entry.services[0]["quantity"] == 2
    assert Decimal(str(entry.services[0]["unit_price"])) == Decimal("100.00")
    assert entry.services[1]["quantity"] == 1
    assert Decimal(str(entry.services[1]["unit_price"])) == Decimal("101.00")
    assert entry.total_amount == 301  # точно, не 300.99

    rows = (
        db_session.query(VisitService)
        .filter(VisitService.visit_id == visit.id, VisitService.service_id == service.id)
        .order_by(VisitService.id.asc())
        .all()
    )
    assert [(r.qty, Decimal(str(r.price))) for r in rows] == [(2, Decimal("100.00")), (1, Decimal("101.00"))]

    db_session.refresh(invoice)
    assert invoice.total_amount == Decimal("301")

    invariant = PaymentInvariantService(db_session).compute_total_cost(visit)
    assert invariant == Decimal("301")
    visit_total, payload_total, entry_total = _layer_totals(db_session, entry.id, visit.id, service.id)
    assert visit_total == payload_total == entry_total == Decimal("301")


@pytest.mark.integration
@pytest.mark.queue
def test_decrease_spanning_layers_consumes_lifo_and_stays_exact(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    """Снижение 3→1 ПЕРЕСЕКАЕТ слои (2×100 + 1×101 → 1×100): последний слой
    снимается целиком (−101), затем 1 единица базового (−100) → списание
    −201. Представления: слой 1×100, entry 100, invoice 100 — точно."""
    service = _create_service(db_session, code="R12-EX-02", price=100)
    queue = _create_queue(db_session, specialist_id=test_doctor.id, queue_tag="laboratory_general", day=date.today())
    visit = _create_visit_with_row(
        db_session, patient=test_patient, doctor_id=test_doctor.id,
        department="laboratory_general", service=service, qty=2, price=100,
    )
    entry = _create_entry(
        db_session, queue=queue, patient=test_patient, service=service,
        quantity=2, unit_price=100, total_amount=200, visit_id=visit.id,
    )
    _create_invoice(db_session, patient=test_patient, visit=visit, amount=200)

    service.price = Decimal("101")
    db_session.commit()
    up = _post_edit_delta(
        client, registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": service.id, "quantity": 3, "specialist_id": None, "queue_entry_id": entry.id}],
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
    assert Decimal(str(down.json()["total_amount"])) == Decimal("-201")

    visit_total, payload_total, entry_total = _layer_totals(db_session, entry.id, visit.id, service.id)
    assert visit_total == payload_total == entry_total == Decimal("100")

    invariant = PaymentInvariantService(db_session).compute_total_cost(visit)
    assert invariant == Decimal("100")


@pytest.mark.integration
@pytest.mark.queue
def test_multi_layer_growth_accumulates_and_decrease_consumes_last(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    """Три слоя (1×100 + 1×150 + 1×200 = 450), затем снижение 3→2 снимает
    последний слой (−200) — представление остаётся точным на каждом шаге."""
    service = _create_service(db_session, code="R12-EX-03", price=100)
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

    for catalog_price, target in ((150, 2), (200, 3)):
        service.price = Decimal(catalog_price)
        db_session.commit()
        response = _post_edit_delta(
            client, registrar_auth_headers,
            patient_id=test_patient.id,
            services=[{"service_id": service.id, "quantity": target, "specialist_id": None, "queue_entry_id": entry.id}],
            entry_ids=[entry.id],
        )
        assert response.status_code == 200, response.text

    visit_total, payload_total, entry_total = _layer_totals(db_session, entry.id, visit.id, service.id)
    assert visit_total == payload_total == entry_total == Decimal("450")

    down = _post_edit_delta(
        client, registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": service.id, "quantity": 2, "specialist_id": None, "queue_entry_id": entry.id}],
        entry_ids=[entry.id],
    )
    assert down.status_code == 200, down.text
    assert Decimal(str(down.json()["total_amount"])) == Decimal("-200")

    visit_total, payload_total, entry_total = _layer_totals(db_session, entry.id, visit.id, service.id)
    assert visit_total == payload_total == entry_total == Decimal("250")


# ===================== P1: ЗЕРКАЛА КВОТЫ (LIFO) =====================


@pytest.mark.integration
@pytest.mark.queue
def test_decrease_quote_mirrors_lifo_layer_amount(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    """Квота снижения токенизирует ГОТОВУЮ сумму потреблённых слоёв (−201),
    а не единичную цену × дельту — при многослойном потреблении единой цены
    за единицу не существует. Сумма квоты == сумма команды."""
    service = _create_service(db_session, code="R12-QM-01", price=100)
    queue = _create_queue(db_session, specialist_id=test_doctor.id, queue_tag="laboratory_general", day=date.today())
    visit = _create_visit_with_row(
        db_session, patient=test_patient, doctor_id=test_doctor.id,
        department="laboratory_general", service=service, qty=2, price=100,
    )
    entry = _create_entry(
        db_session, queue=queue, patient=test_patient, service=service,
        quantity=2, unit_price=100, total_amount=200, visit_id=visit.id,
    )
    _create_invoice(db_session, patient=test_patient, visit=visit, amount=200)

    service.price = Decimal("101")
    db_session.commit()
    up = _post_edit_delta(
        client, registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": service.id, "quantity": 3, "specialist_id": None, "queue_entry_id": entry.id}],
        entry_ids=[entry.id],
    )
    assert up.status_code == 200, up.text

    quote = _quote_edit_delta(
        client, registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": service.id, "quantity": 1, "specialist_id": None, "queue_entry_id": entry.id}],
        preferred_entry_ids=[entry.id],
    ).json()
    assert Decimal(str(quote["total_amount"])) == Decimal("-201")
    item = next(i for i in quote["items"] if i["service_id"] == service.id)
    assert Decimal(str(item["final_price"])) == Decimal("-201")

    # И команда списывает ту же сумму — подтверждённая квота == invoice
    down = _post_edit_delta(
        client, registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": service.id, "quantity": 1, "specialist_id": None, "queue_entry_id": entry.id}],
        entry_ids=[entry.id],
    )
    assert down.status_code == 200, down.text
    assert Decimal(str(down.json()["total_amount"])) == Decimal("-201")


@pytest.mark.integration
@pytest.mark.queue
def test_growth_quote_stays_exact_when_line_total_indivisible(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    """Квота роста при слоях — каталог × дельта (101), ровно то, что спишет
    команда (дельта слоя не смешивается, округлять нечего)."""
    service = _create_service(db_session, code="R12-QM-02", price=100)
    queue = _create_queue(db_session, specialist_id=test_doctor.id, queue_tag="laboratory_general", day=date.today())
    visit = _create_visit_with_row(
        db_session, patient=test_patient, doctor_id=test_doctor.id,
        department="laboratory_general", service=service, qty=2, price=100,
    )
    entry = _create_entry(
        db_session, queue=queue, patient=test_patient, service=service,
        quantity=2, unit_price=100, total_amount=200, visit_id=visit.id,
    )
    _create_invoice(db_session, patient=test_patient, visit=visit, amount=200)

    service.price = Decimal("101")
    db_session.commit()

    quote = _quote_edit_delta(
        client, registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": service.id, "quantity": 3, "specialist_id": None, "queue_entry_id": entry.id}],
        preferred_entry_ids=[entry.id],
    ).json()
    assert Decimal(str(quote["total_amount"])) == Decimal("101")


# ===================== P2 :522 — ГВАРД СНИЖЕНИЯ В КВОТЕ =====================


@pytest.mark.integration
@pytest.mark.queue
def test_decrease_quote_rejected_when_invoice_paid(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    """Оплаченный счёт: квота подтверждает снижение только для команд, которые
    контракт принимает. Гвард зеркалится в квоту ДО выпуска токена — 400 с
    той же причиной, что и на сохранении."""
    service = _create_service(db_session, code="R12-QG-01", price=100)
    queue = _create_queue(db_session, specialist_id=test_doctor.id, queue_tag="laboratory_general", day=date.today())
    visit = _create_visit_with_row(
        db_session, patient=test_patient, doctor_id=test_doctor.id,
        department="laboratory_general", service=service, qty=3, price=100,
    )
    entry = _create_entry(
        db_session, queue=queue, patient=test_patient, service=service,
        quantity=3, unit_price=100, total_amount=300, visit_id=visit.id,
    )
    _create_invoice(db_session, patient=test_patient, visit=visit, amount=300, status="paid")

    response = _quote_edit_delta(
        client, registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": service.id, "quantity": 1, "specialist_id": None, "queue_entry_id": entry.id}],
        preferred_entry_ids=[entry.id],
    )
    assert response.status_code == 400, response.text
    assert "оплаченный счёт" in response.json()["detail"]


@pytest.mark.integration
@pytest.mark.queue
def test_decrease_quote_rejected_while_provider_payment_pending(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    """Инициализированный провайдерский pending-платёж: квота не подтверждает
    снижение, которое apply() отвергнет (та же причина «неоплаченный
    онлайн-платёж»)."""
    service = _create_service(db_session, code="R12-QG-02", price=100)
    queue = _create_queue(db_session, specialist_id=test_doctor.id, queue_tag="laboratory_general", day=date.today())
    visit = _create_visit_with_row(
        db_session, patient=test_patient, doctor_id=test_doctor.id,
        department="laboratory_general", service=service, qty=3, price=100,
    )
    entry = _create_entry(
        db_session, queue=queue, patient=test_patient, service=service,
        quantity=3, unit_price=100, total_amount=300, visit_id=visit.id,
    )
    _create_invoice(db_session, patient=test_patient, visit=visit, amount=300)

    PaymentInvariantService(db_session).create_pending_payment(
        visit_id=visit.id,
        amount=Decimal("300"),
        currency="UZS",
        method="online",
        provider="click",
        note="r12-quote-guard",
        current_user=type("UserRef", (), {"id": None})(),
    )

    response = _quote_edit_delta(
        client, registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": service.id, "quantity": 1, "specialist_id": None, "queue_entry_id": entry.id}],
        preferred_entry_ids=[entry.id],
    )
    assert response.status_code == 400, response.text
    assert "неоплаченный онлайн-платёж" in response.json()["detail"]


@pytest.mark.integration
@pytest.mark.queue
def test_decrease_quote_rejected_for_terminal_visit(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    """Терминальный статус визита (closed): позиция потреблена — квота
    снижения отвечает 400 («уже выполнена или отменена») вместо готовой
    отрицательной корректировки."""
    service = _create_service(db_session, code="R12-QG-03", price=100)
    queue = _create_queue(db_session, specialist_id=test_doctor.id, queue_tag="laboratory_general", day=date.today())
    visit = _create_visit_with_row(
        db_session, patient=test_patient, doctor_id=test_doctor.id,
        department="laboratory_general", service=service, qty=3, price=100,
    )
    visit.status = "closed"
    db_session.commit()
    entry = _create_entry(
        db_session, queue=queue, patient=test_patient, service=service,
        quantity=3, unit_price=100, total_amount=300, visit_id=visit.id,
    )

    response = _quote_edit_delta(
        client, registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": service.id, "quantity": 1, "specialist_id": None, "queue_entry_id": entry.id}],
        preferred_entry_ids=[entry.id],
    )
    assert response.status_code == 400, response.text
    assert "уменьшение количества недоступно" in response.json()["detail"]


@pytest.mark.integration
@pytest.mark.queue
def test_decrease_quote_allowed_when_guard_passes(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    """Негативный контроль: гвард проходит (pending-платёж отменён) — квота
    снижения снова выпускается с точной суммой слоя."""
    service = _create_service(db_session, code="R12-QG-04", price=100)
    queue = _create_queue(db_session, specialist_id=test_doctor.id, queue_tag="laboratory_general", day=date.today())
    visit = _create_visit_with_row(
        db_session, patient=test_patient, doctor_id=test_doctor.id,
        department="laboratory_general", service=service, qty=3, price=100,
    )
    entry = _create_entry(
        db_session, queue=queue, patient=test_patient, service=service,
        quantity=3, unit_price=100, total_amount=300, visit_id=visit.id,
    )
    _create_invoice(db_session, patient=test_patient, visit=visit, amount=300)

    payment = PaymentInvariantService(db_session).create_pending_payment(
        visit_id=visit.id,
        amount=Decimal("300"),
        currency="UZS",
        method="online",
        provider="click",
        note="r12-quote-guard-neg",
        current_user=type("UserRef", (), {"id": None})(),
    )
    payment.status = "cancelled"
    db_session.commit()

    quote = _quote_edit_delta(
        client, registrar_auth_headers,
        patient_id=test_patient.id,
        services=[{"service_id": service.id, "quantity": 1, "specialist_id": None, "queue_entry_id": entry.id}],
        preferred_entry_ids=[entry.id],
    ).json()
    assert quote["total_amount"] is not None
    assert Decimal(str(quote["total_amount"])) == Decimal("-200")
