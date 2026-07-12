from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.patient import Patient
from app.models.user import User


MOBILE_LOGIN_PATH = "/api/v1/mobile/auth/login"


def _create_mobile_user(db_session: Session) -> tuple[User, str, str]:
    suffix = uuid4().hex[:10]
    password = "mobile-secret-123"
    phone = f"+99890{suffix[:7]}"
    user = User(
        username=f"mobile_patient_{suffix}",
        email=f"mobile-patient-{suffix}@test.local",
        hashed_password=get_password_hash(password),
        role="Patient",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    patient = Patient(
        user_id=user.id,
        first_name="Mobile",
        last_name=f"Patient{suffix}",
        phone=phone,
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(user)
    return user, password, phone


def test_mobile_login_existing_phone_requires_password(
    client: TestClient,
    db_session: Session,
) -> None:
    _user, _password, phone = _create_mobile_user(db_session)

    response = client.post(MOBILE_LOGIN_PATH, json={"phone": phone})

    assert response.status_code == 401
    assert "access_token" not in response.text


def test_mobile_login_existing_phone_rejects_wrong_password(
    client: TestClient,
    db_session: Session,
) -> None:
    _user, _password, phone = _create_mobile_user(db_session)

    response = client.post(
        MOBILE_LOGIN_PATH,
        json={"phone": phone, "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert "access_token" not in response.text


def test_mobile_login_existing_phone_accepts_valid_password(
    client: TestClient,
    db_session: Session,
) -> None:
    user, password, phone = _create_mobile_user(db_session)

    response = client.post(
        MOBILE_LOGIN_PATH,
        json={"phone": phone, "password": password},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["access_token"]
    assert payload["user"]["id"] == user.id
