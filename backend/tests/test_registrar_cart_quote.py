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
