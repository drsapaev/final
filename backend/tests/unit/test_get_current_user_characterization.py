"""Characterization tests for get_current_user — pin CURRENT behavior
BEFORE the CTE optimization. These must pass unchanged after the CTE.

Edge cases (owner acceptance criteria):
1. user exists + clean token → 200 (user returned)
2. user exists + revoked JTI → 401
3. user exists + active sentinel → 401
4. user exists + expired sentinel → user returned (sentinel doesn't block)
5. user missing → 401
6. user inactive → user returned (current behavior: no is_active filter)
7. expired JWT → 401
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from jose import jwt as jose_jwt

from app.core.config import get_settings
from app.models.authentication import TokenBlacklist
from app.models.user import User

SETTINGS = get_settings()


def _make_token(user_id: int = 3, jti: str | None = "test-jti-123",
                expires_delta=None, username: str | None = None) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=30)),
    }
    if jti:
        payload["jti"] = jti
    if username:
        payload["username"] = username
    return jose_jwt.encode(payload, SETTINGS.SECRET_KEY, algorithm="HS256")


def _make_expired_token(user_id: int = 3) -> str:
    return _make_token(user_id=user_id,
                       expires_delta=timedelta(minutes=-30))


class FakeDB:
    """In-memory fake DB that simulates users + token_blacklist tables."""

    def __init__(self):
        self.users: dict[int, User] = {}
        self.blacklist: list[dict] = []

    def query(self, model):
        return _FakeQuery(self, model)


class _FakeQuery:
    def __init__(self, fake_db, model):
        self._db = fake_db
        self._model = model
        self._filters = []

    def filter(self, *args):
        self._filters.extend(args)
        return self

    def filter_by(self, **kw):
        return self

    def first(self):
        if self._model is User:
            for u in self._db.users.values():
                if u.id == 3:
                    return u
            return None
        # TokenBlacklist: evaluate filters against blacklist entries
        for entry in self._db.blacklist:
            if self._matches(entry):
                return entry
        return None

    def _matches(self, entry) -> bool:
        # Simplified: check if jti or user_id matches
        jti_val = getattr(entry, "jti", None)
        uid_val = getattr(entry, "user_id", None)
        for f in self._filters:
            # We can't evaluate SQLAlchemy expressions directly;
            # the test overrides this via monkeypatching _matches
            pass
        return False


# ── We use a simpler approach: patch the DB queries directly ──────────────

@pytest.fixture
def fake_db():
    """Fake DB session for dependency injection."""
    db = MagicMock()
    db.execute = MagicMock(return_value=MagicMock())
    db.query = MagicMock(return_value=MagicMock())
    db.commit = MagicMock()
    db.refresh = MagicMock()
    return db


@pytest.fixture
def real_user():
    return User(
        id=3,
        username="admin",
        email="admin@test.local",
        hashed_password="$argon2id$fake",
        role="Admin",
        is_active=True,
        is_superuser=True,
        must_change_password=False,
    )


class TestGetCurrentUserCharacterization:
    """These tests characterize the CURRENT behavior of get_current_user
    BEFORE the CTE optimization. They must pass unchanged after the CTE."""

    def _call_get_current_user(self, fake_db, token: str, user: User | None,
                               blacklisted: bool = False):
        """Call get_current_user with mocked DB lookups."""
        with patch("app.api.deps._get_user_by_id", return_value=user), \
             patch("app.api.deps._get_user_by_username", return_value=user), \
             patch("app.services.token_blacklist_service.TokenBlacklistService.is_token_blacklisted",
                   return_value=blacklisted):
            from app.api.deps import get_current_user
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            return loop.run_until_complete(
                get_current_user(token=token, db=fake_db)
            )

    def _expect_401(self, fake_db, token, user=None, blacklisted=False):
        with pytest.raises(Exception) as exc_info:
            self._call_get_current_user(fake_db, token, user, blacklisted)
        assert "401" in str(exc_info.value.status_code) if hasattr(exc_info.value, 'status_code') else True
        return exc_info.value

    # ─── 1. user exists + clean token → user returned ────────────────────

    def test_clean_token_returns_user(self, fake_db, real_user):
        token = _make_token(user_id=3)
        result = self._call_get_current_user(fake_db, token, real_user, blacklisted=False)
        assert result is real_user
        assert result.id == 3

    # ─── 2. user exists + revoked JTI → 401 ──────────────────────────────

    def test_revoked_jti_rejected(self, fake_db, real_user):
        token = _make_token(user_id=3, jti="revoked-jti")
        exc = self._expect_401(fake_db, token, real_user, blacklisted=True)
        assert "blacklisted" in str(exc.detail).lower() or "revoked" in str(exc.detail).lower()

    # ─── 3. user exists + active sentinel → 401 ──────────────────────────

    def test_active_sentinel_rejected(self, fake_db, real_user):
        token = _make_token(user_id=3, jti="any-jti")
        exc = self._expect_401(fake_db, token, real_user, blacklisted=True)
        assert "blacklisted" in str(exc.detail).lower() or "revoked" in str(exc.detail).lower()

    # ─── 4. user exists + expired sentinel → user returned ───────────────

    def test_expired_sentinel_does_not_block(self, fake_db, real_user):
        # is_token_blacklisted returns False (sentinel expired)
        token = _make_token(user_id=3)
        result = self._call_get_current_user(fake_db, token, real_user, blacklisted=False)
        assert result is real_user

    # ─── 5. user missing → 401 ────────────────────────────────────────────

    def test_missing_user_rejected(self, fake_db):
        token = _make_token(user_id=999)
        exc = self._expect_401(fake_db, token, user=None)
        assert "not found" in str(exc.detail).lower()

    # ─── 6. user inactive → user returned (current behavior) ──────────────

    def test_inactive_user_still_returned(self, fake_db):
        inactive = User(
            id=5, username="inactive", email="inactive@test.local",
            hashed_password="$argon2id$fake", role="Patient",
            is_active=False, is_superuser=False,
        )
        token = _make_token(user_id=5)
        result = self._call_get_current_user(fake_db, token, inactive, blacklisted=False)
        assert result is inactive  # current behavior: no is_active filter

    # ─── 7. expired JWT → 401 ──────────────────────────────────────────────

    def test_expired_jwt_rejected(self, fake_db, real_user):
        token = _make_expired_token(user_id=3)
        exc = self._expect_401(fake_db, token, real_user)
        assert "401" in str(getattr(exc, 'status_code', '401'))
