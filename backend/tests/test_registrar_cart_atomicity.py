"""
Fix C: атомарность корзины регистратора и идемпотентность повторной отправки.

Оригинальный дефект: crud create_visit() делал db.commit() внутри, а
/registrar/cart вызывал его в цикле. Сбой на позднем визите, invoice или
очереди оставлял уже закоммиченные визиты в БД — db.rollback() в except
был бессилен против внутренних коммитов.

Fix: create_visit(commit=False) со стороны cart endpoint — единственный
commit делает сам endpoint после визитов, invoice, invoice-visit связей
и назначения очереди.

Проверки идемпотентности (IdempotencyMiddleware, PR-6): повторная отправка
с тем же Idempotency-Key возвращает кэшированный ответ и не создаёт вторую
корзину; новый ключ — новая операция.

Эти тесты прогоняются на SQLite-харнессе conftest. Отдельной disposable
PostgreSQL в среде выполнения нет — транзакционные гарантии под реальным
PostgreSQL отдельно НЕ проверялись и здесь не заявляются.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1.endpoints.registrar_wizard import _cart as cart_module
from app.crud.clinic import clinic_today
from app.models.online_queue import QueueResource
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.service import Service
from app.models.visit import Visit, VisitService
from tests.conftest import mint_access_token

pytestmark = [pytest.mark.integration]


def _cart_payload(*, patient_id: int, visits: list[dict]) -> dict:
    return {
        "patient_id": patient_id,
        "discount_mode": "none",
        "payment_method": "cash",
        "visits": visits,
    }


def _visit(service_id: int, *, doctor_id: int | None = None) -> dict:
    return {
        "doctor_id": doctor_id,
        "visit_date": date.today().isoformat(),
        "department": "general",
        "services": [{"service_id": service_id, "quantity": 1}],
    }


def _auth_headers(admin_user) -> dict[str, str]:
    return {"Authorization": f"Bearer {mint_access_token(admin_user)}"}


def _counts(db: Session, patient_id: int) -> tuple[int, int, int]:
    visits = db.query(Visit).filter(Visit.patient_id == patient_id).count()
    invoices = (
        db.query(PaymentInvoice)
        .filter(PaymentInvoice.patient_id == patient_id)
        .count()
    )
    invoice_visits = (
        db.query(PaymentInvoiceVisit)
        .join(PaymentInvoice, PaymentInvoice.id == PaymentInvoiceVisit.invoice_id)
        .filter(PaymentInvoice.patient_id == patient_id)
        .count()
    )
    return visits, invoices, invoice_visits


def test_multi_visit_cart_is_atomic_and_complete(
    client: TestClient, db_session: Session, admin_user, test_patient
):
    """Успешная корзина из двух визитов создаёт visits + invoice + связи."""
    service_a = Service(
        code="FIXC-A",
        name="Fix C Service A",
        price=100000.00,
        duration_minutes=30,
        active=True,
        requires_doctor=False,
        is_consultation=False,
    )
    service_b = Service(
        code="FIXC-B",
        name="Fix C Service B",
        price=50000.00,
        duration_minutes=30,
        active=True,
        requires_doctor=False,
        is_consultation=False,
    )
    db_session.add_all([service_a, service_b])
    db_session.commit()
    db_session.refresh(service_a)
    db_session.refresh(service_b)

    before = _counts(db_session, test_patient.id)

    response = client.post(
        "/api/v1/registrar/cart",
        headers=_auth_headers(admin_user),
        json=_cart_payload(
            patient_id=test_patient.id,
            visits=[
                _visit(service_a.id),
                _visit(service_b.id),
            ],
        ),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True
    assert len(payload["visit_ids"]) == 2

    visits, invoices, invoice_visits = _counts(db_session, test_patient.id)
    assert visits == before[0] + 2
    assert invoices == before[1] + 1
    assert invoice_visits == before[2] + 2

    # Итоговая сумма инвойса = 100000 + 50000 (количество × цена)
    invoice = (
        db_session.query(PaymentInvoice)
        .filter(PaymentInvoice.patient_id == test_patient.id)
        .order_by(PaymentInvoice.id.desc())
        .first()
    )
    assert invoice is not None
    assert invoice.total_amount == 150000


def test_second_visit_failure_leaves_no_partial_records(
    client: TestClient, db_session: Session, admin_user, test_patient
):
    """Сбой второго визита (несуществующая услуга) — в БД нет частичных записей."""
    service = Service(
        code="FIXC-C",
        name="Fix C Service C",
        price=100000.00,
        duration_minutes=30,
        active=True,
        requires_doctor=False,
        is_consultation=False,
    )
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)

    before = _counts(db_session, test_patient.id)

    response = client.post(
        "/api/v1/registrar/cart",
        headers=_auth_headers(admin_user),
        json=_cart_payload(
            patient_id=test_patient.id,
            visits=[
                _visit(service.id),  # первый визит валиден
                _visit(999999999),  # второй визит — услуга не найдена (404)
            ],
        ),
    )

    assert response.status_code == 404

    visits, invoices, invoice_visits = _counts(db_session, test_patient.id)
    assert visits == before[0], "первый визит НЕ должен остаться в БД"
    assert invoices == before[1], "invoice не должен создаваться при сбое"
    assert invoice_visits == before[2]


def test_invoice_failure_leaves_no_partial_records(
    client: TestClient,
    db_session: Session,
    admin_user,
    test_patient,
    monkeypatch,
):
    """Сбой создания invoice — визиты откатываются (транзакция одна)."""
    service = Service(
        code="FIXC-D",
        name="Fix C Service D",
        price=100000.00,
        duration_minutes=30,
        active=True,
        requires_doctor=False,
        is_consultation=False,
    )
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)

    before = _counts(db_session, test_patient.id)

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated invoice persistence failure")

    monkeypatch.setattr(cart_module, "PaymentInvoice", _boom)

    response = client.post(
        "/api/v1/registrar/cart",
        headers=_auth_headers(admin_user),
        json=_cart_payload(
            patient_id=test_patient.id,
            visits=[_visit(service.id)],
        ),
    )

    assert response.status_code == 500

    visits, invoices, invoice_visits = _counts(db_session, test_patient.id)
    assert visits == before[0], "визиты не должны остаться при сбое invoice"
    assert invoices == before[1]
    assert invoice_visits == before[2]


def test_queue_failure_leaves_no_partial_records(
    client: TestClient,
    db_session: Session,
    admin_user,
    test_patient,
    monkeypatch,
):
    """Сбой назначения очереди — вся корзина откатывается."""
    service = Service(
        code="FIXC-E",
        name="Fix C Service E",
        price=100000.00,
        duration_minutes=30,
        active=True,
        requires_doctor=False,
        is_consultation=False,
    )
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)

    before = _counts(db_session, test_patient.id)

    class _BrokenQueueService:
        def __init__(self, _db):
            pass

        def assign_same_day_queue_numbers(self, *_args, **_kwargs):
            raise RuntimeError("simulated queue assignment failure")

    monkeypatch.setattr(
        cart_module, "RegistrarWizardQueueAssignmentService", _BrokenQueueService
    )

    response = client.post(
        "/api/v1/registrar/cart",
        headers=_auth_headers(admin_user),
        json=_cart_payload(
            patient_id=test_patient.id,
            visits=[_visit(service.id)],
        ),
    )

    assert response.status_code == 500

    visits, invoices, invoice_visits = _counts(db_session, test_patient.id)
    assert visits == before[0], "визиты не должны остаться при сбое очереди"
    assert invoices == before[1]
    assert invoice_visits == before[2]


def test_idempotency_same_key_returns_cached_response_no_second_cart(
    client: TestClient, db_session: Session, admin_user, test_patient
):
    """Повторная отправка с тем же Idempotency-Key не создаёт вторую корзину."""
    service = Service(
        code="FIXC-F",
        name="Fix C Service F",
        price=100000.00,
        duration_minutes=30,
        active=True,
        requires_doctor=False,
        is_consultation=False,
    )
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)

    payload = _cart_payload(patient_id=test_patient.id, visits=[_visit(service.id)])
    headers = _auth_headers(admin_user) | {"Idempotency-Key": "fix-c-test-key-1"}

    first = client.post(
        "/api/v1/registrar/cart", headers=headers, json=payload
    )
    assert first.status_code == 200, first.text
    first_invoice_id = first.json()["invoice_id"]

    # «Потерянный ответ»: клиент повторяет ту же отправку с тем же ключом
    second = client.post(
        "/api/v1/registrar/cart", headers=headers, json=payload
    )
    assert second.status_code == 200
    assert second.json()["invoice_id"] == first_invoice_id, (
        "повтор с тем же ключом должен вернуть кэшированный ответ"
    )

    _, invoices, _ = _counts(db_session, test_patient.id)
    assert invoices == 1, "две отправки с одним ключом создали вторую корзину"


def test_idempotency_key_survives_token_refresh_same_user(
    client: TestClient, db_session: Session, admin_user, test_patient
):
    """A retry after refresh uses the same user's idempotency namespace."""
    service = Service(
        code="FIXR11-NS",
        name="R11 Namespace Service",
        price=100000.00,
        duration_minutes=30,
        active=True,
        requires_doctor=False,
        is_consultation=False,
    )
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)

    payload = _cart_payload(patient_id=test_patient.id, visits=[_visit(service.id)])
    key = "r11-namespace-refresh-key"

    # Попытка 1 — токен входа с неизменяемым user id:
    from app.services.authentication_service import authentication_service

    login_token = authentication_service.create_access_token(
        {"sub": str(admin_user.id), "auth_epoch": admin_user.auth_epoch}
    )
    first = client.post(
        "/api/v1/registrar/cart",
        headers={"Authorization": f"Bearer {login_token}", "Idempotency-Key": key},
        json=payload,
    )
    assert first.status_code == 200, first.text
    first_invoice_id = first.json()["invoice_id"]

    # Попытка 2 — «потерянный ответ», ретрай ПОСЛЕ refresh: токен формы
    # REFRESH (sub=user.id + username claim), тот же ключ и payload.
    second = client.post(
        "/api/v1/registrar/cart",
        headers=_auth_headers(admin_user) | {"Idempotency-Key": key},
        json=payload,
    )
    assert second.status_code == 200, second.text
    assert second.json()["invoice_id"] == first_invoice_id, (
        "ретрай после refresh-ротации токена должен вернуть закоммиченный ответ "
        "(один namespace на пользователя), а не создать вторую корзину"
    )

    _, invoices, _ = _counts(db_session, test_patient.id)
    assert invoices == 1, "дрейф namespace после refresh создал вторую корзину"


def test_idempotency_new_key_creates_new_operation(
    client: TestClient, db_session: Session, admin_user, test_patient
):
    """Новый Idempotency-Key — новая операция (создаётся новая корзина)."""
    service = Service(
        code="FIXC-G",
        name="Fix C Service G",
        price=100000.00,
        duration_minutes=30,
        active=True,
        requires_doctor=False,
        is_consultation=False,
    )
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)

    payload = _cart_payload(patient_id=test_patient.id, visits=[_visit(service.id)])
    base_headers = _auth_headers(admin_user)

    first = client.post(
        "/api/v1/registrar/cart",
        headers=base_headers | {"Idempotency-Key": "fix-c-test-key-2"},
        json=payload,
    )
    assert first.status_code == 200

    second = client.post(
        "/api/v1/registrar/cart",
        headers=base_headers | {"Idempotency-Key": "fix-c-test-key-3"},
        json=payload,
    )
    assert second.status_code == 200
    assert second.json()["invoice_id"] != first.json()["invoice_id"]

    _, invoices, _ = _counts(db_session, test_patient.id)
    assert invoices == 2, "новый ключ должен создавать новую корзину"


@pytest.mark.parametrize("unit_price", ["25000.00", "0.00"])
def test_cart_response_carries_scoped_price_for_issued_queue(
    client: TestClient, db_session: Session, admin_user, test_patient, unit_price: str
):
    tag = "synthetic_cart_ticket"
    resource = QueueResource(code=tag, queue_tag=tag, display_name="SYNTHETIC ticket")
    service = Service(
        code="SYNTHETIC-TICKET",
        service_code="SYNTHETIC-TICKET",
        name="SYNTHETIC ticket service",
        queue_tag=tag,
        price=Decimal(unit_price),
        requires_doctor=False,
        is_consultation=False,
        active=True,
    )
    db_session.add_all([resource, service])
    db_session.commit()

    visit = _visit(service.id)
    visit["visit_date"] = clinic_today(db_session).isoformat()
    visit["services"][0]["quantity"] = 2
    response = client.post(
        "/api/v1/registrar/cart",
        headers=_auth_headers(admin_user),
        json=_cart_payload(patient_id=test_patient.id, visits=[visit]),
    )
    assert response.status_code == 200
    payload = response.json()
    visit_id = payload["visit_ids"][0]
    [assignment] = payload["queue_numbers"][str(visit_id)]
    assert assignment["queue_tag"] == tag
    assert assignment["number"] > 0
    assert Decimal(assignment["service_price"]) == Decimal(unit_price) * 2


def test_ticket_price_stays_unknown_when_a_visit_cannot_be_priced_by_one_queue():
    line = VisitService(name="SYNTHETIC service", price=Decimal("25000"), qty=2)
    scoped = {"queue_id": 12, "queue_tag": "cardiology_common", "number": 1}
    second = {"queue_id": 13, "queue_tag": "ecg", "number": 1}
    price = cart_module._single_queue_ticket_price
    assert price([scoped, second], [(line, "cardiology_common")], Decimal("50000")) is None
    assert price([scoped], [(line, "ecg")], Decimal("50000")) is None
    assert price([scoped], [(line, None)], Decimal("50000")) is None
    assert price([scoped], [(line, "cardiology_common")], Decimal("60000")) is None


def test_initial_mixed_ecg_procedures_lab_tickets_use_separate_prices(
    client: TestClient, db_session: Session, admin_user, test_patient
):
    # A synthetic copy of the shape (three departments), with deliberately
    # different prices and one genuinely free line.
    from datetime import date

    test_patient.birth_date = date(1988, 12, 27)
    test_patient.address = "SYNTHETIC lab address"
    services = []
    tags = {"ecg": Decimal("41500"), "procedures": Decimal("27500"), "lab": Decimal("0")}
    for tag, amount in tags.items():
        db_session.add(
            QueueResource(code=tag, queue_tag=tag, display_name=f"SYNTHETIC {tag}")
        )
        service = Service(
            code=f"SYNTH-{tag}", service_code=f"SYNTH-{tag}",
            name=f"SYNTHETIC {tag}", queue_tag=tag, price=amount,
            requires_doctor=False, is_consultation=False, active=True,
        )
        db_session.add(service)
        services.append(service)
    db_session.commit()
    day = clinic_today(db_session)
    visit = {
        "doctor_id": None,
        "visit_date": day.isoformat(),
        "department": "lab",
        "services": [{"service_id": service.id, "quantity": 2} for service in services],
    }
    headers = _auth_headers(admin_user)
    response = client.post(
        "/api/v1/registrar/cart",
        headers=headers,
        json=_cart_payload(patient_id=test_patient.id, visits=[visit]),
    )
    assert response.status_code == 200
    payload = response.json()
    [visit_id] = payload["visit_ids"]
    assignments = payload["queue_numbers"][str(visit_id)]
    assert {item["queue_tag"]: Decimal(item["service_price"]) for item in assignments} == {
        tag: price * 2 for tag, price in tags.items()
    }
    assert sum(Decimal(item["service_price"]) for item in assignments) == Decimal(payload["total_amount"])

    rows = client.get("/api/v1/registrar/queues/today", headers=headers, params={"date_str": day})
    assert rows.status_code == 200
    lab_assignment = next(item for item in assignments if item["queue_tag"] == "lab")
    lab_row = next(
        row for bucket in rows.json()["queues"] for row in bucket["entries"]
        if row.get("daily_queue_id") == lab_assignment["queue_id"]
        and row.get("visit_id") == visit_id
    )
    assert lab_row.get("patient_birth_year") == 1988
    assert lab_row.get("address") == "SYNTHETIC lab address"
