"""Fail-first regression tests for TWOFACTOR-BE-002 (audit group 33, #4063).

``GET /two-factor/backup-codes`` returned every unused plaintext backup code to
any bearer-token holder, and ``POST /two-factor/backup-codes/regenerate`` minted
ten fresh codes with NO password and NO TOTP — inconsistent with the same
file's own policy: ``/disable`` demands both factors (AUTH-REAUDIT-28) and
``/two-factor/devices/revoke-all`` verifies the password. A transient session
compromise (token theft, unattended workstation) was convertible into a
permanent, self-service re-entry kit.

Fix contract (wave 3d):
- GET /backup-codes NEVER returns plaintext values again: ``backup_codes: []``
  + ``total`` = remaining count (one-time disclosure stays at
  enable/regenerate time, after re-authentication);
- POST /backup-codes/regenerate requires BOTH factors, mirroring /disable:
  password (401 on mismatch) + a valid TOTP or backup code (400 if absent,
  403 on mismatch). Response shape unchanged (codes + total + generated_at).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.security import (
    get_password_hash,
)  # noqa: F401  # parity with other suites
from app.models.two_factor_auth import TwoFactorAuth, TwoFactorBackupCode
from app.models.user import User
from app.services.two_factor_service import get_two_factor_service

REG_PATH = "/api/v1/2fa/backup-codes"
REGEN_PATH = "/api/v1/2fa/backup-codes/regenerate"
PASSWORD = "TestBackupCodes#2026"


@pytest.fixture()
def authed_client(client: TestClient, db_session) -> TestClient:
    """TestClient whose get_current_user resolves to the 2FA-enabled user."""
    holder: dict = {}

    def _override(token_result=None, db=None):
        return holder["user"]

    app = client.app
    app.dependency_overrides[get_current_user] = _override
    yield client, holder
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture()
def twofa_user(db_session) -> User:
    existing = (
        db_session.query(User).filter(User.username == "test_backup_codes").first()
    )
    if existing:
        db_session.delete(existing)
        db_session.commit()
    user = User(
        username="test_backup_codes",
        email="backupcodes@test.com",
        full_name="Backup Codes Tester",
        hashed_password=get_password_hash(PASSWORD),
        role="Admin",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def twofa_configured(db_session, twofa_user: User) -> tuple[User, str, list[str]]:
    """2FA enabled + three UNUSED backup codes stored RAW (old GET-path shape)."""
    service = get_two_factor_service()
    secret = service.generate_totp_secret()
    two_fa = TwoFactorAuth(
        user_id=twofa_user.id,
        totp_secret=secret,
        totp_enabled=True,
        totp_verified=True,
        recovery_enabled=False,
    )
    db_session.add(two_fa)
    db_session.flush()

    raw_codes = ["1111-2222", "3333-4444", "5555-6666"]
    for code in raw_codes:
        db_session.add(
            TwoFactorBackupCode(
                two_factor_auth_id=two_fa.id,
                code=code,
                used=False,
            )
        )
    db_session.commit()
    return twofa_user, secret, raw_codes


def _totp(secret: str) -> str:
    return get_two_factor_service().generate_totp_code(secret)


class TestTwoFactorBE002BackupCodesReauth:
    def test_get_backup_codes_never_returns_plaintext(
        self, authed_client, db_session, twofa_configured
    ):
        """RED: GET returned all unused plaintext codes to any bearer token.
        GREEN: values are never returned; only the remaining count."""
        client, holder = authed_client
        user, _secret, raw_codes = twofa_configured
        holder["user"] = user

        r = client.get(REG_PATH)

        assert r.status_code == 200, (r.status_code, r.text[:200])
        data = r.json()
        assert (
            data["backup_codes"] == []
        ), "plaintext backup codes must never be returned"
        assert data["total"] == len(raw_codes), "total must report the remaining count"
        for raw in raw_codes:
            assert raw not in r.text, f"raw code {raw} leaked in GET response"
        assert "1111" not in r.text and "5555" not in r.text

    def test_regenerate_requires_password(self, authed_client, twofa_configured):
        """RED: no-password regenerate minted 10 fresh codes. GREEN: 422
        (body required) before anything else happens."""
        client, holder = authed_client
        user, _secret, _codes = twofa_configured
        holder["user"] = user

        r = client.post(REGEN_PATH)
        assert r.status_code == 422, (r.status_code, r.text[:200])
        assert (
            "validation_error" in r.text
        ), "must fail body validation (missing password)"

    def test_regenerate_wrong_password_401(self, authed_client, twofa_configured):
        client, holder = authed_client
        user, secret, _codes = twofa_configured
        holder["user"] = user

        r = client.post(
            REGEN_PATH,
            json={"password": "definitely-wrong", "totp_code": _totp(secret)},
        )
        assert r.status_code == 401, (r.status_code, r.text[:200])

    def test_regenerate_requires_second_factor(self, authed_client, twofa_configured):
        """Password alone is not enough — parity with /disable (both factors)."""
        client, holder = authed_client
        user, _secret, _codes = twofa_configured
        holder["user"] = user

        r = client.post(REGEN_PATH, json={"password": PASSWORD})
        assert r.status_code == 400, (r.status_code, r.text[:200])
        assert "TOTP" in r.text or "backup" in r.text

    def test_regenerate_wrong_totp_403(self, authed_client, twofa_configured):
        client, holder = authed_client
        user, _secret, _codes = twofa_configured
        holder["user"] = user

        r = client.post(
            REGEN_PATH,
            json={"password": PASSWORD, "totp_code": "000000"},
        )
        assert r.status_code == 403, (r.status_code, r.text[:200])

    def test_regenerate_ok_returns_new_codes_and_invalidates_old(
        self, authed_client, db_session, twofa_configured
    ):
        """The legitimate path survives: correct password + valid TOTP →
        ten fresh codes; the old raw codes stop validating afterwards."""
        client, holder = authed_client
        user, secret, raw_codes = twofa_configured
        holder["user"] = user

        r = client.post(
            REGEN_PATH,
            json={"password": PASSWORD, "totp_code": _totp(secret)},
        )
        assert r.status_code == 200, (r.status_code, r.text[:200])
        data = r.json()
        assert len(data["backup_codes"]) == 10
        assert data["total"] == 10
        for raw in raw_codes:
            assert raw not in data["backup_codes"]

        # old codes are gone (deleted, then regenerated by the service)
        from app.models.two_factor_auth import TwoFactorAuth as TFA

        two_fa = db_session.query(TFA).filter(TFA.user_id == user.id).first()
        stored = [
            c.code
            for c in db_session.query(TwoFactorBackupCode)
            .filter(TwoFactorBackupCode.two_factor_auth_id == two_fa.id)
            .all()
        ]
        for raw in raw_codes:
            assert raw not in stored
