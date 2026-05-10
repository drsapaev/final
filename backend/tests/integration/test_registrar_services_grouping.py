from decimal import Decimal

import pytest

from app.models.clinic import ServiceCategory
from app.models.service import Service


@pytest.mark.integration
def test_registrar_services_prefers_explicit_lab_routing_over_code_fallback(
    client,
    db_session,
    admin_user,
    admin_password,
):
    lab_category = ServiceCategory(
        code="lab-adm-06",
        name_ru="Лабораторная категория ADM-06",
        specialty="laboratory",
        active=True,
    )
    db_session.add(lab_category)
    db_session.commit()
    db_session.refresh(lab_category)

    service = Service(
        name="ADM-06 Лабораторная услуга",
        code="P77",
        service_code="P77",
        category_code="P",
        category_id=lab_category.id,
        queue_tag="lab",
        department_key="lab",
        price=Decimal("15000.00"),
        currency="UZS",
        duration_minutes=30,
        active=True,
    )
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)

    login_response = client.post(
        "/api/v1/authentication/login",
        json={"username": admin_user.username, "password": admin_password},
    )
    assert login_response.status_code == 200, login_response.text

    headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
    response = client.get("/api/v1/registrar/services", headers=headers)

    assert response.status_code == 200, response.text
    payload = response.json()["services_by_group"]

    laboratory_rows = [row for row in payload["laboratory"] if row["id"] == service.id]
    procedures_rows = [row for row in payload["procedures"] if row["id"] == service.id]

    assert len(laboratory_rows) == 1
    assert laboratory_rows[0]["group"] == "laboratory"
    assert laboratory_rows[0]["queue_tag"] == "lab"
    assert laboratory_rows[0]["department_key"] == "lab"
    assert procedures_rows == []
