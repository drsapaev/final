"""Two-stage 2FA enrollment flow — server-side single-use enrollment token.

Contract under test (replaces the hard login block for critical roles
without enrolled 2FA; see the two-stage authentication design):

    POST /authentication/login  (Admin/Cashier, 2FA not enrolled)
        -> 200 {requires_2fa_setup: true, enrollment_token, NO access_token}
    POST /2fa/setup {enrollment_token}         -> QR/secret
    POST /2fa/verify-setup {enrollment_token, totp_code}
        -> success + normal access/refresh tokens, enrollment session revoked

Security boundary (the enrollment token is a server-side session token,
NOT a JWT — normal endpoints only accept JWTs):
    enrollment token as Bearer on /patients        -> 401
    enrollment token on /2fa/verify (challenge)     -> 401
    challenge pending token on /2fa/setup           -> 401
    reuse after exchange                            -> 401
    expired token                                   -> 401
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.core.security import get_password_hash
from app.models.authentication import UserSession
from app.models.user import User
from app.services.two_factor_service import get_two_factor_service

LOGIN = "/api/v1/authentication/login"
SETUP = "/api/v1/2fa/setup"
VERIFY_SETUP = "/api/v1/2fa/verify-setup"
VERIFY = "/api/v1/2fa/verify"


@pytest.fixture(autouse=True)
def _no_2fa_bypass(monkeypatch):
    """Isolate tests from a developer-machine DISABLE_2FA_REQUIREMENT=1
    that leaks from backend/.env via load_dotenv — the enrollment flow
    must be exercised with the requirement active."""
    monkeypatch.delenv("DISABLE_2FA_REQUIREMENT", raising=False)


def _make_user(db, *, username: str, role: str, password: str = "Passw0rd!123") -> User:
    user = User(
        username=username,
        email=f"{username}@test.local",
        full_name=f"Enroll {username}",
        hashed_password=get_password_hash(password),
        role=role,
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _login(client, username: str, password: str = "Passw0rd!123"):
    return client.post(LOGIN, json={"username": username, "password": password})


def _totp_now(secret: str) -> str:
    return get_two_factor_service().generate_totp_code(secret)


class TestLoginIssuesEnrollmentToken:
    def test_admin_without_2fa_gets_enrollment_token_not_access(self, client, db_session):
        _make_user(db_session, username="enr_admin", role="Admin")
        r = _login(client, "enr_admin")
        assert r.status_code == 200
        body = r.json()
        assert body.get("requires_2fa_setup") is True
        assert body.get("enrollment_token")
        assert body.get("access_token") is None
        assert body.get("refresh_token") is None

    def test_cashier_without_2fa_also_enrolls(self, client, db_session):
        _make_user(db_session, username="enr_cashier", role="Cashier")
        r = _login(client, "enr_cashier")
        assert r.status_code == 200
        assert r.json().get("requires_2fa_setup") is True

    def test_non_critical_role_login_unaffected(self, client, db_session):
        _make_user(db_session, username="enr_doctor", role="Doctor")
        r = _login(client, "enr_doctor")
        assert r.status_code == 200
        body = r.json()
        assert body.get("access_token")
        assert body.get("requires_2fa_setup") is not True

    def test_wrong_password_still_401(self, client, db_session):
        _make_user(db_session, username="enr_admin2", role="Admin")
        r = _login(client, "enr_admin2", password="wrong-password-1")
        assert r.status_code == 401


class TestEnrollmentTokenBoundary:
    def test_enrollment_token_rejected_as_bearer_on_patients(self, client, db_session):
        _make_user(db_session, username="enr_bnd", role="Admin")
        token = _login(client, "enr_bnd").json()["enrollment_token"]
        r = client.get("/api/v1/patients/", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401

    def test_enrollment_token_rejected_on_challenge_verify(self, client, db_session):
        _make_user(db_session, username="enr_chal", role="Admin")
        token = _login(client, "enr_chal").json()["enrollment_token"]
        r = client.post(VERIFY, json={"pending_2fa_token": token, "totp_code": "123456"})
        assert r.status_code == 401

    def test_challenge_pending_token_rejected_for_setup(self, client, db_session):
        user = _make_user(db_session, username="enr_pt", role="Admin")
        db_session.add(
            UserSession(
                user_id=user.id,
                refresh_token="challenge-pending-token-x",
                session_kind="pending_2fa",
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )
        db_session.commit()
        r = client.post(SETUP, json={"enrollment_token": "challenge-pending-token-x"})
        assert r.status_code == 401

    def test_expired_enrollment_token_rejected(self, client, db_session):
        user = _make_user(db_session, username="enr_exp", role="Admin")
        db_session.add(
            UserSession(
                user_id=user.id,
                refresh_token="expired-enrollment-token-x",
                session_kind="2fa_enrollment",
                expires_at=datetime.now(UTC) - timedelta(minutes=1),
            )
        )
        db_session.commit()
        r = client.post(SETUP, json={"enrollment_token": "expired-enrollment-token-x"})
        assert r.status_code == 401


class TestEnrollmentFlowCompletion:
    def test_full_flow_setup_verify_tokens(self, client, db_session):
        user = _make_user(db_session, username="enr_full", role="Admin")
        login_body = _login(client, "enr_full").json()
        token = login_body["enrollment_token"]

        r_setup = client.post(SETUP, json={"enrollment_token": token})
        assert r_setup.status_code == 200, r_setup.text
        secret = r_setup.json().get("secret_key")
        assert secret

        code = _totp_now(secret)
        r_verify = client.post(
            VERIFY_SETUP, json={"enrollment_token": token, "totp_code": code}
        )
        assert r_verify.status_code == 200, r_verify.text
        body = r_verify.json()
        assert body.get("success") is True
        assert body.get("access_token")
        assert body.get("refresh_token")

        db_session.refresh(user)
        assert user.two_factor_auth is not None
        assert user.two_factor_auth.totp_verified is True

    def test_wrong_totp_does_not_complete(self, client, db_session):
        _make_user(db_session, username="enr_bad", role="Admin")
        token = _login(client, "enr_bad").json()["enrollment_token"]
        client.post(SETUP, json={"enrollment_token": token})
        r = client.post(
            VERIFY_SETUP, json={"enrollment_token": token, "totp_code": "000000"}
        )
        assert r.status_code == 200
        assert r.json().get("success") is False
        assert not r.json().get("access_token")

    def test_enrollment_token_single_use(self, client, db_session):
        _make_user(db_session, username="enr_once", role="Admin")
        token = _login(client, "enr_once").json()["enrollment_token"]
        secret = client.post(SETUP, json={"enrollment_token": token}).json()[
            "secret_key"
        ]
        code = _totp_now(secret)
        first = client.post(
            VERIFY_SETUP, json={"enrollment_token": token, "totp_code": code}
        )
        assert first.json().get("success") is True
        # reuse: setup and verify-setup must both reject the consumed token
        assert client.post(SETUP, json={"enrollment_token": token}).status_code == 401
        second = client.post(
            VERIFY_SETUP, json={"enrollment_token": token, "totp_code": code}
        )
        assert second.status_code == 401

    def test_garbage_token_rejected(self, client, db_session):
        r = client.post(SETUP, json={"enrollment_token": "not-a-real-token"})
        assert r.status_code == 401


@pytest.mark.parametrize(
    "endpoint,body",
    [
        (SETUP, {}),
        # verify-setup требует totp_code по схеме — без кредов ожидаем 401, не 422
        (VERIFY_SETUP, {"totp_code": "123456"}),
    ],
)
def test_enrollment_endpoints_require_auth(client, endpoint, body):
    r = client.post(endpoint, json=body)
    assert r.status_code == 401
