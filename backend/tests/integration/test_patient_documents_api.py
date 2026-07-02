from datetime import date

import pytest


@pytest.mark.integration
def test_create_patient_accepts_document_type_and_number_pair(
    client,
    admin_user,
    admin_password,
):
    login_response = client.post(
        "/api/v1/authentication/login",
        json={
            "username": admin_user.username,
            "password": admin_password,
        },
    )
    assert login_response.status_code == 200, login_response.text

    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/api/v1/patients/",
        json={
            "last_name": "Документ",
            "first_name": "Пара",
            "middle_name": "Тест",
            "birth_date": str(date(1991, 4, 15)),
            "sex": "M",
            "phone": "+998901234599",
            "doc_type": "passport",
            "doc_number": "AA7654321",
            "address": "QA patient document test",
        },
        headers=headers,
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["doc_type"] == "passport"
    assert data["doc_number"] == "AA7654321"
    assert data["last_name"] == "Документ"
