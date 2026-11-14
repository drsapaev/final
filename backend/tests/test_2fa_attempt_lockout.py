"""Fail-first regression tests for TWOFACTOR-BE-001 (audit group 33, #4063).

``TwoFactorService.verify_two_factor`` accepted an unlimited number of wrong
TOTP/backup/recovery codes per user, forever: the only defenses were the
optional endpoint limiter (per-IP, trivially bypassed from distributed or
rotating sources) and the 6-digit code space. A 30-second TOTP window plus
unlimited retries makes the second factor brute-forceable in practice.

Fix contract (wave 3b2):
- after 5 failed verifications the account's 2FA locks for 15 minutes
  (``locked_until``), enforced service-side, storage-backed via the new
  ``failed_attempts``/``locked_until`` columns on ``two_factor_auth``
  (alembic 0093_two_factor_attempt_lockout);
- a successful verification resets the counter;
- an expired lock self-clears and verification resumes normally;
- the endpoint contract is unchanged (200 + ``success:false`` + message on
  failure — no new status codes, no counter disclosure to the caller).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

TOTP_SECRET = "JBSWY3DPEHPK3PXP"  # valid base32 test secret
VERIFY_URL = "/api/v1/2fa/verify"


@pytest.fixture()
def two_factor_enabled(db_session, admin_user):
    """Enable TOTP 2FA for the admin user with a known secret."""
    from app.models.two_factor_auth import TwoFactorAuth

    record = TwoFactorAuth(
        user_id=admin_user.id,
        totp_enabled=True,
        totp_verified=True,
        totp_secret=TOTP_SECRET,
    )
    db_session.add(record)
    db_session.commit()
    db_session.refresh(record)
    return record


def _wrong_code(service):
    # A code from an hour ago: outside the ±1 step (30s) verification window.
    return service.generate_totp_code(
        TOTP_SECRET, int(__import__("time").time()) - 3600
    )


def _valid_code(service):
    from time import time

    return service.generate_totp_code(TOTP_SECRET, int(time()))


class TestTwoFactorBE001AttemptCap:
    def test_five_wrong_codes_lock_even_correct_code(
        self, client, auth_headers, admin_user, two_factor_enabled, db_session
    ):
        """RED: the 6th attempt with a CORRECT code succeeded (no cap).
        GREEN: 200 + success:false + lock message; DB has locked_until."""
        from app.services.two_factor_service import get_two_factor_service

        service = get_two_factor_service()
        for _ in range(5):
            resp = client.post(
                VERIFY_URL,
                json={"totp_code": _wrong_code(service)},
                headers=auth_headers,
            )
            assert resp.status_code == 200, resp.text
            assert resp.json()["success"] is False

        correct = client.post(
            VERIFY_URL,
            json={"totp_code": _valid_code(service)},
            headers=auth_headers,
        )

        assert correct.status_code == 200, correct.text
        body = correct.json()
        assert body["success"] is False
        assert "locked" in body["message"].lower()

        db_session.refresh(two_factor_enabled)
        assert two_factor_enabled.locked_until is not None
        assert two_factor_enabled.failed_attempts >= 5

    def test_success_resets_failed_counter(
        self, client, auth_headers, admin_user, two_factor_enabled, db_session
    ):
        """Three wrong attempts then a correct one: success and the stored
        counter is back to zero (RED: counter stayed at 3 / was never
        maintained)."""
        from app.services.two_factor_service import get_two_factor_service

        service = get_two_factor_service()
        for _ in range(3):
            client.post(
                VERIFY_URL,
                json={"totp_code": _wrong_code(service)},
                headers=auth_headers,
            )

        ok = client.post(
            VERIFY_URL,
            json={"totp_code": _valid_code(service)},
            headers=auth_headers,
        )
        assert ok.status_code == 200, ok.text
        assert ok.json()["success"] is True

        db_session.refresh(two_factor_enabled)
        assert (two_factor_enabled.failed_attempts or 0) == 0
        assert two_factor_enabled.locked_until is None

    def test_expired_lock_self_clears_and_verifies(
        self, client, auth_headers, admin_user, two_factor_enabled, db_session
    ):
        """A lock whose ``locked_until`` has passed must not permanently
        disable 2FA: the next correct code verifies and the lock row is
        cleared."""
        from app.services.two_factor_service import get_two_factor_service

        service = get_two_factor_service()
        two_factor_enabled.failed_attempts = 5
        two_factor_enabled.locked_until = datetime.now(UTC) - timedelta(seconds=5)
        db_session.commit()

        ok = client.post(
            VERIFY_URL,
            json={"totp_code": _valid_code(service)},
            headers=auth_headers,
        )
        assert ok.status_code == 200, ok.text
        assert ok.json()["success"] is True

        db_session.refresh(two_factor_enabled)
        assert two_factor_enabled.locked_until is None
        assert (two_factor_enabled.failed_attempts or 0) == 0
