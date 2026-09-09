"""Codex R10 #3115 — исправления P1: forward queue_entry_id (адаптер —
frontend-тест), сохранение записанной стоимости при росте, блокировка счёта
при снижении.

Codex R12 PR 3118 (P1): рост больше НЕ смешивает позицию средневзвешенной
ценой за единицу (при неделимой сумме строки — 2×100 + 1×101 = 301 — квант
до 2 знаков рвал инвариант VisitService ≠ entry.total_amount). Вместо
этого — СЛОЕВОЕ (LIFO) представление: рост добавляет слой (дельта ×
каталог), VisitService-строки зеркалят слои payload. Инвариант прежний и
теперь ТОЧНЫЙ: Σ (price×qty) строк VisitService == Σ unit×qty слоёв payload
== entry.total_amount == invoice.

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


def _visit_service_rows(db_session, visit_id: int, service_id: int) -> list[VisitService]:
    """Codex R12 PR 3118 (P1): ВСЕ строки позиции (слои), в порядке записи."""
    db_session.expire_all()
    return (
        db_session.query(VisitService)
        .filter(VisitService.visit_id == visit_id, VisitService.service_id == service_id)
        .order_by(VisitService.id.asc())
        .all()
    )


def _layers_invariant(db_session, entry_id: int, visit_id: int, service_id: int) -> tuple[Decimal, Decimal, Decimal]:
    """Возвращает (Σ VisitService, Σ payload-слоёв, entry.total_amount)."""
    db_session.expire_all()
    entry = db_session.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).first()
    visit_total = sum(
        (Decimal(str(r.price)) * r.qty for r in _visit_service_rows(db_session, visit_id, service_id)),
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


# ===================== P1: РОСТ СОХРАНЯЕТ ЗАПИСАННУЮ СТОИМОСТЬ =====================


@pytest.mark.integration
@pytest.mark.queue
def test_increase_with_catalog_change_layers_recorded_and_delta_cost(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    """Визит записан 1×100, каталог изменился на 150, рост 1→2:
    счёт выставляет только дельту (+150) → итог 250. СЛОЙ (Codex R12 PR 3118
    P1): строка базового слоя сохраняет записанную цену (1×100), дельта —
    новый слой (1×150); VisitService-строки зеркалят слои payload.
    Инвариант ТОЧЕН: Σ строк VisitService == Σ слоёв payload ==
    entry.total_amount == invoice (250) — иначе compute_total_cost считал бы
    иную каноническую стоимость и собирал бы лишние/недостающие деньги."""
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

    # Повторное чтение: слои согласованы, базовый слой НЕ переписан
    rows = _visit_service_rows(db_session, visit.id, service.id)
    assert [(r.qty, Decimal(str(r.price))) for r in rows] == [(1, Decimal("100.00")), (1, Decimal("150.00"))]

    db_session.expire_all()
    db_session.refresh(entry)
    assert len(entry.services) == 2
    assert entry.services[0]["quantity"] == 1 and Decimal(str(entry.services[0]["unit_price"])) == Decimal("100.00")
    assert entry.services[1]["quantity"] == 1 and Decimal(str(entry.services[1]["unit_price"])) == Decimal("150.00")
    assert entry.total_amount == 250

    db_session.refresh(invoice)
    assert invoice.total_amount == Decimal("250")
    assert invoice.status == "pending"

    # Каноническая стоимость визита == сумма счёта — лишнего долга нет
    invariant = PaymentInvariantService(db_session).compute_total_cost(visit)
    assert invariant == Decimal("250")
    # Полный инвариант слоёв
    visit_total, payload_total, entry_total = _layers_invariant(db_session, entry.id, visit.id, service.id)
    assert visit_total == payload_total == entry_total == Decimal("250")


@pytest.mark.integration
@pytest.mark.queue
def test_increase_without_catalog_change_keeps_catalog_price(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    """Без изменения цены рост ведёт себя как раньше: слой биллится по
    каталоговой цене, счёт — дельта (1×100 → 2: итог 200 = 100 + 100).
    Слои (Codex R12 PR 3118 P1): базовый слой не переписывается."""
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

    rows = _visit_service_rows(db_session, visit.id, service.id)
    assert [(r.qty, Decimal(str(r.price))) for r in rows] == [(1, Decimal("100.00")), (1, Decimal("100.00"))]
    db_session.expire_all()
    db_session.refresh(entry)
    assert entry.total_amount == 200
    assert len(entry.services) == 2
    assert Decimal(str(entry.services[0]["unit_price"])) == Decimal("100.00")


@pytest.mark.integration
@pytest.mark.queue
def test_decrease_after_growth_consumes_last_layer_and_representations_agree(
    client, db_session, registrar_auth_headers, test_patient, test_doctor
):
    """Последующее снижение после роста ПОТРЕБЛЯЕТ ПОСЛЕДНИЙ слой (LIFO):
    возвращаются последние добавленные единицы. 1×100, рост до 2 (слой 1×150,
    итог 250), снижение до 1 → слой 1×150 снимается целиком (−150),
    остаётся базовый слой 1×100. Строка, пейлоад, entry и счёт согласованы
    (100 = 100 = 100 = 100)."""
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
    assert Decimal(str(down.json()["total_amount"])) == Decimal("-150")  # снят слой 1×150

    rows = _visit_service_rows(db_session, visit.id, service.id)
    assert [(r.qty, Decimal(str(r.price))) for r in rows] == [(1, Decimal("100.00"))]
    db_session.expire_all()
    db_session.refresh(entry)
    assert entry.total_amount == 100
    assert len(entry.services) == 1
    assert Decimal(str(entry.services[0]["unit_price"])) == Decimal("100.00")

    db_session.expire_all()
    invoice = (
        db_session.query(PaymentInvoice)
        .filter(PaymentInvoice.patient_id == test_patient.id, PaymentInvoice.status == "pending")
        .first()
    )
    assert invoice is not None
    assert invoice.total_amount == Decimal("100")

    visit_total, payload_total, entry_total = _layers_invariant(db_session, entry.id, visit.id, service.id)
    assert visit_total == payload_total == entry_total == Decimal("100")


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
