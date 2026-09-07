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
    assert all_free_quote.json()["approval_status"] == "approved"
