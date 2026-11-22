"""NOTIFYLIVEAUTH-BE-001 residual — WebSocket re-check must see fresh
principal attributes, not identity-map copies.

The periodic live re-authorization merged in #4079 reuses the handshake DB
session (no new checkout per idle socket). A plain re-query on that session
hits the SQLAlchemy identity map: the ``User`` loaded at handshake is
returned without refreshed column values, so ``is_active`` / ``role`` /
row-deletion committed by another session (or process) stayed invisible and
the socket survived revocation. Group102 corrected the registry row back to
unchecked; the required remedy is a session-lifetime proof plus a fix.

These tests model the "other session" divergence with raw SQL on the shared
connection (bypassing the handshake session's identity map entirely — a
separate real session commits the same database state), then assert the
canonical resolver observes CURRENT database state:

- deactivated user (``is_active=False``) → resolver rejects (None);
- role change → re-checked principal carries the new role (no stale copy);
- deleted user row → resolver returns None (no ghost from the identity map).

Run: pytest backend/tests/unit/test_websocket_auth_identity_freshness.py -v
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.api.v1.endpoints.websocket_auth import resolve_websocket_token_user
from app.core.security import create_access_token


def _mint(user_id: int) -> str:
    return create_access_token(str(user_id))


@pytest.mark.unit
class TestWebsocketAuthIdentityFreshness:
    def test_recheck_rejects_user_deactivated_after_handshake(
        self, db_session, test_doctor_user
    ):
        token = _mint(test_doctor_user.id)
        handshake_user = resolve_websocket_token_user(token, db_session)
        assert handshake_user is not None
        assert handshake_user.is_active is True

        # "Other session" write: bypass the handshake session's identity map
        # with raw SQL — exactly the state another session/process commits.
        db_session.execute(
            text("UPDATE users SET is_active = 0 WHERE id = :i"),
            {"i": test_doctor_user.id},
        )

        # The periodic re-check must observe current database state, not the
        # identity-map copy loaded at handshake time.
        assert resolve_websocket_token_user(token, db_session) is None

    def test_recheck_sees_role_changed_after_handshake(
        self, db_session, test_doctor_user
    ):
        token = _mint(test_doctor_user.id)
        handshake_user = resolve_websocket_token_user(token, db_session)
        role_before = handshake_user.role
        new_role = "Registrar" if role_before != "Registrar" else "Doctor"

        db_session.execute(
            text("UPDATE users SET role = :r WHERE id = :i"),
            {"r": new_role, "i": test_doctor_user.id},
        )

        rechecked = resolve_websocket_token_user(token, db_session)
        assert rechecked is not None
        assert rechecked.role == new_role, (
            "re-check returned a stale identity-map copy with role="
            f"{role_before}"
        )

    def test_recheck_rejects_user_row_deleted_after_handshake(
        self, db_session, test_doctor_user
    ):
        token = _mint(test_doctor_user.id)
        assert resolve_websocket_token_user(token, db_session) is not None

        db_session.execute(
            text("DELETE FROM users WHERE id = :i"), {"i": test_doctor_user.id}
        )

        assert resolve_websocket_token_user(token, db_session) is None
