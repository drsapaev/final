from __future__ import annotations

import pytest

from app.core.security import get_password_hash
from app.models.user import User


@pytest.fixture
def dentist_user(db_session):
    existing = db_session.query(User).filter(User.username == "test_dentist").first()
    if existing:
        return existing

    user = User(
        username="test_dentist",
        email="dentist@test.com",
        full_name="Test Dentist",
        hashed_password=get_password_hash("dentist123"),
        role="dentist",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def dentist_auth_headers(client, dentist_user):
    response = client.post(
        "/api/v1/authentication/login",
        json={"username": dentist_user.username, "password": "dentist123"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.integration
class TestDentalApi:
    def test_dentist_role_can_create_examination(self, client, dentist_auth_headers):
        response = client.post(
            "/api/v1/dental/examinations",
            json={
                "patient_id": 451,
                "examination_date": "2026-03-22",
                "diagnosis": "Кариес дентина",
            },
            headers=dentist_auth_headers,
        )

        assert response.status_code == 200
        assert response.json()["message"] == "Стоматологический осмотр создан"

    def test_dentist_role_can_list_examinations(self, client, dentist_auth_headers):
        response = client.get(
            "/api/v1/dental/examinations?patient_id=451&limit=10",
            headers=dentist_auth_headers,
        )

        assert response.status_code == 200
        assert response.json() == []
