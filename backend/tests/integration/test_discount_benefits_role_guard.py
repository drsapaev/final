from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.discount_benefits import Discount


def test_admin_can_list_discount_benefits(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    response = client.get("/api/v1/discount-benefits/discounts", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["success"] is True


def test_patient_cannot_create_discount_benefit_config(
    client: TestClient,
    db_session: Session,
    patient_token: str,
) -> None:
    before_count = db_session.query(Discount).count()

    response = client.post(
        "/api/v1/discount-benefits/discounts",
        headers={"Authorization": f"Bearer {patient_token}"},
        json={
            "name": "patient-created-discount",
            "discount_type": "percentage",
            "value": 99,
            "min_amount": 0,
        },
    )

    assert response.status_code == 403
    assert db_session.query(Discount).count() == before_count


def test_patient_cannot_read_discount_benefit_analytics(
    client: TestClient,
    patient_token: str,
) -> None:
    response = client.get(
        "/api/v1/discount-benefits/analytics/discounts",
        headers={"Authorization": f"Bearer {patient_token}"},
    )

    assert response.status_code == 403
