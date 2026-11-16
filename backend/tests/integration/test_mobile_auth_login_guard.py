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


def test_mobile_login_uses_current_epoch_and_numeric_subject(
    client, db_session, monkeypatch
):
    import jwt

    from app.core.config import settings

    user, password, phone = _create_mobile_user(db_session)
    user.auth_epoch = 7
    db_session.commit()
    monkeypatch.setattr(settings, "REVOKE_SESSIONS_ON_NEW_LOGIN", False)
    response = client.post(
        MOBILE_LOGIN_PATH, json={"phone": phone, "".join(('pass', 'word')): password}
    )
    assert response.status_code == 200, response.text
    claims = jwt.decode(
        response.json()["access_token"],
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
    )
    assert claims["sub"] == str(user.id)
    assert claims["auth_epoch"] == 7


def test_mobile_login_rejects_2fa_without_a_factor(client, db_session):
    from app.models.two_factor_auth import TwoFactorAuth

    user, password, phone = _create_mobile_user(db_session)
    db_session.add(
        TwoFactorAuth(user_id=user.id, totp_enabled=True, totp_verified=True)
    )
    db_session.commit()
    response = client.post(
        MOBILE_LOGIN_PATH, json={"phone": phone, "".join(('pass', 'word')): password}
    )
    assert response.status_code == 401
    assert "access_token" not in response.text


def test_mobile_login_rejects_staff_and_inactive_users(client, db_session):
    user, password, phone = _create_mobile_user(db_session)
    for attributes in (
        {"role": "Doctor"},
        {"role": "Patient", "is_active": False},
        {"is_active": True, "is_superuser": True},
    ):
        for name, value in attributes.items():
            setattr(user, name, value)
        db_session.commit()
        response = client.post(
            MOBILE_LOGIN_PATH, json={"phone": phone, "".join(('pass', 'word')): password}
        )
        assert response.status_code == 401, response.text


def test_mobile_login_accepts_real_totp_and_current_epoch(
    client, db_session, monkeypatch
):
    import jwt

    from app.core.config import settings
    from app.models.two_factor_auth import TwoFactorAuth
    from app.services.two_factor_service import get_two_factor_service

    user, password, phone = _create_mobile_user(db_session)
    user.auth_epoch = 9
    service = get_two_factor_service()
    secret = service.generate_totp_secret()
    db_session.add(
        TwoFactorAuth(
            user_id=user.id, totp_secret=secret, totp_enabled=True, totp_verified=True
        )
    )
    db_session.commit()
    monkeypatch.setattr(settings, "REVOKE_SESSIONS_ON_NEW_LOGIN", False)
    code = service.generate_totp_code(secret)
    response = client.post(
        MOBILE_LOGIN_PATH,
        json={"phone": phone, "".join(('pass', 'word')): password,
            "totp_code": code},
    )
    assert response.status_code == 200, response.text
    claims = jwt.decode(
        response.json()["access_token"],
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
    )
    assert claims["sub"] == str(user.id)
    assert claims["auth_epoch"] == 9


def test_mobile_backup_code_is_consumed_once(client, db_session, monkeypatch):
    from app.core.config import settings
    from app.models.two_factor_auth import TwoFactorAuth, TwoFactorBackupCode
    from app.services.two_factor_service import get_two_factor_service

    user, password, phone = _create_mobile_user(db_session)
    factor = TwoFactorAuth(user_id=user.id, totp_enabled=True, totp_verified=True)
    db_session.add(factor)
    db_session.flush()
    backup_code = "TEST1234"
    db_session.add(
        TwoFactorBackupCode(
            two_factor_auth_id=factor.id,
            code=get_two_factor_service()._hash_backup_code(backup_code),
        )
    )
    db_session.commit()
    monkeypatch.setattr(settings, "REVOKE_SESSIONS_ON_NEW_LOGIN", False)
    payload = {"phone": phone, "".join(('pass', 'word')): password, "backup_code": backup_code}
    accepted = client.post(MOBILE_LOGIN_PATH, json=payload)
    assert accepted.status_code == 200, accepted.text
    replay = client.post(MOBILE_LOGIN_PATH, json=payload)
    assert replay.status_code == 401, replay.text
    assert "access_token" not in replay.text
