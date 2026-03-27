import pytest

from app.models.clinic import ServiceCategory
from app.models.service import Service


def _login_admin(client, admin_user):
    login_response = client.post(
        "/api/v1/authentication/login",
        json={"username": admin_user.username, "password": "admin123"},
    )
    assert login_response.status_code == 200, login_response.text
    return {"Authorization": f"Bearer {login_response.json()['access_token']}"}


@pytest.mark.integration
def test_service_create_rejects_prefix_mismatch_for_selected_category(
    client,
    db_session,
    admin_user,
):
    lab_category = ServiceCategory(
        code="adm-06-lab-prefix",
        name_ru="ADM-06 Лаборатория",
        specialty="laboratory",
        active=True,
    )
    db_session.add(lab_category)
    db_session.commit()
    db_session.refresh(lab_category)

    headers = _login_admin(client, admin_user)
    response = client.post(
        "/api/v1/services",
        json={
            "name": "ADM-06 Prefix Mismatch",
            "code": "P77",
            "service_code": "P77",
            "category_id": lab_category.id,
            "queue_tag": "lab",
            "department_key": "lab",
            "category_code": "P",
            "price": 15000,
            "currency": "UZS",
            "duration_minutes": 30,
            "active": True,
        },
        headers=headers,
    )

    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert "Допустимые префиксы: L" in detail


@pytest.mark.integration
def test_service_create_accepts_allowed_prefixes_for_procedures(
    client,
    db_session,
    admin_user,
):
    procedures_category = ServiceCategory(
        code="adm-06-proc-prefix",
        name_ru="ADM-06 Процедуры",
        specialty="procedures",
        active=True,
    )
    db_session.add(procedures_category)
    db_session.commit()
    db_session.refresh(procedures_category)

    headers = _login_admin(client, admin_user)
    response = client.post(
        "/api/v1/services",
        json={
            "name": "ADM-06 Procedure Service",
            "code": "C77",
            "service_code": "C77",
            "category_id": procedures_category.id,
            "queue_tag": "procedures",
            "department_key": "procedures",
            "category_code": "C",
            "price": 15000,
            "currency": "UZS",
            "duration_minutes": 30,
            "active": True,
        },
        headers=headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["code"] == "C77"
    assert body["service_code"] == "C77"
    assert body["category_code"] == "C"
    assert body["queue_tag"] == "procedures"
    assert body["department_key"] == "procedures"
