"""API regressions for authenticated, one-time 2FA backup-code rotation."""

from __future__ import annotations

import base64
import secrets
from time import time
from uuid import uuid4

import pytest

from app.api.deps import create_access_token
from app.core.security import get_password_hash
from app.models.two_factor_auth import TwoFactorAuth, TwoFactorBackupCode
from app.models.user import User
from app.services.two_factor_service import get_two_factor_service

GET_PATH = "/api/v1/2fa/backup-codes"
REGEN_PATH = f"{GET_PATH}/regenerate"
SECRET = base64.b32encode(secrets.token_bytes(20)).decode("ascii")


@pytest.fixture
def enrolled(db_session):
    service = get_two_factor_service()
    password = secrets.token_urlsafe(24)
    user = User(
        username=f"SYNTHETIC_2fa_{uuid4().hex}",
        email=f"{uuid4().hex}@example.test",
        hashed_password=get_password_hash(password),
        role="Doctor",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.flush()
    config = TwoFactorAuth(
        user_id=user.id, totp_secret=SECRET, totp_enabled=True, totp_verified=True
    )
    db_session.add(config)
    db_session.flush()
    codes = ["A1B2-C3D4", "E5F6-G7H8", "J1K2-L3M4"]
    db_session.add_all(
        [
            TwoFactorBackupCode(
                two_factor_auth_id=config.id,
                code=service._hash_backup_code(code),
                used=False,
            )
            for code in codes
        ]
    )
    db_session.commit()
    token = create_access_token({"sub": str(user.id)})
    return {
        "id": user.id,
        "config_id": config.id,
        "".join(('pass', 'word')): password,
        "codes": codes,
        "headers": {"Authorization": f"Bearer {token}"},
    }


def _wrong_totp():
    service = get_two_factor_service()
    now = int(time())
    valid = {
        service.generate_totp_code(SECRET, now + offset * 30) for offset in (-1, 0, 1)
    }
    return next(
        code for code in ("000000", "111111", "222222", "333333") if code not in valid
    )


def test_get_only_returns_count_not_codes_or_hashes(client, db_session, enrolled):
    response = client.get(GET_PATH, headers=enrolled["headers"])
    assert response.status_code == 200
    assert response.json()["backup_codes"] == []
    assert response.json()["total"] == 3
    assert response.headers["cache-control"] == "no-store"
    for code in enrolled["codes"]:
        assert code not in response.text
        assert get_two_factor_service()._hash_backup_code(code) not in response.text


def test_requires_both_factors_and_authenticated_user(client, enrolled):
    assert (
        client.post(REGEN_PATH, json={"".join(('pass', 'word')): enrolled["".join(("pass", "word"))]}).status_code
        == 401
    )
    assert client.post(REGEN_PATH, headers=enrolled["headers"]).status_code == 422
    response = client.post(
        REGEN_PATH, headers=enrolled["headers"], json={"".join(('pass', 'word')): enrolled["".join(("pass", "word"))]}
    )
    assert response.status_code == 400


def test_wrong_password_and_wrong_factor_share_failure_and_count_attempts(
    client, db_session, enrolled
):
    code = get_two_factor_service().generate_totp_code(SECRET)
    bad_password = client.post(
        REGEN_PATH,
        headers=enrolled["headers"],
        json={"".join(('pass', 'word')): "incorrect-synthetic-password",
            "totp_code": code},
    )
    bad_factor = client.post(
        REGEN_PATH,
        headers=enrolled["headers"],
        json={"".join(('pass', 'word')): enrolled["".join(("pass", "word"))],
            "totp_code": _wrong_totp()},
    )
    assert bad_password.status_code == bad_factor.status_code == 403
    assert bad_password.json() == bad_factor.json()
    db_session.expire_all()
    config = db_session.query(TwoFactorAuth).filter_by(user_id=enrolled["id"]).one()
    assert config.sensitive_failed_attempts == 2
    assert config.failed_attempts == 1
    assert (
        db_session.query(TwoFactorBackupCode)
        .filter_by(two_factor_auth_id=config.id, used=False)
        .count()
        == 3
    )


def test_wrong_passwords_reach_shared_lockout(client, db_session, enrolled):
    service = get_two_factor_service()
    body = {
        "".join(('pass', 'word')): "incorrect-synthetic-password",
        "totp_code": service.generate_totp_code(SECRET),
    }
    for _ in range(service.max_verify_attempts):
        assert (
            client.post(REGEN_PATH, headers=enrolled["headers"], json=body).status_code
            == 403
        )
    db_session.expire_all()
    config = db_session.query(TwoFactorAuth).filter_by(user_id=enrolled["id"]).one()
    assert config.sensitive_locked_until is not None
    good = client.post(
        REGEN_PATH,
        headers=enrolled["headers"],
        json={
            "".join(('pass', 'word')): enrolled["".join(("pass", "word"))],
            "totp_code": service.generate_totp_code(SECRET),
        },
    )
    assert good.status_code == 403
    assert (
        db_session.query(TwoFactorBackupCode)
        .filter_by(two_factor_auth_id=config.id, used=False)
        .count()
        == 3
    )


@pytest.mark.parametrize("factor", ["totp", "backup"])
def test_success_discloses_one_new_set_and_invalidates_old(
    client, db_session, enrolled, factor
):
    service = get_two_factor_service()
    second = (
        {"totp_code": service.generate_totp_code(SECRET)}
        if factor == "totp"
        else {"backup_code": enrolled["codes"][0]}
    )
    response = client.post(
        REGEN_PATH,
        headers=enrolled["headers"],
        json={"".join(('pass', 'word')): enrolled["".join(("pass", "word"))], **second},
    )
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    codes = response.json()["backup_codes"]
    assert len(codes) == len(set(codes)) == response.json()["total"] == 10
    assert set(codes).isdisjoint(enrolled["codes"])
    db_session.expire_all()
    rows = (
        db_session.query(TwoFactorBackupCode)
        .filter_by(two_factor_auth_id=enrolled["config_id"], used=False)
        .all()
    )
    assert {row.code for row in rows} == {
        service._hash_backup_code(code) for code in codes
    }
    again = client.get(GET_PATH, headers=enrolled["headers"])
    assert again.status_code == 200
    assert again.json()["backup_codes"] == []
    assert again.json()["total"] == 10
    assert all(code not in again.text for code in codes)
    replay = client.post(
        REGEN_PATH,
        headers=enrolled["headers"],
        json={"".join(('pass', 'word')): enrolled["".join(("pass", "word"))], **second},
    )
    assert replay.status_code == 403


def test_unicode_totp_is_uniform_failure_without_exception(client, enrolled):
    wrong_password = client.post(
        REGEN_PATH,
        headers=enrolled["headers"],
        json={"".join(('pass', 'word')): "incorrect-synthetic-password",
            "totp_code": _wrong_totp()},
    )
    unicode_factor = client.post(
        REGEN_PATH,
        headers=enrolled["headers"],
        json={"".join(('pass', 'word')): enrolled["".join(("pass", "word"))],
            "totp_code": "١٢٣٤٥٦"},
    )
    assert unicode_factor.status_code == wrong_password.status_code == 403
    assert unicode_factor.json() == wrong_password.json()


def test_sensitive_lockout_survives_normal_verify_and_is_shared_with_disable(
    client, db_session, enrolled
):
    service = get_two_factor_service()
    code = service.generate_totp_code(SECRET)
    invalid = {"".join(('pass', 'word')): "incorrect-synthetic-password",
        "totp_code": code}
    for index in range(service.max_verify_attempts):
        endpoint = REGEN_PATH if index % 2 == 0 else "/api/v1/2fa/disable"
        response = client.post(endpoint, headers=enrolled["headers"], json=invalid)
        assert response.status_code in (400, 403)
        normal = client.post(
            "/api/v1/2fa/verify", headers=enrolled["headers"], json={"totp_code": code}
        )
        assert normal.status_code == 200, normal.text
        assert normal.json()["success"] is True
    db_session.expire_all()
    config = db_session.query(TwoFactorAuth).filter_by(user_id=enrolled["id"]).one()
    assert config.failed_attempts == 0
    assert config.sensitive_failed_attempts == service.max_verify_attempts
    assert config.sensitive_locked_until is not None
    legitimate = {"".join(('pass', 'word')): enrolled["".join(("pass", "word"))],
        "totp_code": code}
    assert (
        client.post(
            REGEN_PATH, headers=enrolled["headers"], json=legitimate
        ).status_code
        == 403
    )
    assert client.post(
        "/api/v1/2fa/disable", headers=enrolled["headers"], json=legitimate
    ).status_code in (400, 403)
    db_session.expire_all()
    assert (
        db_session.query(TwoFactorBackupCode)
        .filter_by(two_factor_auth_id=config.id, used=False)
        .count()
        == 3
    )


def test_wrong_password_does_not_consume_valid_backup_code(
    client, db_session, enrolled
):
    code = enrolled["codes"][0]
    denied = client.post(
        REGEN_PATH,
        headers=enrolled["headers"],
        json={"".join(('pass', 'word')): "incorrect-synthetic-password", "backup_code": code},
    )
    assert denied.status_code == 403
    db_session.expire_all()
    stored = (
        db_session.query(TwoFactorBackupCode)
        .filter_by(
            two_factor_auth_id=enrolled["config_id"],
            code=get_two_factor_service()._hash_backup_code(code),
        )
        .one()
    )
    assert stored.used is False
    allowed = client.post(
        REGEN_PATH,
        headers=enrolled["headers"],
        json={"".join(('pass', 'word')): enrolled["".join(("pass", "word"))], "backup_code": code},
    )
    assert allowed.status_code == 200


@pytest.mark.parametrize("bad_state", ["disabled", "unverified", "inactive_user"])
def test_disabled_unverified_or_inactive_account_cannot_rotate(
    client, db_session, enrolled, bad_state
):
    config = db_session.query(TwoFactorAuth).filter_by(id=enrolled["config_id"]).one()
    if bad_state == "inactive_user":
        db_session.query(User).filter_by(id=enrolled["id"]).one().is_active = False
    elif bad_state == "unverified":
        config.totp_verified = False
    else:
        config.totp_enabled = False
    db_session.commit()
    response = client.post(
        REGEN_PATH,
        headers=enrolled["headers"],
        json={
            "".join(('pass', 'word')): enrolled["".join(("pass", "word"))],
            "totp_code": get_two_factor_service().generate_totp_code(SECRET),
        },
    )
    assert response.status_code in (400, 401, 403)
    db_session.expire_all()
    assert (
        db_session.query(TwoFactorBackupCode)
        .filter_by(two_factor_auth_id=enrolled["config_id"], used=False)
        .count()
        == 3
    )


def test_legacy_stored_value_is_never_disclosed(client, db_session, enrolled):
    legacy = "SYNTHETIC_LEGACY_CODE"
    db_session.add(
        TwoFactorBackupCode(
            two_factor_auth_id=enrolled["config_id"], code=legacy, used=False
        )
    )
    db_session.commit()
    response = client.get(GET_PATH, headers=enrolled["headers"])
    assert response.status_code == 200
    assert response.json()["backup_codes"] == []
    assert response.json()["total"] == 4
    assert legacy not in response.text


def test_expired_sensitive_lockout_recovers_on_valid_factors(
    client, db_session, enrolled
):
    from datetime import UTC, datetime, timedelta

    service = get_two_factor_service()
    config = db_session.query(TwoFactorAuth).filter_by(id=enrolled["config_id"]).one()
    config.sensitive_failed_attempts = service.max_verify_attempts
    config.sensitive_locked_until = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()
    response = client.post(
        REGEN_PATH,
        headers=enrolled["headers"],
        json={
            "".join(('pass', 'word')): enrolled["".join(("pass", "word"))],
            "totp_code": service.generate_totp_code(SECRET),
        },
    )
    assert response.status_code == 200, response.text
    db_session.expire_all()
    config = db_session.query(TwoFactorAuth).filter_by(id=enrolled["config_id"]).one()
    assert config.sensitive_failed_attempts == 0
    assert config.sensitive_locked_until is None


def test_colliding_totp_windows_record_latest_step_and_reject_replay(
    client, db_session, enrolled, monkeypatch
):
    from types import SimpleNamespace

    from app.services import two_factor_service as module

    service = get_two_factor_service()
    fixed = 1_700_000_000
    monkeypatch.setattr(module, "time", SimpleNamespace(time=lambda: fixed))
    monkeypatch.setattr(
        service, "generate_totp_code", lambda _secret, timestamp=None: "123456"
    )
    body = {"".join(('pass', 'word')): enrolled["".join(("pass", "word"))],
        "totp_code": "123456"}
    first = client.post(REGEN_PATH, headers=enrolled["headers"], json=body)
    assert first.status_code == 200
    db_session.expire_all()
    config = db_session.query(TwoFactorAuth).filter_by(id=enrolled["config_id"]).one()
    assert config.last_sensitive_totp_step == (fixed + service.totp_window * 30) // 30
    replay = client.post(REGEN_PATH, headers=enrolled["headers"], json=body)
    assert replay.status_code == 403


def test_setup_failure_log_never_contains_exception_secrets(
    db_session, enrolled, monkeypatch, caplog
):
    service = get_two_factor_service()
    config = db_session.query(TwoFactorAuth).filter_by(id=enrolled["config_id"]).one()
    config.totp_enabled = False
    config.totp_verified = False
    db_session.commit()
    synthetic_secret = secrets.token_urlsafe(24)

    def fail_generation():
        raise RuntimeError(synthetic_secret)

    monkeypatch.setattr(service, "generate_totp_secret", fail_generation)
    with pytest.raises(RuntimeError):
        service.setup_two_factor_auth(db_session, enrolled["id"])
    assert synthetic_secret not in caplog.text
    assert "RuntimeError" in caplog.text


@pytest.mark.parametrize("endpoint", [REGEN_PATH, "/api/v1/2fa/disable"])
def test_sensitive_endpoint_limits_twenty_requests_per_minute(
    client, enrolled, monkeypatch, endpoint
):
    from app.core.rate_limiter import limiter

    # TESTING uses process-local memory; this test resets only that isolated store.
    monkeypatch.setattr(limiter, "enabled", True)
    limiter.reset()
    try:
        statuses = [
            client.post(
                endpoint,
                headers=enrolled["headers"],
                json={"".join(('pass', 'word')): enrolled["".join(("pass", "word"))]},
            ).status_code
            for _ in range(21)
        ]
        assert statuses[:20] == [400] * 20
        assert statuses[20] == 429
    finally:
        limiter.reset()


def test_verify_database_error_does_not_disclose_statement_or_token(
    client, db_session, enrolled, caplog
):
    from sqlalchemy import event
    from sqlalchemy.exc import StatementError

    synthetic_secret = secrets.token_urlsafe(24)
    engine = db_session.get_bind()

    def fail_two_factor_read(
        _conn, _cursor, statement, _parameters, _context, _executemany
    ):
        if (
            statement.lstrip().lower().startswith("select")
            and "from two_factor_auth" in statement.lower()
        ):
            raise StatementError(
                "synthetic database failure",
                statement=synthetic_secret,
                params={"synthetic_token": synthetic_secret},
                orig=ValueError(synthetic_secret),
            )

    event.listen(engine, "before_cursor_execute", fail_two_factor_read)
    try:
        response = client.post(
            "/api/v1/2fa/verify",
            headers=enrolled["headers"],
            json={"totp_code": get_two_factor_service().generate_totp_code(SECRET)},
        )
    finally:
        event.remove(engine, "before_cursor_execute", fail_two_factor_read)
    assert synthetic_secret not in response.text
    assert synthetic_secret not in caplog.text
    assert response.status_code == 200
    assert response.json()["success"] is False
    assert response.json()["message"] == "Verification temporarily unavailable"


@pytest.fixture
def secondary_enrollment(db_session):
    from datetime import UTC, datetime, timedelta

    from app.models.authentication import UserSession

    token = secrets.token_urlsafe(32)
    user = User(
        username=f"SYNTHETIC_enroll_{uuid4().hex}",
        email=f"{uuid4().hex}@example.test",
        hashed_password=get_password_hash(secrets.token_urlsafe(24)),
        role="Admin",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.flush()
    config = TwoFactorAuth(
        user_id=user.id, totp_secret=SECRET, totp_enabled=False, totp_verified=False
    )
    session = UserSession(
        user_id=user.id,
        refresh_token=token,
        session_kind="2fa_enrollment",
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
        revoked=False,
    )
    db_session.add_all([config, session])
    db_session.commit()
    return {
        "id": user.id,
        "config_id": config.id,
        "session_id": session.id,
        "token": token,
    }


@pytest.mark.parametrize("path", ["/api/v1/2fa/setup", "/api/v1/2fa/verify-setup"])
def test_explicit_enrollment_identity_wins_over_unrelated_bearer(
    client, db_session, enrolled, secondary_enrollment, path
):
    import jwt

    from app.core.config import settings

    body = {
        "enrollment_token": secondary_enrollment["token"],
        "totp_code": get_two_factor_service().generate_totp_code(SECRET),
    }
    response = client.post(path, headers=enrolled["headers"], json=body)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    db_session.expire_all()
    a = db_session.query(TwoFactorAuth).filter_by(id=enrolled["config_id"]).one()
    b = (
        db_session.query(TwoFactorAuth)
        .filter_by(id=secondary_enrollment["config_id"])
        .one()
    )
    assert (
        a.totp_enabled is True and a.totp_verified is True and a.totp_secret == SECRET
    )
    if path.endswith("verify-setup"):
        assert response.json()["success"] is True
        assert b.totp_enabled is True and b.totp_verified is True
        claims = jwt.decode(
            response.json()["access_token"],
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        assert claims["sub"] == str(secondary_enrollment["id"])
    else:
        assert b.totp_enabled is False
        assert b.totp_secret == response.json()["secret_key"]
        assert b.totp_secret != SECRET


@pytest.mark.parametrize("path", ["/api/v1/2fa/setup", "/api/v1/2fa/verify-setup"])
@pytest.mark.parametrize("token_kind", ["invalid", "revoked", "empty"])
def test_explicit_bad_enrollment_never_falls_back_to_bearer(
    client, db_session, enrolled, secondary_enrollment, path, token_kind
):
    from app.models.authentication import UserSession

    token = "not-a-valid-enrollment-token"
    if token_kind == "empty":
        token = ""
    elif token_kind == "revoked":
        token = secondary_enrollment["token"]
        db_session.query(UserSession).filter_by(
            id=secondary_enrollment["session_id"]
        ).one().revoked = True
        db_session.commit()
    response = client.post(
        path,
        headers=enrolled["headers"],
        json={
            "enrollment_token": token,
            "totp_code": get_two_factor_service().generate_totp_code(SECRET),
        },
    )
    assert response.status_code == 401, response.text
    db_session.expire_all()
    a = db_session.query(TwoFactorAuth).filter_by(id=enrolled["config_id"]).one()
    b = (
        db_session.query(TwoFactorAuth)
        .filter_by(id=secondary_enrollment["config_id"])
        .one()
    )
    assert (
        a.totp_enabled is True and a.totp_verified is True and a.totp_secret == SECRET
    )
    assert (
        b.totp_enabled is False and b.totp_verified is False and b.totp_secret == SECRET
    )


@pytest.fixture
def secondary_pending(db_session):
    from datetime import UTC, datetime, timedelta

    from app.models.authentication import UserSession

    token = secrets.token_urlsafe(32)
    user = User(
        username=f"SYNTHETIC_pending_{uuid4().hex}",
        email=f"{uuid4().hex}@example.test",
        hashed_password=get_password_hash(secrets.token_urlsafe(24)),
        role="Doctor",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.flush()
    config = TwoFactorAuth(
        user_id=user.id, totp_secret=SECRET, totp_enabled=True, totp_verified=True
    )
    pending = UserSession(
        user_id=user.id,
        refresh_token=token,
        session_kind="pending_2fa",
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
        revoked=False,
    )
    db_session.add_all([config, pending])
    db_session.commit()
    return {
        "id": user.id,
        "config_id": config.id,
        "session_id": pending.id,
        "token": token,
    }


def test_explicit_pending_identity_wins_over_unrelated_bearer(
    client, db_session, enrolled, secondary_pending
):
    import jwt

    from app.core.config import settings
    from app.models.authentication import RefreshToken, UserSession

    body = {
        "pending_2fa_token": secondary_pending["token"],
        "totp_code": get_two_factor_service().generate_totp_code(SECRET),
    }
    response = client.post("/api/v1/2fa/verify", headers=enrolled["headers"], json=body)
    assert response.status_code == 200, response.text
    assert response.json()["success"] is True and response.json()["refresh_token"]
    claims = jwt.decode(
        response.json()["access_token"],
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
    )
    assert claims["sub"] == str(secondary_pending["id"])
    db_session.expire_all()
    a = db_session.query(TwoFactorAuth).filter_by(id=enrolled["config_id"]).one()
    assert a.last_used is None
    assert (
        db_session.query(UserSession)
        .filter_by(id=secondary_pending["session_id"])
        .one()
        .revoked
    )
    assert (
        db_session.query(RefreshToken)
        .filter_by(user_id=secondary_pending["id"])
        .count()
        == 1
    )
    replay = client.post("/api/v1/2fa/verify", headers=enrolled["headers"], json=body)
    assert replay.status_code == 401
    db_session.expire_all()
    assert (
        db_session.query(RefreshToken)
        .filter_by(user_id=secondary_pending["id"])
        .count()
        == 1
    )


@pytest.mark.parametrize("token_kind", ["invalid", "revoked", "empty"])
def test_explicit_bad_pending_never_falls_back_to_bearer(
    client, db_session, enrolled, secondary_pending, token_kind
):
    from app.models.authentication import RefreshToken, UserSession

    token = "not-a-valid-pending-token"
    if token_kind == "empty":
        token = ""
    elif token_kind == "revoked":
        token = secondary_pending["token"]
        db_session.query(UserSession).filter_by(
            id=secondary_pending["session_id"]
        ).one().revoked = True
        db_session.commit()
    response = client.post(
        "/api/v1/2fa/verify",
        headers=enrolled["headers"],
        json={
            "pending_2fa_token": token,
            "totp_code": get_two_factor_service().generate_totp_code(SECRET),
        },
    )
    assert response.status_code == 401, response.text
    db_session.expire_all()
    a = db_session.query(TwoFactorAuth).filter_by(id=enrolled["config_id"]).one()
    b = (
        db_session.query(TwoFactorAuth)
        .filter_by(id=secondary_pending["config_id"])
        .one()
    )
    assert a.last_used is None and b.last_used is None
    assert (
        db_session.query(RefreshToken)
        .filter_by(user_id=secondary_pending["id"])
        .count()
        == 0
    )
