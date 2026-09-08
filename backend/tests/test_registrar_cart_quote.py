"""
Fix D: read-only квота цен корзины /registrar/cart/quote.

Оригинальные дефекты:
  - frontend считал сумму сам и считал repeat-консультации бесплатными,
    тогда как backend применяет настраиваемый repeat_visit_discount процент —
    подтверждение расходилось с invoice;
  - подтверждение сабмита считало сумму из несуществующего item.price → 0
    для платных услуг;
  - отсутствие цены у услуги отображалось как 0 сум.

Quote endpoint переиспользует те же SSOT-хелперы, что и сохранение
(_load_registration_discount_settings + _apply_service_discount), поэтому
квота == invoice при неизменных настройках.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.clinic import ClinicSettings
from app.models.service import Service
from tests.conftest import mint_access_token

pytestmark = [pytest.mark.integration]


def _auth_headers(admin_user) -> dict[str, str]:
    return {"Authorization": f"Bearer {mint_access_token(admin_user)}"}


def _service(db: Session, *, code: str, price, is_consultation: bool = False) -> Service:
    service = Service(
        code=code,
        name=f"Fix D {code}",
        price=price,
        duration_minutes=30,
        active=True,
        requires_doctor=False,
        is_consultation=is_consultation,
    )
    db.add(service)
    db.commit()
    db.refresh(service)
    return service


def _set_settings(db: Session, **values) -> None:
    for key, value in values.items():
        row = db.query(ClinicSettings).filter(ClinicSettings.key == key).first()
        if row is None:
            db.add(ClinicSettings(key=key, value=str(value)))
        else:
            row.value = str(value)
    db.commit()


def _quote(client: TestClient, admin_user, items: list[dict], *, discount_mode="none", all_free=False):
    return client.post(
        "/api/v1/registrar/cart/quote",
        headers=_auth_headers(admin_user),
        json={"items": items, "discount_mode": discount_mode, "all_free": all_free},
    )


def test_quote_plain_service_with_quantity(
    client: TestClient, db_session: Session, admin_user
):
    """100000 × 1 и 100000 × 3 — квота умножает количество."""
    service = _service(db_session, code="FIXD-1", price=100000.00)

    one = _quote(client, admin_user, [{"service_id": service.id, "quantity": 1}])
    assert one.status_code == 200, one.text
    body = one.json()
    assert float(body["total_amount"]) == 100000
    assert float(body["items"][0]["final_price"]) == 100000
    assert body["items"][0]["discount_percent"] == 0

    three = _quote(client, admin_user, [{"service_id": service.id, "quantity": 3}])
    assert float(three.json()["total_amount"]) == 300000


def test_quote_repeat_discount_percent_not_automatic_free(
    client: TestClient, db_session: Session, admin_user
):
    """Repeat ≠ автоматически бесплатно: repeat_visit_discount=50 → 50% цены."""
    service = _service(db_session, code="FIXD-2", price=100000.00, is_consultation=True)
    _set_settings(db_session, repeat_visit_discount=50)

    response = _quote(
        client, admin_user,
        [{"service_id": service.id, "quantity": 1}],
        discount_mode="repeat",
    )
    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["discount_percent"] == 50
    assert float(body["items"][0]["final_price"]) == 50000
    assert float(body["total_amount"]) == 50000

    # repeat_visit_discount=0 → полная цена (раньше frontend показывал 0)
    _set_settings(db_session, repeat_visit_discount=0)
    zero = _quote(
        client, admin_user,
        [{"service_id": service.id, "quantity": 1}],
        discount_mode="repeat",
    )
    assert float(zero.json()["items"][0]["final_price"]) == 100000

    # 100% → бесплатно
    _set_settings(db_session, repeat_visit_discount=100)
    full = _quote(
        client, admin_user,
        [{"service_id": service.id, "quantity": 2}],
        discount_mode="repeat",
    )
    assert float(full.json()["total_amount"]) == 0
    assert full.json()["items"][0]["discount_percent"] == 100


def test_quote_all_free_pending_approval(
    client: TestClient, db_session: Session, admin_user
):
    """All Free без автоодобрения → сумма 0 + approval_status=pending."""
    service = _service(db_session, code="FIXD-3", price=100000.00)

    response = _quote(
        client, admin_user,
        [{"service_id": service.id, "quantity": 1}],
        all_free=True,
    )
    assert response.status_code == 200
    body = response.json()
    assert float(body["total_amount"]) == 0
    assert body["approval_status"] == "pending"

    # С автоодобрением → approved
    _set_settings(db_session, all_free_auto_approve=True)
    approved = _quote(
        client, admin_user,
        [{"service_id": service.id, "quantity": 1}],
        all_free=True,
    )
    assert approved.json()["approval_status"] == "approved"


def test_quote_missing_price_is_not_zero(
    client: TestClient, db_session: Session, admin_user
):
    """Услуга без цены — 409 с указанием услуги, а НЕ 0 сум."""
    service = _service(db_session, code="FIXD-4", price=None)

    response = _quote(client, admin_user, [{"service_id": service.id, "quantity": 1}])
    assert response.status_code == 409
    assert "не указана цена" in response.json()["detail"]
    assert service.name in response.json()["detail"]


def test_quote_unknown_service_is_404(
    client: TestClient, db_session: Session, admin_user
):
    response = _quote(client, admin_user, [{"service_id": 999999999, "quantity": 1}])
    assert response.status_code == 404


# ===================== Codex R1 #3095 =====================


def test_quote_honors_custom_price_in_cart_mode(
    client: TestClient, db_session: Session, admin_user
):
    """Codex R1 P2: custom_price зеркалится в квоту, иначе квота (каталог
    100000) расходится с инвойсом /registrar/cart (врачебная цена 80000)."""
    service = _service(db_session, code="FIXD-CP", price=100000.00)

    response = client.post(
        "/api/v1/registrar/cart/quote",
        headers=_auth_headers(admin_user),
        json={
            "items": [
                {"service_id": service.id, "quantity": 2, "custom_price": 80000}
            ],
            "discount_mode": "none",
            "all_free": False,
            "pricing_mode": "cart",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert float(body["items"][0]["unit_price"]) == 80000
    assert float(body["items"][0]["final_price"]) == 160000
    assert float(body["total_amount"]) == 160000


def test_quote_edit_delta_mode_ignores_repeat_discount(
    client: TestClient, db_session: Session, admin_user
):
    """Codex R1 P1: edit-delta НЕ применяет repeat-скидку (RegistrarEditDelta
    Service считает каталоговую цену) — квота edit_delta обязана повторять
    это, иначе подтверждение расходится с invoice edit-дельты."""
    service = _service(
        db_session, code="FIXD-ED", price=100000.00, is_consultation=True
    )
    _set_settings(db_session, repeat_visit_discount=50)

    # cart-режим: repeat-скидка применяется (50%)
    cart_mode = _quote(
        client, admin_user,
        [{"service_id": service.id, "quantity": 1}],
        discount_mode="repeat",
    )
    assert float(cart_mode.json()["items"][0]["final_price"]) == 50000

    # edit_delta-режим: каталоговая цена, скидка НЕ применяется
    edit_delta = client.post(
        "/api/v1/registrar/cart/quote",
        headers=_auth_headers(admin_user),
        json={
            "items": [{"service_id": service.id, "quantity": 1}],
            "discount_mode": "repeat",
            "all_free": False,
            "pricing_mode": "edit_delta",
        },
    )
    assert edit_delta.status_code == 200
    body = edit_delta.json()
    assert float(body["items"][0]["final_price"]) == 100000
    assert body["items"][0]["discount_percent"] == 0


def test_quote_edit_delta_mode_applies_all_free_zero(
    client: TestClient, db_session: Session, admin_user
):
    """edit_delta-режим: all_free → 0 (единственное правило edit-delta)."""
    service = _service(db_session, code="FIXD-ED2", price=100000.00)

    edit_delta = client.post(
        "/api/v1/registrar/cart/quote",
        headers=_auth_headers(admin_user),
        json={
            "items": [{"service_id": service.id, "quantity": 3}],
            "discount_mode": "none",
            "all_free": True,
            "pricing_mode": "edit_delta",
        },
    )
    assert edit_delta.status_code == 200
    assert float(edit_delta.json()["total_amount"]) == 0
    assert edit_delta.json()["approval_status"] in ("pending", "approved")


# ===================== Codex R2 #3095 =====================


def test_quote_edit_delta_all_free_reports_approved_like_the_command(
    client: TestClient, db_session: Session, admin_user
):
    """Codex R2 #3095 (P2): RegistrarEditDeltaService._create_visit ВСЕГДА
    пишет approval_status="approved" и не читает all_free_auto_approve —
    квота edit_delta не должна предупреждать о согласовании, которого
    команда не выполняет."""
    service = _service(db_session, code="FIXD-ED3", price=100000.00)
    # Явно выключаем авто-approve: раньше это давало "pending" в квоте,
    # тогда как команда сохранения пишет "approved".
    _set_settings(db_session, all_free_auto_approve=False)

    edit_delta = client.post(
        "/api/v1/registrar/cart/quote",
        headers=_auth_headers(admin_user),
        json={
            "items": [{"service_id": service.id, "quantity": 1}],
            "discount_mode": "none",
            "all_free": True,
            "pricing_mode": "edit_delta",
        },
    )
    assert edit_delta.status_code == 200
    body = edit_delta.json()
    assert float(body["total_amount"]) == 0
    assert body["approval_status"] == "approved", (
        "edit-delta command always writes approved — the quote must not claim pending"
    )

    # cart-режим с теми же настройками честно требует согласования
    cart_mode = client.post(
        "/api/v1/registrar/cart/quote",
        headers=_auth_headers(admin_user),
        json={
            "items": [{"service_id": service.id, "quantity": 1}],
            "discount_mode": "none",
            "all_free": True,
            "pricing_mode": "cart",
        },
    )
    assert cart_mode.status_code == 200
    assert cart_mode.json()["approval_status"] == "pending"


def test_quote_cart_mode_allows_custom_price_when_catalog_price_missing(
    client: TestClient, db_session: Session, admin_user
):
    """Codex R2 #3095 (P2): price=None + валидный custom_price — контракт
    cart-пути сохранения (create_cart_appointments берёт custom_price
    первым). Квота обязана считать по custom_price, а не отвечать 409."""
    service = _service(db_session, code="FIXD-CP", price=None)

    quoted = client.post(
        "/api/v1/registrar/cart/quote",
        headers=_auth_headers(admin_user),
        json={
            "items": [{"service_id": service.id, "quantity": 2, "custom_price": 15000}],
            "discount_mode": "none",
            "all_free": False,
            "pricing_mode": "cart",
        },
    )
    assert quoted.status_code == 200, quoted.text
    body = quoted.json()
    assert float(body["items"][0]["unit_price"]) == 15000
    assert float(body["total_amount"]) == 30000

    # Нет ни одной эффективной цены — 409 остаётся (отсутствие цены НЕ 0)
    both_missing = client.post(
        "/api/v1/registrar/cart/quote",
        headers=_auth_headers(admin_user),
        json={
            "items": [{"service_id": service.id, "quantity": 1}],
            "discount_mode": "none",
            "all_free": False,
            "pricing_mode": "cart",
        },
    )
    assert both_missing.status_code == 409

    # edit_delta: custom_price вне контракта маршрута — отсутствие каталог-
    # цены остаётся 409 (сейв-путь edit-delta custom_price не принимает)
    edit_delta = client.post(
        "/api/v1/registrar/cart/quote",
        headers=_auth_headers(admin_user),
        json={
            "items": [{"service_id": service.id, "quantity": 1, "custom_price": 15000}],
            "discount_mode": "none",
            "all_free": False,
            "pricing_mode": "edit_delta",
        },
    )
    assert edit_delta.status_code == 409


def test_quote_full_update_mode_mirrors_the_full_update_route(
    client: TestClient, db_session: Session, admin_user
):
    """Codex R2 #3095 (P1): full_update-квота зеркалирует
    _full_update_create_single_independent_entry — консультация при
    repeat/benefit → 0, не-консультация → полная каталог-цена,
    all_free → 0."""
    consultation = _service(
        db_session, code="FIXD-FU-C", price=100000.00, is_consultation=True
    )
    lab = _service(db_session, code="FIXD-FU-L", price=60000.00)
    _set_settings(db_session, repeat_visit_discount=50)

    repeat_quote = client.post(
        "/api/v1/registrar/cart/quote",
        headers=_auth_headers(admin_user),
        json={
            "items": [
                {"service_id": consultation.id, "quantity": 1},
                {"service_id": lab.id, "quantity": 1},
            ],
            "discount_mode": "repeat",
            "all_free": False,
            "pricing_mode": "full_update",
        },
    )
    assert repeat_quote.status_code == 200, repeat_quote.text
    body = repeat_quote.json()
    by_id = {item["service_id"]: item for item in body["items"]}
    # Консультация бесплатна (маршрут пишет price=0), 50% скидка НЕ применяется
    assert float(by_id[consultation.id]["final_price"]) == 0
    # Лабораторная услуга — полная каталог-цена (в отличие от cart-режима,
    # где repeat дал бы 50%)
    assert float(by_id[lab.id]["final_price"]) == 60000
    assert float(body["total_amount"]) == 60000
    # У full-update маршрута нет согласования
    assert body["approval_status"] == "approved"

    all_free_quote = client.post(
        "/api/v1/registrar/cart/quote",
        headers=_auth_headers(admin_user),
        json={
            "items": [{"service_id": lab.id, "quantity": 2}],
            "discount_mode": "none",
            "all_free": True,
            "pricing_mode": "full_update",
        },
    )
    assert all_free_quote.status_code == 200
    assert float(all_free_quote.json()["total_amount"]) == 0
    # Codex R3 #3095 (P2): _full_update_handle_all_free_visit writes
    # approval_status="pending" for BOTH the unpaid existing visit and a new
    # visit — the quote must warn about approval, not report approved.
    assert all_free_quote.json()["approval_status"] == "pending"


# ===================== Codex R3 #3095 =====================


def test_quote_full_update_int_conversion_mirrors_the_command(
    client: TestClient, db_session: Session, admin_user
):
    """Codex R3 #3095 (P2): _full_update_create_single_independent_entry
    stores int(item_price) (unit × quantity) in the payload and total_amount.
    A valid two-decimal catalog price 10.99 × 3 must therefore quote 32
    (the exact saved amount), not 32.97."""
    service = _service(db_session, code="FIXD-FU-DEC", price=10.99)

    response = client.post(
        "/api/v1/registrar/cart/quote",
        headers=_auth_headers(admin_user),
        json={
            "items": [{"service_id": service.id, "quantity": 3}],
            "discount_mode": "none",
            "all_free": False,
            "pricing_mode": "full_update",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert float(body["items"][0]["final_price"]) == 32, (
        "the quote must mirror the command's int() conversion exactly"
    )
    assert float(body["total_amount"]) == 32

    # The cart-mode quote keeps decimal precision (the cart path saves Decimals)
    cart_quote = client.post(
        "/api/v1/registrar/cart/quote",
        headers=_auth_headers(admin_user),
        json={
            "items": [{"service_id": service.id, "quantity": 3}],
            "discount_mode": "none",
            "all_free": False,
            "pricing_mode": "cart",
        },
    )
    assert float(cart_quote.json()["items"][0]["final_price"]) == 32.97


def test_quote_token_rejects_stale_pricing_at_save_409(
    client: TestClient, db_session: Session, admin_user, test_patient, test_doctor
):
    """Codex R3 #3095 (P1): the confirmed quote is bound to the save command.
    If an administrator changes the price after confirmation, /registrar/cart
    must reject the stale token with 409 instead of silently invoicing a
    different amount."""
    service = _service(db_session, code="FIXD-TOK-1", price=50000.00)

    quoted = _quote(client, admin_user, [{"service_id": service.id, "quantity": 1}])
    assert quoted.status_code == 200
    stale_token = quoted.json()["quote_token"]
    assert stale_token

    # Administrator changes the price AFTER the registrar confirmed
    service.price = 70000.00
    db_session.commit()

    payload = {
        "patient_id": test_patient.id,
        "discount_mode": "none",
        "payment_method": "cash",
        "quote_token": stale_token,
        "visits": [
            {
                "doctor_id": test_doctor.id,
                "visit_date": date.today().isoformat(),
                "department": "general",
                "services": [{"service_id": service.id, "quantity": 1}],
            }
        ],
    }
    stale_save = client.post(
        "/api/v1/registrar/cart", headers=_auth_headers(admin_user), json=payload
    )
    assert stale_save.status_code == 409, stale_save.text
    assert "изменились" in stale_save.json()["detail"]
    # The current price is surfaced so the registrar can re-confirm knowingly
    assert "70000" in stale_save.json()["detail"]


def test_quote_token_fresh_pricing_passes_revalidation(
    client: TestClient, db_session: Session, admin_user, test_patient, test_doctor
):
    """The same payload re-quoted AFTER the price change produces a fresh
    token that passes revalidation — the save proceeds (no false 409)."""
    service = _service(db_session, code="FIXD-TOK-2", price=50000.00)

    quoted = _quote(client, admin_user, [{"service_id": service.id, "quantity": 1}])
    stale_token = quoted.json()["quote_token"]

    service.price = 70000.00
    db_session.commit()

    payload = {
        "patient_id": test_patient.id,
        "discount_mode": "none",
        "payment_method": "cash",
        "quote_token": stale_token,
        "visits": [
            {
                "doctor_id": test_doctor.id,
                "visit_date": date.today().isoformat(),
                "department": "general",
                "services": [{"service_id": service.id, "quantity": 1}],
            }
        ],
    }
    # Re-confirm: fresh quote for the SAME payload on the new price
    fresh = _quote(client, admin_user, [{"service_id": service.id, "quantity": 1}])
    payload["quote_token"] = fresh.json()["quote_token"]

    saved = client.post(
        "/api/v1/registrar/cart", headers=_auth_headers(admin_user), json=payload
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert float(body["total_amount"]) == 70000


def test_cart_without_quote_token_still_saves_backward_compatible(
    client: TestClient, db_session: Session, admin_user, test_patient, test_doctor
):
    """No token → no revalidation (external API callers, backward compat).
    The wizard always sends the token; absence is allowed but not exploited."""
    service = _service(db_session, code="FIXD-TOK-3", price=45000.00)

    payload = {
        "patient_id": test_patient.id,
        "discount_mode": "none",
        "payment_method": "cash",
        "visits": [
            {
                "doctor_id": test_doctor.id,
                "visit_date": date.today().isoformat(),
                "department": "general",
                "services": [{"service_id": service.id, "quantity": 1}],
            }
        ],
    }
    saved = client.post(
        "/api/v1/registrar/cart", headers=_auth_headers(admin_user), json=payload
    )
    assert saved.status_code == 200, saved.text


def test_edit_delta_quote_token_rejects_stale_pricing_409(
    client: TestClient, db_session: Session, admin_user, test_patient
):
    """Codex R4 #3095 (P1): the edit-delta command revalidates the confirmed
    edit quote BEFORE any mutation — an admin price change after confirmation
    yields 409, never a silently different invoice."""
    service = _service(db_session, code="FIXD-EDT-1", price=50000.00)

    quoted = client.post(
        "/api/v1/registrar/cart/quote",
        headers=_auth_headers(admin_user),
        json={
            "items": [{"service_id": service.id, "quantity": 1}],
            "discount_mode": "none",
            "all_free": False,
            "pricing_mode": "edit_delta",
        },
    )
    assert quoted.status_code == 200
    stale_token = quoted.json()["quote_token"]

    service.price = 90000.00
    db_session.commit()

    payload = {
        "patient_id": test_patient.id,
        "target_date": date.today().isoformat(),
        "payment_method": "cash",
        "discount_mode": "none",
        "all_free": False,
        "services": [{"service_id": service.id, "quantity": 1, "specialist_id": None}],
        "quote_token": stale_token,
    }
    stale = client.post(
        "/api/v1/registrar/cart/edit-delta", headers=_auth_headers(admin_user), json=payload
    )
    assert stale.status_code == 409, stale.text
    assert "изменились" in stale.json()["detail"]
    assert "90000" in stale.json()["detail"]


def test_edit_delta_fresh_quote_token_passes_revalidation(
    client: TestClient, db_session: Session, admin_user, test_patient
):
    """Fresh token for the same payload (re-quoted after the price change)
    passes revalidation — the command proceeds past the pricing gate."""
    from tests.conftest import mint_access_token

    service = _service(db_session, code="FIXD-EDT-2", price=50000.00)

    token_headers = {"Authorization": f"Bearer {mint_access_token(admin_user)}"}
    quoted = client.post(
        "/api/v1/registrar/cart/quote",
        headers=token_headers,
        json={
            "items": [{"service_id": service.id, "quantity": 1}],
            "discount_mode": "none",
            "all_free": False,
            "pricing_mode": "edit_delta",
        },
    )
    stale_token = quoted.json()["quote_token"]

    service.price = 90000.00
    db_session.commit()

    fresh = client.post(
        "/api/v1/registrar/cart/quote",
        headers=token_headers,
        json={
            "items": [{"service_id": service.id, "quantity": 1}],
            "discount_mode": "none",
            "all_free": False,
            "pricing_mode": "edit_delta",
        },
    )
    payload = {
        "patient_id": test_patient.id,
        "target_date": date.today().isoformat(),
        "payment_method": "cash",
        "discount_mode": "none",
        "all_free": False,
        "services": [{"service_id": service.id, "quantity": 1, "specialist_id": None}],
        "quote_token": fresh.json()["quote_token"],
    }
    ok = client.post(
        "/api/v1/registrar/cart/edit-delta", headers=token_headers, json=payload
    )
    assert ok.status_code != 409, ok.text


# ===================== Codex R6 #3095 =====================


def _active_entry_with_service(
    db: Session, *, patient_id: int, service: Service, existing_qty: int, specialist_id=None
):
    """Active same-day queue entry for the patient that already contains the
    service with the given quantity — the routing target of the edit-delta
    command (RegistrarEditDeltaService._find_active_entry predicate)."""
    import json as _json

    from app.models.online_queue import DailyQueue, OnlineQueueEntry

    daily_queue = DailyQueue(
        day=date.today(),
        specialist_id=specialist_id,
        queue_tag=service.queue_tag or service.department_key,
        active=True,
    )
    db.add(daily_queue)
    db.flush()
    entry = OnlineQueueEntry(
        queue_id=daily_queue.id,
        number=1,
        patient_id=patient_id,
        source="desk",
        status="waiting",
        services=[
            {
                "service_id": service.id,
                "code": service.service_code or service.code,
                "name": service.name,
                "qty": existing_qty,
                "price": float(service.price or 0),
            }
        ],
    )
    entry.services = _json.loads(_json.dumps(entry.services))
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def _quote_with_context(client: TestClient, admin_user, items, *, extra: dict):
    payload = {
        "items": items,
        "discount_mode": "none",
        "all_free": False,
        "pricing_mode": "edit_delta",
    }
    payload.update(extra)
    return client.post(
        "/api/v1/registrar/cart/quote", headers=_auth_headers(admin_user), json=payload
    )


def test_quote_edit_delta_with_context_bills_the_delta_the_command_bills(
    client: TestClient, db_session: Session, admin_user, test_patient, test_doctor
):
    """Codex R6 #3095 (P2): when the added service routes to an active
    same-day entry that ALREADY contains it, the command bills only
    max(requested − existing, 0) (_append_to_existing_entry) — the quote
    with the edit context must validate the SAME delta, not the full
    requested quantity (the confirmed amount must never exceed the actual
    invoice delta)."""
    service = _service(db_session, code="FIXD-R6-1", price=100000.00)
    service.queue_tag = "fixd_r6_tag"
    db_session.commit()
    entry = _active_entry_with_service(
        db_session,
        patient_id=test_patient.id,
        service=service,
        existing_qty=2,
        specialist_id=test_doctor.id,
    )

    quoted = _quote_with_context(
        client,
        admin_user,
        [{"service_id": service.id, "quantity": 5}],
        extra={
            "patient_id": test_patient.id,
            "target_date": date.today().isoformat(),
            "preferred_entry_ids": [entry.id],
        },
    )
    assert quoted.status_code == 200, quoted.text
    body = quoted.json()
    # Command routing: entry holds 2 → billed 5 − 2 = 3 × 100000
    assert body["items"][0]["quantity"] == 3
    assert float(body["items"][0]["final_price"]) == 300000
    assert float(body["total_amount"]) == 300000


def test_quote_edit_delta_without_context_bills_full_quantity(
    client: TestClient, db_session: Session, admin_user, test_patient, test_doctor
):
    """Legacy contract preserved: a quote WITHOUT the edit context (older
    clients) still prices the full requested quantity."""
    service = _service(db_session, code="FIXD-R6-2", price=100000.00)
    service.queue_tag = "fixd_r6_tag2"
    db_session.commit()
    _active_entry_with_service(
        db_session,
        patient_id=test_patient.id,
        service=service,
        existing_qty=2,
        specialist_id=test_doctor.id,
    )

    quoted = _quote_with_context(
        client, admin_user, [{"service_id": service.id, "quantity": 5}], extra={}
    )
    assert quoted.status_code == 200
    body = quoted.json()
    assert body["items"][0]["quantity"] == 5
    assert float(body["total_amount"]) == 500000


def test_edit_delta_command_accepts_the_context_bound_delta_token(
    client: TestClient, db_session: Session, admin_user, test_patient, test_doctor
):
    """Round-trip: quote WITH context → command WITH the same context passes
    the pricing gate (the revalidation recomputes the same delta and thus
    the same token)."""
    service = _service(db_session, code="FIXD-R6-3", price=100000.00)
    service.queue_tag = "fixd_r6_tag3"
    db_session.commit()
    entry = _active_entry_with_service(
        db_session,
        patient_id=test_patient.id,
        service=service,
        existing_qty=2,
        specialist_id=test_doctor.id,
    )

    context = {
        "patient_id": test_patient.id,
        "target_date": date.today().isoformat(),
        "preferred_entry_ids": [entry.id],
    }
    quoted = _quote_with_context(
        client, admin_user, [{"service_id": service.id, "quantity": 5}], extra=context
    )
    token = quoted.json()["quote_token"]

    payload = {
        **context,
        "payment_method": "cash",
        "discount_mode": "none",
        "all_free": False,
        "services": [{"service_id": service.id, "quantity": 5, "specialist_id": None}],
        "quote_token": token,
    }
    ok = client.post(
        "/api/v1/registrar/cart/edit-delta", headers=_auth_headers(admin_user), json=payload
    )
    assert ok.status_code != 409, ok.text


def test_edit_delta_command_rejects_full_quantity_token_when_entry_holds_service(
    client: TestClient, db_session: Session, admin_user, test_patient, test_doctor
):
    """The exact Codex R6 scenario: a token confirming the FULL requested
    quantity (5 × 100000) can no longer validate a save whose real invoice
    delta is 3 × 100000 — the context-aware revalidation recomputes the
    delta, finds the token stale and returns 409 instead of confirming an
    amount greater than what will be billed."""
    service = _service(db_session, code="FIXD-R6-4", price=100000.00)
    service.queue_tag = "fixd_r6_tag4"
    db_session.commit()
    entry = _active_entry_with_service(
        db_session,
        patient_id=test_patient.id,
        service=service,
        existing_qty=2,
        specialist_id=test_doctor.id,
    )

    # Context-less quote bills the full 5 × 100000 (legacy behavior)
    quoted = _quote_with_context(
        client, admin_user, [{"service_id": service.id, "quantity": 5}], extra={}
    )
    full_token = quoted.json()["quote_token"]
    assert float(quoted.json()["total_amount"]) == 500000

    payload = {
        "patient_id": test_patient.id,
        "target_date": date.today().isoformat(),
        "preferred_entry_ids": [entry.id],
        "payment_method": "cash",
        "discount_mode": "none",
        "all_free": False,
        "services": [{"service_id": service.id, "quantity": 5, "specialist_id": None}],
        "quote_token": full_token,
    }
    rejected = client.post(
        "/api/v1/registrar/cart/edit-delta", headers=_auth_headers(admin_user), json=payload
    )
    assert rejected.status_code == 409, rejected.text


def test_create_cart_skips_settings_reload_when_token_validated(
    client: TestClient, db_session: Session, admin_user, test_patient, test_doctor, monkeypatch
):
    """Codex R6 #3095 (P2): "price the save directly from the validated
    values" — after the token revalidation the save path must NOT re-read
    the discount settings (an unlocked reload would see settings rows
    inserted after revalidation, which FOR UPDATE cannot lock). With a
    validated token the ONLY settings read is the locked snapshot inside
    the revalidation."""
    from app.api.v1.endpoints.registrar_wizard import _cart as cart_module

    service = _service(db_session, code="FIXD-R6-5", price=50000.00)

    quoted = _quote(client, admin_user, [{"service_id": service.id, "quantity": 1}])
    token = quoted.json()["quote_token"]

    calls: list[bool] = []
    real_loader = cart_module._load_registration_discount_settings

    def spy(db, lock_rows: bool = False):
        calls.append(lock_rows)
        return real_loader(db, lock_rows=lock_rows)

    monkeypatch.setattr(cart_module, "_load_registration_discount_settings", spy)

    payload = {
        "patient_id": test_patient.id,
        "discount_mode": "none",
        "payment_method": "cash",
        "quote_token": token,
        "visits": [
            {
                "doctor_id": test_doctor.id,
                "visit_date": date.today().isoformat(),
                "department": "general",
                "services": [{"service_id": service.id, "quantity": 1}],
            }
        ],
    }
    saved = client.post(
        "/api/v1/registrar/cart", headers=_auth_headers(admin_user), json=payload
    )
    assert saved.status_code == 200, saved.text
    assert float(saved.json()["total_amount"]) == 50000
    assert calls == [True], (
        "the locked snapshot inside revalidation is the only settings read; "
        "the unlocked save-time reload is gone"
    )


# ===================== Codex R8 #3095 (P2): ТОЧНОСТЬ custom_price =====================


@pytest.mark.integration
@pytest.mark.queue
def test_custom_price_rejected_beyond_two_decimal_places(
    client, db_session, admin_user, test_patient, test_doctor
):
    """custom_price точнее 2dp отвергается ДО вычислений (422): quote
    округлял строку до 2dp при токенe, а путь сохранения аккумулировал
    сырое значение и полагался на Numeric(12,2) — 1.005 подтверждался как
    1.00, а сохранялся в счёт как 1.01. Единая точность DTO закрывает
    расхождение, не меняя контракт для корректных 2dp-цен."""
    service = _service(db_session, code="R8-PREC-01", price=Decimal("100"))

    # custom_price с 3 знаками — отвергается схемой quote
    quoted = client.post(
        "/api/v1/registrar/cart/quote",
        headers=_auth_headers(admin_user),
        json={
            "items": [{"service_id": service.id, "quantity": 2, "custom_price": "1.005"}],
            "discount_mode": "none",
            "all_free": False,
            "pricing_mode": "cart",
        },
    )
    assert quoted.status_code == 422, quoted.text

    # 2dp-цена по-прежнему валидна и согласована
    ok = client.post(
        "/api/v1/registrar/cart/quote",
        headers=_auth_headers(admin_user),
        json={
            "items": [{"service_id": service.id, "quantity": 2, "custom_price": "1.01"}],
            "discount_mode": "none",
            "all_free": False,
            "pricing_mode": "cart",
        },
    )
    assert ok.status_code == 200, ok.text
    assert Decimal(str(ok.json()["total_amount"])) == Decimal("2.02")


# ===================== Codex R9 #3095 =====================


def test_save_path_locks_service_rows_in_sorted_order(
    client: TestClient, db_session: Session, admin_user
):
    """Codex R9 #3095 (P2): the save path acquires service row locks in ONE
    deterministic (sorted id) order. With only the default pricing settings,
    the settings query locks no rows, so two concurrent token-bound saves
    holding the same services in opposite item orders used to reach the
    per-item loop together and lock in opposite orders — a lock-order
    deadlock; PostgreSQL aborted one save. The lock query must therefore be a
    single sorted bulk acquisition, not per-item lookups in request order."""
    from sqlalchemy import event

    from app.api.v1.endpoints.registrar_wizard._cart import _quote_core
    from app.api.v1.endpoints.registrar_wizard._helpers import (
        CartQuoteItemRequest,
        CartQuoteRequest,
    )

    second = _service(db_session, code="R9-LOCK-B", price=50000.00)
    first = _service(db_session, code="R9-LOCK-A", price=70000.00)

    # Items deliberately in DESCENDING id order — the lock acquisition must
    # still happen in ascending id order. (Built BEFORE the listener: lazy
    # refreshes of these very instances are not part of the lock contract.)
    quote_req = CartQuoteRequest(
        items=[
            CartQuoteItemRequest(service_id=second.id, quantity=1),
            CartQuoteItemRequest(service_id=first.id, quantity=2),
        ],
        discount_mode="none",
        all_free=False,
        pricing_mode="cart",
    )

    statements: list[str] = []

    def _capture(conn, cursor, statement, parameters, context, executemany):
        normalized = " ".join(statement.split())
        if "FROM services" in normalized:
            statements.append(normalized)

    engine = db_session.get_bind()
    event.listen(engine, "before_cursor_execute", _capture)
    try:
        response = _quote_core(db_session, quote_req, lock_pricing_rows=True)
    finally:
        event.remove(engine, "before_cursor_execute", _capture)

    lock_queries = [
        s for s in statements if "ORDER BY services.id" in s and "IN" in s
    ]
    assert lock_queries, (
        "the save path must prefetch+lock all service rows in one sorted "
        f"query; captured: {statements}"
    )
    # Per-item locking reads in request order are gone: the locked save path
    # must not issue per-item equality reads on the services table at all.
    per_item = [
        s for s in statements if "services.id =" in s
    ]
    assert not per_item, (
        "per-item service reads must not remain in the locked save path: "
        f"{per_item}"
    )
    # Pricing behavior unchanged (50000×1 + 70000×2)
    assert float(response.total_amount) == 190000
