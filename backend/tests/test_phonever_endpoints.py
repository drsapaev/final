"""Fail-first regression tests for PHONEVER-BE-001/002/003 (audit group 33, #4063).

- PHONEVER-BE-001: ``POST /phone-verification/send-code`` forwarded
  ``custom_message`` verbatim to the SMS service (attacker-controlled SMS body
  under the clinic's sender identity), accepted arbitrary recipient phones with
  no ownership binding, and its purpose allowlist included ``password_reset``
  (minting reset codes outside the 3/minute ``/password-reset/initiate`` gate).
- PHONEVER-BE-002: ``GET /status`` and ``DELETE /cancel`` operated on fully
  caller-chosen phone/purpose — a cross-user verification-state oracle and a
  cancellation DoS on a victim's pending code.
- PHONEVER-BE-003: ``POST /verify-code`` lacked the endpoint limiter its
  sibling ``/send-code`` carries.

Fix contract (wave 3e):
- send-code: ``custom_message`` → 400 (admin-only via /admin/send-code);
  purposes narrowed to ``verification`` | ``phone_change`` (password_reset /
  registration removed from the authenticated surface); record stores the
  requesting user_id.
- status/cancel/verify: unknown purposes and records owned by another user are
  indistinguishable from missing records (``exists: False`` / 404
  CODE_NOT_FOUND) — no oracle, no cross-user cancel; Admin/SuperAdmin bypass.
- verify-code: endpoint limiter 5/minute mirroring /send-code.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.rate_limiter import limiter
from app.core.security import get_password_hash
from app.models.user import User
from app.services.phone_verification_service import get_phone_verification_service

PASSWORD = "PhoneVerTest#2026"


def _fresh_phone() -> str:
    """Unique +998 number per use — the service singleton rate-limits
    re-sends to the same phone+purpose for a minute and persists across tests."""
    from uuid import uuid4

    return f"+99890{uuid4().int % 10_000_000:07d}"


SEND_PATH = "/api/v1/phone-verification/send-code"
VERIFY_PATH = "/api/v1/phone-verification/verify-code"
STATUS_PATH = "/api/v1/phone-verification/status"
CANCEL_PATH = "/api/v1/phone-verification/cancel"


@pytest.fixture()
def sms_stub(db_session, monkeypatch):
    """Deterministic SMS success (no real provider in tests)."""
    svc = get_phone_verification_service()

    async def _send(phone, message, provider_type=None):
        return SimpleNamespace(
            success=True, message_id="test-mid", provider="mock", error=None
        )

    monkeypatch.setattr(svc, "sms_manager", SimpleNamespace(send_sms=_send))
    return svc


@pytest.fixture()
def authed_client(client: TestClient):
    holder: dict = {}

    def _override(token_result=None, db=None):
        return holder["user"]

    app = client.app
    app.dependency_overrides[get_current_user] = _override
    yield client, holder
    app.dependency_overrides.pop(get_current_user, None)


def _make_user(db_session, username: str, email: str, role: str = "Admin") -> User:
    existing = db_session.query(User).filter(User.username == username).first()
    if existing:
        return existing
    user = User(
        username=username,
        email=email,
        full_name=username,
        hashed_password=get_password_hash(PASSWORD),
        role=role,
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def users(db_session):
    a = _make_user(db_session, "phonever_user_a", "phonever_a@test.com", role="Cashier")
    b = _make_user(db_session, "phonever_user_b", "phonever_b@test.com", role="Cashier")
    admin = _make_user(
        db_session, "phonever_admin", "phonever_admin@test.com", "SuperAdmin"
    )
    return SimpleNamespace(a=a, b=b, admin=admin)


def _send(client, phone: str, purpose: str = "verification", **extra):
    return client.post(SEND_PATH, json={"phone": phone, "purpose": purpose, **extra})


class TestPhoneverBE001SendRestrictions:
    def test_send_code_rejects_custom_message(
        self, authed_client, db_session, users, sms_stub
    ):
        """RED: custom_message reached the SMS body verbatim. GREEN: 400 —
        arbitrary SMS content is admin-only (/admin/send-code)."""
        client, holder = authed_client
        holder["user"] = users.a
        phone = _fresh_phone()

        r = _send(client, phone, custom_message="Выиграй iPhone! Код: {code}")

        assert r.status_code == 400, (r.status_code, r.text[:200])

    def test_send_code_rejects_password_reset_purpose(
        self, authed_client, db_session, users, sms_stub
    ):
        """RED: authenticated users minted password_reset codes outside the
        3/min /password-reset/initiate gate. GREEN: 422 — the purpose is not
        part of the authenticated send surface."""
        client, holder = authed_client
        holder["user"] = users.a
        phone = _fresh_phone()

        r = _send(client, phone, purpose="password_reset")

        assert r.status_code == 422, (r.status_code, r.text[:200])

    def test_send_code_records_owner(self, authed_client, db_session, users, sms_stub):
        """RED: records carried no owner — status/cancel/verify could not be
        bound. GREEN: the record stores the requesting user's id."""
        client, holder = authed_client
        holder["user"] = users.a
        phone = _fresh_phone()

        r = _send(client, phone)

        assert r.status_code == 200, (r.status_code, r.text[:200])
        svc = sms_stub
        record = svc.verification_codes.get(svc._get_code_key(phone, "verification"))
        assert record is not None, "record must exist after successful send"
        assert (
            record.get("user_id") == users.a.id
        ), f"record must bind owner user_id={users.a.id}, got {record.get('user_id')}"


class TestPhoneverBE002OwnershipMasking:
    def test_status_of_other_users_phone_is_masked(
        self, authed_client, db_session, users, sms_stub
    ):
        """RED: any user read purpose/expiry/attempts of ANY phone. GREEN:
        a foreign record is indistinguishable from a missing one."""
        client, holder = authed_client
        holder["user"] = users.a
        phone = _fresh_phone()
        assert _send(client, phone).status_code == 200

        # owner sees it
        holder["user"] = users.a
        r_owner = client.get(
            STATUS_PATH, params={"phone": phone, "purpose": "verification"}
        )
        assert r_owner.status_code == 200 and r_owner.json()["exists"] is True

        # foreign user sees exactly the missing-record shape
        holder["user"] = users.b
        r_b = client.get(
            STATUS_PATH, params={"phone": phone, "purpose": "verification"}
        )
        assert r_b.status_code == 200, (r_b.status_code, r_b.text[:200])
        assert r_b.json() == {"exists": False, "verified": False}, r_b.json()

        # admin still sees it
        holder["user"] = users.admin
        r_admin = client.get(
            STATUS_PATH, params={"phone": phone, "purpose": "verification"}
        )
        assert r_admin.json()["exists"] is True

    def test_cancel_of_other_users_phone_is_404_and_record_survives(
        self, authed_client, db_session, users, sms_stub
    ):
        """RED: any user could delete a victim's pending code (DoS). GREEN:
        foreign cancel is 404 and the record survives."""
        client, holder = authed_client
        holder["user"] = users.a
        phone = _fresh_phone()
        assert _send(client, phone).status_code == 200
        svc = sms_stub
        key = svc._get_code_key(phone, "verification")

        holder["user"] = users.b
        r_b = client.delete(
            CANCEL_PATH, params={"phone": phone, "purpose": "verification"}
        )
        assert r_b.status_code == 404, (r_b.status_code, r_b.text[:200])
        assert (
            key in svc.verification_codes
        ), "foreign cancel must not delete the record"

        # owner cancels fine
        holder["user"] = users.a
        r_owner = client.delete(
            CANCEL_PATH, params={"phone": phone, "purpose": "verification"}
        )
        assert r_owner.status_code == 200
        assert key not in svc.verification_codes

    def test_verify_of_other_users_code_is_404_not_success(
        self, authed_client, db_session, users, sms_stub
    ):
        """RED: with the correct code a foreign user verified another user's
        phone; with a wrong one they probed attempts_left. GREEN: foreign
        verify is exactly CODE_NOT_FOUND (404) — no success, no attempt info."""
        client, holder = authed_client
        holder["user"] = users.a
        phone = _fresh_phone()
        assert _send(client, phone).status_code == 200
        svc = sms_stub
        real_code = svc.verification_codes[svc._get_code_key(phone, "verification")][
            "code"
        ]

        holder["user"] = users.b
        r_correct = client.post(
            VERIFY_PATH,
            json={"phone": phone, "code": real_code, "purpose": "verification"},
        )
        assert r_correct.status_code == 404, (
            r_correct.status_code,
            r_correct.text[:200],
        )
        assert "CODE_NOT_FOUND" in r_correct.text, r_correct.text[:300]

        r_wrong = client.post(
            VERIFY_PATH,
            json={"phone": phone, "code": "000000", "purpose": "verification"},
        )
        assert r_wrong.status_code == 404, (r_wrong.status_code, r_wrong.text[:200])
        assert "attempts_left" not in r_wrong.text


class TestPhoneverBE003VerifyLimiter:
    def test_verify_code_has_endpoint_limiter(
        self, authed_client, db_session, users, sms_stub, monkeypatch
    ):
        """RED: /verify-code had no endpoint limiter (sibling /send-code has
        5/minute) — brute-force rode fresh codes' attempt budgets. GREEN: the
        limiter engages (429 after the budget)."""
        client, holder = authed_client
        holder["user"] = users.a
        phone = _fresh_phone()
        assert _send(client, phone).status_code == 200

        # slowapi reads ``Limiter.enabled`` at call time (the repo's
        # ``limiter._enabled`` mutation is inert for the real decorator);
        # conftest sets TESTING=1 which constructs it with enabled=False.
        monkeypatch.setattr(limiter, "enabled", True)
        responses = []
        for _ in range(8):
            responses.append(
                client.post(
                    VERIFY_PATH,
                    json={"phone": phone, "code": "000000", "purpose": "verification"},
                )
            )
        # a bare 429 (no MAX_ATTEMPTS_EXCEEDED payload) = slowapi endpoint limiter;
        # the service-side attempts cap (429 WITH that payload) does not count —
        # it only guards one code, not fresh-code churn.
        limiter_429 = [
            r
            for r in responses
            if r.status_code == 429 and "MAX_ATTEMPTS" not in r.text
        ]
        assert limiter_429, (
            "endpoint limiter must engage: expected a bare 429 within 8 rapid calls, got "
            + ", ".join(f"{r.status_code}:{r.text[:60]}" for r in responses)
        )
