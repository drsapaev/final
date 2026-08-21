"""Integration tests for the 2FA recovery dispatch (email channel).

Contract under test (PR: wire actual delivery into /2fa/recovery/request):
    POST /2fa/recovery/request (authenticated, 2FA enabled)
        -> 200 {recovery_token: null, expires_at}  AND a real email carrying
           the one-time token is sent to the CONFIGURED recovery address
           (never to an arbitrary recovery_value from the request body).
    SMTP failure   -> 502, no TwoFactorRecovery row persisted (no dangling
                      token the user never received).
    New request    -> burns previously unverified tokens (exactly one live).
    verify         -> token works once (single-use), second use rejected.
    PII            -> neither the token nor the address appears in logs.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.two_factor_auth import TwoFactorAuth, TwoFactorRecovery
from app.models.user import User
from app.services.two_factor_service import get_two_factor_service
from tests.conftest import mint_access_token

REQUEST = "/api/v1/2fa/recovery/request"
VERIFY = "/api/v1/2fa/verify"


@pytest.fixture
def user_with_2fa(db_session: Session):
    user = User(
        username="recovery_dispatch_user",
        email="recovery.dispatch.user@test.local",
        full_name="Recovery Dispatch",
        hashed_password=get_password_hash("Passw0rd!123"),
        role="Registrar",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    tfa = TwoFactorAuth(
        user_id=user.id,
        totp_secret="JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP",
        totp_enabled=True,
        totp_verified=True,
        backup_codes_generated=False,
        backup_codes_count=0,
        recovery_enabled=True,
        recovery_email="configured.recovery@test.local",
    )
    db_session.add(tfa)
    db_session.commit()
    db_session.refresh(tfa)
    return user, tfa


def _headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {mint_access_token(user)}"}


def _rows(db_session: Session, tfa_id: int) -> list[TwoFactorRecovery]:
    return (
        db_session.query(TwoFactorRecovery)
        .filter(TwoFactorRecovery.two_factor_auth_id == tfa_id)
        .order_by(TwoFactorRecovery.id)
        .all()
    )


@pytest.fixture
def capture_send(monkeypatch):
    """Capture dispatch calls; (sent_tokens, fail_flag holder)."""
    state = {"tokens": [], "fail": False}

    async def fake_send(to_email, subject, **kwargs):
        assert to_email == "configured.recovery@test.local", (
            "доставка должна идти на НАСТРОЕННЫЙ recovery_email, "
            f"а не на произвольный ({to_email})"
        )
        if state["fail"]:
            return False, "smtp unavailable"
        # Токен приезжает в text_content письма
        token = kwargs.get("text_content", "").split("восстановления: ")[-1].split()[0]
        state["tokens"].append(token)
        return True, "sent"

    svc = get_two_factor_service()
    monkeypatch.setattr(svc.email_service, "send_email_enhanced", fake_send)
    return state


def test_recovery_email_dispatched_and_stored(
    client, db_session, user_with_2fa, capture_send, caplog
):
    user, tfa = user_with_2fa
    with caplog.at_level(logging.INFO):
        resp = client.post(
            REQUEST,
            headers=_headers(user),
            json={
                "recovery_type": "email",
                "recovery_value": "attacker@evil.example",  # попытка подмены
            },
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["recovery_token"] is None  # токен не возвращается
    assert body["expires_at"] is not None

    rows = _rows(db_session, tfa.id)
    assert len(rows) == 1
    assert rows[0].verified is False
    assert rows[0].recovery_token == capture_send["tokens"][0]
    assert rows[0].recovery_value == "configured.recovery@test.local"

    # PII/secret hygiene: ни токен, ни адрес — не в логах
    assert capture_send["tokens"][0] not in caplog.text
    assert "configured.recovery@test.local" not in caplog.text


def test_smtp_failure_leaves_no_dangling_token(
    client, db_session, user_with_2fa, capture_send
):
    user, tfa = user_with_2fa
    capture_send["fail"] = True

    resp = client.post(
        REQUEST,
        headers=_headers(user),
        json={"recovery_type": "email", "recovery_value": "x"},
    )
    assert resp.status_code == 502
    assert _rows(db_session, tfa.id) == []

    # После восстановления провайдера повтор проходит чисто
    capture_send["fail"] = False
    resp2 = client.post(
        REQUEST, headers=_headers(user),
        json={"recovery_type": "email", "recovery_value": "x"},
    )
    assert resp2.status_code == 200
    assert len(_rows(db_session, tfa.id)) == 1


def test_new_request_burns_previous_tokens(
    client, db_session, user_with_2fa, capture_send
):
    user, tfa = user_with_2fa
    for _ in range(2):
        resp = client.post(
            REQUEST, headers=_headers(user),
            json={"recovery_type": "email", "recovery_value": "x"},
        )
        assert resp.status_code == 200

    rows = _rows(db_session, tfa.id)
    assert len(rows) == 2
    assert rows[0].verified is True   # старый сожжён
    assert rows[1].verified is False  # действует только новый

    svc = get_two_factor_service()
    ok_old, _, _ = svc.verify_two_factor(
        db_session, user.id, recovery_token=capture_send["tokens"][0]
    )
    ok_new, _, _ = svc.verify_two_factor(
        db_session, user.id, recovery_token=capture_send["tokens"][1]
    )
    assert ok_old is False
    assert ok_new is True

    # Одноразовость: второй прогон того же токена отклоняется
    ok_repeat, _, _ = svc.verify_two_factor(
        db_session, user.id, recovery_token=capture_send["tokens"][1]
    )
    assert ok_repeat is False


def test_expired_token_rejected(
    client, db_session, user_with_2fa, capture_send
):
    user, tfa = user_with_2fa
    resp = client.post(
        REQUEST, headers=_headers(user),
        json={"recovery_type": "email", "recovery_value": "x"},
    )
    assert resp.status_code == 200

    # Старим токен вручную
    db_session.query(TwoFactorRecovery).filter(
        TwoFactorRecovery.two_factor_auth_id == tfa.id
    ).update({"expires_at": datetime.now(UTC) - timedelta(minutes=1)})
    db_session.commit()

    svc = get_two_factor_service()
    ok, _, _ = svc.verify_two_factor(
        db_session, user.id, recovery_token=capture_send["tokens"][0]
    )
    assert ok is False


def test_unconfigured_channel_and_unsupported_types(
    client, db_session, user_with_2fa, capture_send
):
    user, tfa = user_with_2fa
    tfa.recovery_email = None
    db_session.commit()

    r1 = client.post(
        REQUEST, headers=_headers(user),
        json={"recovery_type": "email", "recovery_value": "x"},
    )
    assert r1.status_code == 400
    assert _rows(db_session, tfa.id) == []

    tfa.recovery_email = "configured.recovery@test.local"
    db_session.commit()
    r2 = client.post(
        REQUEST, headers=_headers(user),
        json={"recovery_type": "phone", "recovery_value": "+998901234567"},
    )
    assert r2.status_code == 503
    assert capture_send["tokens"] == []

    r3 = client.post(
        REQUEST, headers=_headers(user),
        json={"recovery_type": "backup_code", "recovery_value": "x"},
    )
    assert r3.status_code == 400


def test_requires_authentication(client, user_with_2fa):
    resp = client.post(
        REQUEST, headers={},
        json={"recovery_type": "email", "recovery_value": "x"},
    )
    assert resp.status_code in (401, 403)

