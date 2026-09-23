"""
Тесты одного SQL roundtrip в deps.get_current_user (perf #2772).

Проверяет:
- numeric-sub, text-sub и username-claim токены: ровно 1 SELECT за вызов
  get_current_user (user fetch + blacklist jti + sentinel в одном запросе)
- отзыв jti и sentinel "all_user_tokens" → 401 "Token has been revoked"
- TokenBlacklistService.is_token_blacklisted: ровно 1 SELECT (регрессия
  дублирования класса из #2881, когда старая версия с 2 SELECTs
  затеняла OR-версию)
"""

import asyncio
import threading
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import HTTPException
from sqlalchemy import event

from app.api.deps import (
    _get_user_with_blacklist,
    create_access_token,
    get_current_user,
)
from app.core.config import settings
from app.models.authentication import TokenBlacklist
from app.models.user import User
from app.services.token_blacklist_service import TokenBlacklistService


def _decode(token: str) -> dict:
    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[getattr(settings, "ALGORITHM", "HS256")],
    )


class _SelectCounter:
    """Считает SELECT-статменты на уровне engine (savepoint-служебные команды не считает)."""

    def __init__(self, engine):
        self.count = 0
        event.listen(engine, "before_cursor_execute", self._on_statement)

    def _on_statement(self, conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            self.count += 1

    def stop(self, engine):
        event.remove(engine, "before_cursor_execute", self._on_statement)


def _engine_of(session):
    return session.get_bind().engine


def _call_get_current_user(db_session, token: str) -> User:
    return asyncio.run(get_current_user(token=token, db=db_session))


def test_sync_auth_query_releases_event_loop_while_waiting():
    started = threading.Event()
    release = threading.Event()
    expected_user = object()

    class FakeResult:
        def first(self):
            return expected_user, False, True

    class FakeSyncSession:
        calls = 0

        def execute(self, _statement):
            self.calls += 1
            started.set()
            if not release.wait(timeout=5):
                raise AssertionError("fake database call was not released")
            return FakeResult()

    db = FakeSyncSession()

    async def check():
        auth_task = asyncio.create_task(
            _get_user_with_blacklist(db, jti="test-jti", user_id=1)
        )
        try:
            assert await asyncio.wait_for(asyncio.to_thread(started.wait, 3), 4)
            event_loop_was_free = not auth_task.done()
        finally:
            release.set()
        result = await auth_task
        assert event_loop_was_free
        return result

    user, blacklisted = asyncio.run(check())
    assert user is expected_user
    assert blacklisted is True
    assert db.calls == 1


def test_async_auth_query_still_uses_single_execute():
    expected_user = object()

    class FakeResult:
        def first(self):
            return expected_user, False, False

    class FakeAsyncSession:
        calls = 0

        async def execute(self, _statement):
            self.calls += 1
            return FakeResult()

    db = FakeAsyncSession()
    user, blacklisted = asyncio.run(
        _get_user_with_blacklist(db, jti="test-jti", username="test-user")
    )
    assert user is expected_user
    assert blacklisted is False
    assert db.calls == 1


@pytest.fixture
def auth_user(db_session):
    user = User(
        username="auth_rt_user",
        email="auth_rt@test.com",
        full_name="Auth Roundtrip",
        hashed_password="not-verified-here",
        role="Doctor",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_numeric_sub_single_select(db_session, auth_user):
    token = create_access_token({"sub": str(auth_user.id)})
    engine = _engine_of(db_session)
    counter = _SelectCounter(engine)
    try:
        user = _call_get_current_user(db_session, token)
    finally:
        counter.stop(engine)

    assert user.id == auth_user.id
    assert user.role == "Doctor"
    assert user.is_active is True
    assert counter.count == 1


def test_text_sub_single_select(db_session, auth_user):
    token = create_access_token({"sub": auth_user.username})
    engine = _engine_of(db_session)
    counter = _SelectCounter(engine)
    try:
        user = _call_get_current_user(db_session, token)
    finally:
        counter.stop(engine)

    assert user.id == auth_user.id
    assert counter.count == 1


def test_username_claim_canonical_login_single_select(db_session, auth_user):
    # Каноническая форма токена 2FA-логина: username-claim имеет приоритет
    token = create_access_token(
        {
            "sub": str(auth_user.id),
            "username": auth_user.username,
            "role": auth_user.role,
            "is_active": auth_user.is_active,
            "is_superuser": auth_user.is_superuser,
        }
    )
    engine = _engine_of(db_session)
    counter = _SelectCounter(engine)
    try:
        user = _call_get_current_user(db_session, token)
    finally:
        counter.stop(engine)

    assert user.id == auth_user.id
    assert counter.count == 1


def test_revoked_jti_single_select(db_session, auth_user):
    token = create_access_token({"sub": str(auth_user.id)})
    payload = _decode(token)
    db_session.add(
        TokenBlacklist(
            jti=payload["jti"],
            user_id=auth_user.id,
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
            reason="logout",
        )
    )
    db_session.commit()

    engine = _engine_of(db_session)
    counter = _SelectCounter(engine)
    try:
        with pytest.raises(HTTPException) as exc:
            _call_get_current_user(db_session, token)
    finally:
        counter.stop(engine)

    assert exc.value.status_code == 401
    assert exc.value.detail == "Token has been revoked"
    assert counter.count == 1


def test_sentinel_revokes_all_user_tokens(db_session, auth_user):
    token = create_access_token({"sub": auth_user.username})
    TokenBlacklistService.blacklist_all_user_tokens(
        db_session, auth_user.id, reason="password_change"
    )

    engine = _engine_of(db_session)
    counter = _SelectCounter(engine)
    try:
        with pytest.raises(HTTPException) as exc:
            _call_get_current_user(db_session, token)
    finally:
        counter.stop(engine)

    assert exc.value.status_code == 401
    assert exc.value.detail == "Token has been revoked"
    assert counter.count == 1


def test_unknown_user_401(db_session):
    token = create_access_token({"sub": "999999"})
    with pytest.raises(HTTPException) as exc:
        _call_get_current_user(db_session, token)

    assert exc.value.status_code == 401
    assert exc.value.detail == "User not found"


def test_invalid_token_401_user_not_found(db_session):
    # Невалидный JWT: старое поведение — 401 "User not found" (пользователь не разрешён)
    with pytest.raises(HTTPException) as exc:
        _call_get_current_user(db_session, "not-a-jwt")

    assert exc.value.status_code == 401
    assert exc.value.detail == "User not found"


def test_service_is_token_blacklisted_single_select(db_session, auth_user):
    engine = _engine_of(db_session)
    counter = _SelectCounter(engine)
    try:
        result = TokenBlacklistService.is_token_blacklisted(
            db_session, "no-such-jti", user_id=auth_user.id
        )
    finally:
        counter.stop(engine)

    assert result is False
    assert counter.count == 1


def test_service_jti_and_sentinel_hits(db_session, auth_user):
    ok = TokenBlacklistService.blacklist_token(
        db_session,
        jti="fixed-jti-abc",
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
        user_id=auth_user.id,
        reason="logout",
    )
    assert ok is True
    assert (
        TokenBlacklistService.is_token_blacklisted(
            db_session, "fixed-jti-abc", user_id=auth_user.id
        )
        is True
    )

    TokenBlacklistService.blacklist_all_user_tokens(
        db_session, auth_user.id, reason="security"
    )
    # Свежий (не отозванный) jti того же пользователя блокируется sentinel-записью
    assert (
        TokenBlacklistService.is_token_blacklisted(
            db_session, "brand-new-jti", user_id=auth_user.id
        )
        is True
    )
    # Другой пользователь не затронут
    assert (
        TokenBlacklistService.is_token_blacklisted(
            db_session, "brand-new-jti", user_id=auth_user.id + 1
        )
        is False
    )
