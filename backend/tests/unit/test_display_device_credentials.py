"""Device credential tests use synthetic records and an in-memory database."""

from __future__ import annotations

import asyncio

import jwt
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request
from starlette.responses import Response

from app.api.v1.endpoints.display_websocket import _set_display_device_session_cookie
from app.core.config import settings
from app.db.base_class import Base
from app.middleware.idempotency_middleware import (
    IdempotencyMiddleware,
    _is_display_device_idempotency_exempt,
)
from app.models.authentication import TokenBlacklist
from app.models.display_config import DisplayBoard, DisplayBoardDevice
from app.models.user import User
from app.services.display_device_credentials import (
    DISPLAY_DEVICE_SESSION_TTL_SECONDS,
    DISPLAY_DEVICE_TOKEN_TTL_SECONDS,
    authenticate_display_device_token,
    create_display_board_device,
    exchange_display_device_secret,
    exchange_display_device_session,
    display_device_session_cookie_name,
    revoke_display_board_device,
    rotate_display_board_device,
)


@pytest.fixture()
def device_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[
            User.__table__,
            TokenBlacklist.__table__,
            DisplayBoard.__table__,
            DisplayBoardDevice.__table__,
        ],
    )
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    db = factory()
    try:
        admin = User(
            username="synthetic-admin",
            full_name="Synthetic Admin",
            hashed_password="test-only",
            role="Admin",
            is_active=True,
        )
        board = DisplayBoard(name="synthetic_board", display_name="Synthetic board")
        db.add_all([admin, board])
        db.commit()
        db.refresh(admin)
        db.refresh(board)
        yield db, admin, board
    finally:
        db.close()
        engine.dispose()


def test_exchange_issues_short_lived_scoped_jwt_and_only_hash_is_stored(device_db):
    db, admin, board = device_db
    device, secret = create_display_board_device(
        db,
        board=board,
        device_name="Synthetic waiting room TV",
        created_by=admin.id,
    )

    original_hash = device.secret_hash
    assert secret not in original_hash
    token_result = exchange_display_device_secret(
        db, device_id=device.id, secret=secret, board_name=board.name
    )
    assert token_result is not None
    token, ttl, board_name, session_token = token_result
    consumed_hash = (
        db.query(DisplayBoardDevice.secret_hash)
        .filter_by(id=device.id)
        .scalar()
    )
    claims = jwt.decode(
        token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
    )
    assert ttl == DISPLAY_DEVICE_TOKEN_TTL_SECONDS == 3600
    assert claims["typ"] == "display_device"
    assert claims["device_id"] == device.id
    assert claims["board_id"] == board.id
    assert claims["board_name"] == board.name
    assert board_name == board.name
    assert claims["exp"] - claims["iat"] == 3600
    assert claims["jti"]
    assert "secret" not in claims
    assert consumed_hash != original_hash
    assert consumed_hash and secret not in consumed_hash

    session_claims = jwt.decode(
        session_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
    )
    assert session_claims["typ"] == "display_device_session"
    assert session_claims["device_id"] == device.id
    assert session_claims["board_id"] == board.id
    assert session_claims["board_name"] == board.name
    assert session_claims["exp"] - session_claims["iat"] == DISPLAY_DEVICE_SESSION_TTL_SECONDS

    refreshed = exchange_display_device_session(
        db,
        device_id=device.id,
        board_name=board.name,
        session_token=session_token,
    )
    assert refreshed is not None
    refreshed_token, refreshed_ttl, refreshed_board_name, _renewed_session = refreshed
    assert refreshed_ttl == DISPLAY_DEVICE_TOKEN_TTL_SECONDS
    assert refreshed_board_name == board.name
    assert authenticate_display_device_token(
        db, refreshed_token, board_name=board.name
    ) is not None

    principal = authenticate_display_device_token(
        db, token, board_name=board.name, touch_connection=True
    )
    assert principal is not None
    assert principal.device_id == device.id
    assert device.last_connected_at is not None


def test_device_token_is_rejected_for_another_or_inactive_board(device_db):
    db, admin, board = device_db
    device, secret = create_display_board_device(
        db, board=board, device_name="Synthetic TV", created_by=admin.id
    )
    token, _ttl, _board_name, session_token = exchange_display_device_secret(
        db, device_id=device.id, secret=secret, board_name=board.name
    )

    assert authenticate_display_device_token(db, token, board_name="another_board") is None
    assert exchange_display_device_session(
        db,
        device_id=device.id,
        board_name=board.name,
        session_token=session_token,
    ) is not None
    assert exchange_display_device_session(
        db,
        device_id=device.id,
        board_name="another_board",
        session_token=session_token,
    ) is None
    board.active = False
    db.commit()
    assert authenticate_display_device_token(db, token, board_name=board.name) is None
    assert exchange_display_device_session(
        db,
        device_id=device.id,
        board_name=board.name,
        session_token=session_token,
    ) is None
    assert exchange_display_device_secret(
        db, device_id=device.id, secret=secret, board_name=board.name
    ) is None


def test_secret_is_bound_to_board_and_consumed_once(device_db):
    db, admin, board = device_db
    device, secret = create_display_board_device(
        db, board=board, device_name="Synthetic TV", created_by=admin.id
    )
    issued_wrong_board = exchange_display_device_secret(
        db,
        device_id=device.id,
        secret=secret,
        board_name="another_board",
    )
    assert issued_wrong_board is None
    original_hash = device.secret_hash
    assert original_hash

    issued = exchange_display_device_secret(
        db, device_id=device.id, secret=secret, board_name=board.name
    )
    assert issued is not None
    consumed_hash = (
        db.query(DisplayBoardDevice.secret_hash)
        .filter_by(id=device.id)
        .scalar()
    )
    assert consumed_hash != original_hash
    assert consumed_hash and secret not in consumed_hash
    assert exchange_display_device_secret(
        db, device_id=device.id, secret=secret, board_name=board.name
    ) is None


def test_pending_secret_exchange_is_invalidated_by_concurrent_rotation(
    device_db, monkeypatch
):
    db, admin, board = device_db
    device, secret = create_display_board_device(
        db, board=board, device_name="Synthetic TV", created_by=admin.id
    )
    session_factory = sessionmaker(
        bind=db.get_bind(), autoflush=False, expire_on_commit=False
    )
    real_commit = db.commit

    def commit_then_rotate():
        real_commit()
        rotation_db = session_factory()
        try:
            rotating_device = (
                rotation_db.query(DisplayBoardDevice)
                .filter_by(id=device.id)
                .first()
            )
            assert rotating_device is not None
            rotate_display_board_device(rotation_db, rotating_device)
        finally:
            rotation_db.close()

    monkeypatch.setattr(db, "commit", commit_then_rotate)
    issued = exchange_display_device_secret(
        db, device_id=device.id, secret=secret, board_name=board.name
    )
    assert issued is not None
    access_token, _ttl, _board_name, session_token = issued

    verify_db = session_factory()
    try:
        assert authenticate_display_device_token(
            verify_db, access_token, board_name=board.name
        ) is None
        assert exchange_display_device_session(
            verify_db,
            device_id=device.id,
            board_name=board.name,
            session_token=session_token,
        ) is None
    finally:
        verify_db.close()


def test_device_session_cookie_is_board_scoped_http_only_and_secure(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("DISPLAY_DEVICE_COOKIE_SAMESITE", "lax")
    request = Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "https",
            "path": "/api/v1/display/devices/token",
            "raw_path": b"/api/v1/display/devices/token",
            "query_string": b"",
            "headers": [(b"host", b"clinic.example")],
            "server": ("clinic.example", 443),
            "client": ("test", 1234),
        }
    )
    response = Response()

    _set_display_device_session_cookie(
        request,
        response,
        device_id=17,
        board_name="synthetic_board",
        session_token="synthetic-session-token",
    )

    cookie = response.headers["set-cookie"]
    assert cookie.startswith(
        f"{display_device_session_cookie_name(17, 'synthetic_board')}="
    )
    assert "synthetic_board" not in cookie
    assert "Path=/api/v1/display/devices/token" in cookie
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=lax" in cookie


def test_rotation_invalidates_existing_jwts_and_old_secret(device_db):
    db, admin, board = device_db
    device, old_secret = create_display_board_device(
        db, board=board, device_name="Synthetic TV", created_by=admin.id
    )
    old_token, _ttl, _board_name, old_session = exchange_display_device_secret(
        db, device_id=device.id, secret=old_secret, board_name=board.name
    )

    new_secret = rotate_display_board_device(db, device)
    assert new_secret != old_secret
    assert exchange_display_device_secret(
        db, device_id=device.id, secret=old_secret, board_name=board.name
    ) is None
    assert authenticate_display_device_token(
        db, old_token, board_name=board.name
    ) is None
    assert exchange_display_device_session(
        db,
        device_id=device.id,
        board_name=board.name,
        session_token=old_session,
    ) is None
    new_token, _ttl, _board_name, new_session = exchange_display_device_secret(
        db, device_id=device.id, secret=new_secret, board_name=board.name
    )
    assert authenticate_display_device_token(
        db, new_token, board_name=board.name
    ) is not None
    revoke_display_board_device(db, device)
    assert exchange_display_device_session(
        db,
        device_id=device.id,
        board_name=board.name,
        session_token=new_session,
    ) is None


def test_stale_concurrent_rotations_advance_credential_version(device_db):
    db, admin, board = device_db
    device, initial_secret = create_display_board_device(
        db, board=board, device_name="Synthetic TV", created_by=admin.id
    )
    stale_session_factory = sessionmaker(
        bind=db.get_bind(), autoflush=False, expire_on_commit=False
    )
    stale_session = stale_session_factory()
    try:
        stale_device = (
            stale_session.query(DisplayBoardDevice)
            .filter_by(id=device.id)
            .first()
        )
        assert stale_device is not None
        assert stale_device.credential_version == 1

        first_secret = rotate_display_board_device(db, device)
        token_from_first_rotation, _ttl, _board_name, _session = exchange_display_device_secret(
            db, device_id=device.id, secret=first_secret, board_name=board.name
        )

        second_secret = rotate_display_board_device(stale_session, stale_device)

        assert stale_device.credential_version == 3
        assert exchange_display_device_secret(
            db, device_id=device.id, secret=initial_secret, board_name=board.name
        ) is None
        assert authenticate_display_device_token(
            db, token_from_first_rotation, board_name=board.name
        ) is None
        token_from_second_rotation, _ttl, _board_name, _session = exchange_display_device_secret(
            db, device_id=device.id, secret=second_secret, board_name=board.name
        )
        assert authenticate_display_device_token(
            db, token_from_second_rotation, board_name=board.name
        ) is not None
    finally:
        stale_session.close()


def test_device_revocation_invalidates_tokens_and_secret_exchange(device_db):
    db, admin, board = device_db
    device, secret = create_display_board_device(
        db, board=board, device_name="Synthetic TV", created_by=admin.id
    )
    token, _ttl, _board_name, session_token = exchange_display_device_secret(
        db, device_id=device.id, secret=secret, board_name=board.name
    )

    revoke_display_board_device(db, device)

    assert exchange_display_device_secret(
        db, device_id=device.id, secret=secret, board_name=board.name
    ) is None
    assert authenticate_display_device_token(db, token, board_name=board.name) is None
    assert exchange_display_device_session(
        db,
        device_id=device.id,
        board_name=board.name,
        session_token=session_token,
    ) is None


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/admin/display/boards/1/devices",
        "/api/v1/admin/display/boards/1/devices/2/rotate",
        "/api/v1/display/devices/token",
    ],
)
def test_device_credential_responses_bypass_idempotency_cache(path):
    assert _is_display_device_idempotency_exempt("POST", path)


def test_other_post_responses_keep_idempotency_cache():
    assert not _is_display_device_idempotency_exempt(
        "POST", "/api/v1/admin/display/boards"
    )


def test_keyed_device_secret_issuance_is_rejected_without_caching():
    request = Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/api/v1/admin/display/boards/1/devices",
            "raw_path": b"/api/v1/admin/display/boards/1/devices",
            "query_string": b"",
            "headers": [(b"idempotency-key", b"synthetic-idem-key")],
            "server": ("test", 80),
            "client": ("test", 1234),
        }
    )
    called_next = False

    async def call_next(_request):
        nonlocal called_next
        called_next = True
        return Response(content='{"secret":"synthetic"}')

    middleware = IdempotencyMiddleware(app=lambda *_args: None)
    response = asyncio.run(middleware.dispatch(request, call_next))

    assert response.status_code == 400
    assert response.headers["Cache-Control"] == "no-store"
    assert not called_next
