"""Device credential tests use synthetic records and an in-memory database."""

from __future__ import annotations

import asyncio

import jwt
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

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
    DISPLAY_DEVICE_TOKEN_TTL_SECONDS,
    authenticate_display_device_token,
    create_display_board_device,
    exchange_display_device_secret,
    revoke_display_board_device,
    rotate_display_board_device,
)
from starlette.requests import Request
from starlette.responses import Response


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

    assert secret not in device.secret_hash
    assert device.secret_hash != secret
    token_result = exchange_display_device_secret(
        db, device_id=device.id, secret=secret
    )
    assert token_result is not None
    token, ttl, board_name = token_result
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
    token, _ttl, _board_name = exchange_display_device_secret(
        db, device_id=device.id, secret=secret
    )

    assert authenticate_display_device_token(db, token, board_name="another_board") is None
    board.active = False
    db.commit()
    assert authenticate_display_device_token(db, token, board_name=board.name) is None
    assert exchange_display_device_secret(db, device_id=device.id, secret=secret) is None


def test_rotation_invalidates_existing_jwts_and_old_secret(device_db):
    db, admin, board = device_db
    device, old_secret = create_display_board_device(
        db, board=board, device_name="Synthetic TV", created_by=admin.id
    )
    old_token, _ttl, _board_name = exchange_display_device_secret(
        db, device_id=device.id, secret=old_secret
    )

    new_secret = rotate_display_board_device(db, device)
    assert new_secret != old_secret
    assert exchange_display_device_secret(
        db, device_id=device.id, secret=old_secret
    ) is None
    assert authenticate_display_device_token(
        db, old_token, board_name=board.name
    ) is None
    new_token, _ttl, _board_name = exchange_display_device_secret(
        db, device_id=device.id, secret=new_secret
    )
    assert authenticate_display_device_token(
        db, new_token, board_name=board.name
    ) is not None


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
        token_from_first_rotation, _ttl, _board_name = exchange_display_device_secret(
            db, device_id=device.id, secret=first_secret
        )

        second_secret = rotate_display_board_device(stale_session, stale_device)

        assert stale_device.credential_version == 3
        assert exchange_display_device_secret(
            db, device_id=device.id, secret=initial_secret
        ) is None
        assert authenticate_display_device_token(
            db, token_from_first_rotation, board_name=board.name
        ) is None
        token_from_second_rotation, _ttl, _board_name = exchange_display_device_secret(
            db, device_id=device.id, secret=second_secret
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
    token, _ttl, _board_name = exchange_display_device_secret(
        db, device_id=device.id, secret=secret
    )

    revoke_display_board_device(db, device)

    assert exchange_display_device_secret(db, device_id=device.id, secret=secret) is None
    assert authenticate_display_device_token(db, token, board_name=board.name) is None


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
