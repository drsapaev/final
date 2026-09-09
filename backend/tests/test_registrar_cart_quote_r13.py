"""Codex R13 #3095: дубликаты услуг в full-update и specialist при ревалидации.

Находки:
  - P2 (_online_entries.py): loose full-update payload с одной и той же услугой
    дважды (quantity 1 и 2) — квота/токен ценили обе строки (3 единицы), но
    мутация итерировала дублирующийся id и next(...) каждый раз выбирала ПЕРВУЮ
    строку → создавались две одноединицные записи. Канонизация (слияние по
    service_id с суммой количеств) ДО ревалидации токена и мутации.
  - P2 (_cart.py): квота full_update обязана ценить ту же каноническую цель —
    иначе токен, подтверждённый за расщеплённый payload, никогда не совпал бы
    со слитой командой сохранения.
  - P2 (_cart.py:edit-delta): ревалидация токена на сохранении теряла
    specialist_id — услуга без врача по умолчанию и без активной очереди дня:
    квота проходила с выбранным врачом, а ревалидация падала 400
    "specialist_id is required" ДО мутации, которая умеет использовать
    request.services[*].specialist_id.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.online_queue import OnlineQueueEntry
from app.models.service import Service
from tests.conftest import mint_access_token

pytestmark = [pytest.mark.integration]


def _auth_headers(admin_user) -> dict[str, str]:
    return {"Authorization": f"Bearer {mint_access_token(admin_user)}"}


def _service(db: Session, *, code: str, price: float) -> Service:
    service = Service(
        code=code,
        name=f"R13 {code}",
        price=price,
        duration_minutes=30,
        active=True,
        requires_doctor=False,
    )
    db.add(service)
    db.commit()
    db.refresh(service)
    return service


# ===================== P2: дубликаты в full-update =====================


def test_full_update_quote_merges_duplicate_service_rows(
    client: TestClient, db_session: Session, admin_user
):
    """Квота full_update ценит каноническую цель: [X×1, X×2] == [X×3] —
    одна строка с quantity 3 и итогом int(3 × цена)."""
    service = _service(db_session, code="R13-DUP-Q", price=10000.00)

    response = client.post(
        "/api/v1/registrar/cart/quote",
        headers=_auth_headers(admin_user),
        json={
            "items": [
                {"service_id": service.id, "quantity": 1},
                {"service_id": service.id, "quantity": 2},
            ],
            "discount_mode": "none",
            "all_free": False,
            "pricing_mode": "full_update",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["items"]) == 1, (
        "duplicate full-update rows must be priced as one canonical row"
    )
    assert body["items"][0]["quantity"] == 3
    assert float(body["items"][0]["final_price"]) == 30000
    assert float(body["total_amount"]) == 30000

    # Тот же токен, что и у эквивалентной слитой команды
    merged = client.post(
        "/api/v1/registrar/cart/quote",
        headers=_auth_headers(admin_user),
        json={
            "items": [{"service_id": service.id, "quantity": 3}],
            "discount_mode": "none",
            "all_free": False,
            "pricing_mode": "full_update",
        },
    )
    assert merged.json()["quote_token"] == body["quote_token"]


def test_full_update_duplicate_rows_save_confirmed_quantity(
    client: TestClient,
    db_session: Session,
    registrar_auth_headers,
    test_daily_queue,
    test_patient,
):
    """Сохранение с дублирующимися строками и токеном за расщеплённый
    payload: одна новая запись с quantity 3, а не две по единице."""
    old_service = _service(db_session, code="R13-DUP-OLD", price=20000.00)
    new_service = _service(db_session, code="R13-DUP-NEW", price=10000.00)
    entry = OnlineQueueEntry(
        queue_id=test_daily_queue.id,
        number=13,
        patient_id=test_patient.id,
        patient_name=test_patient.short_name(),
        phone=test_patient.phone,
        source="online",
        status="waiting",
        queue_time=datetime.now(ZoneInfo("Asia/Tashkent")).replace(microsecond=0),
        services=[
            {
                "service_id": old_service.id,
                "name": old_service.name,
                "quantity": 1,
                "price": 20000,
                "cancelled": False,
            }
        ],
        service_codes=[old_service.code],
        total_amount=20000,
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)

    # Легаси-клиент квотирует расщеплённый payload — прямой вызов ядра
    # ценообразования (тот же код, что и endpoint квоты)
    from app.api.v1.endpoints.registrar_wizard._cart import _quote_core
    from app.api.v1.endpoints.registrar_wizard._helpers import (
        CartQuoteItemRequest,
        CartQuoteRequest,
    )

    quote = _quote_core(
        db_session,
        CartQuoteRequest(
            items=[
                CartQuoteItemRequest(service_id=old_service.id, quantity=1),
                CartQuoteItemRequest(service_id=new_service.id, quantity=1),
                CartQuoteItemRequest(service_id=new_service.id, quantity=2),
            ],
            discount_mode="none",
            all_free=False,
            pricing_mode="full_update",
        ),
    )
    token = quote.quote_token
    assert token

    response = client.put(
        f"/api/v1/queue/online-entry/{entry.id}/full-update",
        headers=registrar_auth_headers,
        json={
            "patient_data": {
                "patient_name": test_patient.short_name(),
                "phone": test_patient.phone,
                "birth_year": 1990,
                "address": test_patient.address,
            },
            "visit_type": "paid",
            "discount_mode": "none",
            "services": [
                {"service_id": old_service.id, "quantity": 1},
                {"service_id": new_service.id, "quantity": 1},
                {"service_id": new_service.id, "quantity": 2},
            ],
            "all_free": False,
            "quote_token": token,
        },
    )
    assert response.status_code == 200, response.text

    created = (
        db_session.query(OnlineQueueEntry)
        .filter(
            OnlineQueueEntry.patient_id == test_patient.id,
            OnlineQueueEntry.id != entry.id,
        )
        .all()
    )
    assert len(created) == 1, (
        "duplicated service rows must produce ONE independent entry"
    )
    payload = created[0].services
    payload = (
        __import__("json").loads(payload)
        if isinstance(payload, str)
        else list(payload)
    )
    assert len(payload) == 1
    assert payload[0]["quantity"] == 3
    assert created[0].total_amount == 30000


def test_full_update_duplicate_rows_with_conflicting_params_rejected(
    client: TestClient,
    db_session: Session,
    registrar_auth_headers,
    test_daily_queue,
    test_patient,
):
    """Дубликаты одного service_id с РАЗНЫМИ не-quantity параметрами —
    неоднозначное целевое состояние, честный 400."""
    service = _service(db_session, code="R13-DUP-CONF", price=10000.00)
    entry = OnlineQueueEntry(
        queue_id=test_daily_queue.id,
        number=14,
        patient_id=test_patient.id,
        patient_name=test_patient.short_name(),
        phone=test_patient.phone,
        source="online",
        status="waiting",
        queue_time=datetime.now(ZoneInfo("Asia/Tashkent")).replace(microsecond=0),
        services=[],
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)

    response = client.put(
        f"/api/v1/queue/online-entry/{entry.id}/full-update",
        headers=registrar_auth_headers,
        json={
            "patient_data": {
                "patient_name": test_patient.short_name(),
                "phone": test_patient.phone,
            },
            "visit_type": "paid",
            "discount_mode": "none",
            "services": [
                {"service_id": service.id, "quantity": 1, "note": "first"},
                {"service_id": service.id, "quantity": 2, "note": "second"},
            ],
            "all_free": False,
        },
    )
    assert response.status_code == 400, response.text
    assert "несколько раз" in response.json()["detail"]


# ===================== P2: specialist при ревалидации edit-delta =====================


def test_edit_delta_save_revalidation_preserves_selected_specialist(
    client: TestClient,
    db_session: Session,
    registrar_auth_headers,
    admin_user,
    test_patient,
    test_doctor,
):
    """Услуга без врача по умолчанию, активной очереди дня нет. Квота с
    выбранным регистратором специалистом проходит; сохранение обязано
    ревалидировать токен с ТЕМ ЖЕ specialist_id — иначе 400
    "specialist_id is required" отбрасывает подтверждённую команду."""
    from app.models.online_queue import DailyQueue

    # Нет активной очереди для тега на сегодня — ровно сценарий находки
    assert (
        db_session.query(DailyQueue)
        .filter(DailyQueue.day == date.today(), DailyQueue.active.is_(True))
        .count()
        == 0
    )
    service = Service(
        code="R13-SPEC-1",
        service_code="R13-SPEC-1",
        name="R13 No Default Doctor",
        price=Decimal("25000"),
        active=True,
        requires_doctor=False,
        queue_tag="r13_spec_tag",
        department_key="r13_spec_tag",
        doctor_id=None,
    )
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)

    quoted = client.post(
        "/api/v1/registrar/cart/quote",
        headers=_auth_headers(admin_user),
        json={
            "items": [
                {
                    "service_id": service.id,
                    "quantity": 1,
                    "specialist_id": test_doctor.id,
                }
            ],
            "discount_mode": "none",
            "all_free": False,
            "pricing_mode": "edit_delta",
            "patient_id": test_patient.id,
            "target_date": date.today().isoformat(),
        },
    )
    assert quoted.status_code == 200, quoted.text
    token = quoted.json()["quote_token"]
    assert token

    response = client.post(
        "/api/v1/registrar/cart/edit-delta",
        headers=registrar_auth_headers,
        json={
            "patient_id": test_patient.id,
            "target_date": date.today().isoformat(),
            "payment_method": "cash",
            "discount_mode": "none",
            "all_free": False,
            "services": [
                {
                    "service_id": service.id,
                    "quantity": 1,
                    "specialist_id": test_doctor.id,
                }
            ],
            "existing_queue_entry_ids": [],
            "quote_token": token,
        },
    )
    assert response.status_code == 200, (
        "the save must revalidate with the SAME specialist the quote used: "
        f"{response.text}"
    )
    body = response.json()
    assert body["success"] is True
