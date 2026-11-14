"""Provision and validate revocable board-scoped display credentials."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from jwt import PyJWTError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.models.display_config import DisplayBoard, DisplayBoardDevice
from app.services.token_blacklist_service import TokenBlacklistService

DISPLAY_DEVICE_TOKEN_TYPE = "display_device"
DISPLAY_DEVICE_TOKEN_TTL_SECONDS = 60 * 60
DISPLAY_DEVICE_SESSION_TYPE = "display_device_session"
DISPLAY_DEVICE_SESSION_TTL_SECONDS = 30 * 24 * 60 * 60
DISPLAY_DEVICE_SESSION_COOKIE_PREFIX = "clinic_display_device_session_"
DISPLAY_DEVICE_ACTIVE = "active"
DISPLAY_DEVICE_REVOKED = "revoked"


@dataclass(frozen=True)
class DisplayDevicePrincipal:
    device_id: int
    board_id: int
    board_name: str
    device_name: str
    credential_version: int


def _new_device_secret() -> str:
    return secrets.token_urlsafe(32)


def create_display_board_device(
    db: Session, *, board: DisplayBoard, device_name: str, created_by: int
) -> tuple[DisplayBoardDevice, str]:
    secret = _new_device_secret()
    device = DisplayBoardDevice(
        board_id=board.id,
        device_name=device_name.strip(),
        secret_hash=get_password_hash(secret),
        status=DISPLAY_DEVICE_ACTIVE,
        credential_version=1,
        created_by=created_by,
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return device, secret


def rotate_display_board_device(
    db: Session, device: DisplayBoardDevice
) -> str:
    secret = _new_device_secret()
    # Increment in SQL rather than from the ORM object's possibly stale
    # version. Two overlapping rotations may both have loaded version N;
    # an atomic N+1 expression ensures a token issued between them is
    # invalidated by the later rotation as well.
    updated = (
        db.query(DisplayBoardDevice)
        .filter(DisplayBoardDevice.id == device.id)
        .update(
            {
                DisplayBoardDevice.secret_hash: get_password_hash(secret),
                DisplayBoardDevice.credential_version: (
                    DisplayBoardDevice.credential_version + 1
                ),
                DisplayBoardDevice.status: DISPLAY_DEVICE_ACTIVE,
                DisplayBoardDevice.rotated_at: datetime.now(UTC),
            },
            synchronize_session=False,
        )
    )
    if updated != 1:
        db.rollback()
        raise ValueError("Display device no longer exists")
    db.refresh(device)
    db.commit()
    return secret


def revoke_display_board_device(db: Session, device: DisplayBoardDevice) -> None:
    updated = (
        db.query(DisplayBoardDevice)
        .filter(DisplayBoardDevice.id == device.id)
        .update(
            {
                DisplayBoardDevice.status: DISPLAY_DEVICE_REVOKED,
                DisplayBoardDevice.credential_version: (
                    DisplayBoardDevice.credential_version + 1
                ),
            },
            synchronize_session=False,
        )
    )
    if updated != 1:
        db.rollback()
        raise ValueError("Display device no longer exists")
    db.refresh(device)
    db.commit()


def _issue_display_device_token(device: DisplayBoardDevice, board: DisplayBoard) -> str:
    now = datetime.now(UTC)
    payload = {
        "typ": DISPLAY_DEVICE_TOKEN_TYPE,
        "token_type": DISPLAY_DEVICE_TOKEN_TYPE,
        "device_id": device.id,
        "board_id": board.id,
        "board_name": board.name,
        "credential_version": device.credential_version,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + timedelta(seconds=DISPLAY_DEVICE_TOKEN_TTL_SECONDS),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _issue_display_device_session_token(
    device: DisplayBoardDevice, board: DisplayBoard
) -> str:
    now = datetime.now(UTC)
    payload = {
        "typ": DISPLAY_DEVICE_SESSION_TYPE,
        "device_id": device.id,
        "board_id": board.id,
        "board_name": board.name,
        "credential_version": device.credential_version,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + timedelta(seconds=DISPLAY_DEVICE_SESSION_TTL_SECONDS),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def display_device_session_cookie_prefix(board_name: str) -> str:
    board_digest = hashlib.sha256(board_name.encode("utf-8")).hexdigest()
    return f"{DISPLAY_DEVICE_SESSION_COOKIE_PREFIX}{board_digest}_"


def display_device_session_cookie_name(device_id: int, board_name: str) -> str:
    return f"{display_device_session_cookie_prefix(board_name)}{device_id}"


def exchange_display_device_secret(
    db: Session, *, device_id: int, secret: str, board_name: str
) -> tuple[str, int, str, str] | None:
    device = db.query(DisplayBoardDevice).filter_by(id=device_id).first()
    if device is None or device.status != DISPLAY_DEVICE_ACTIVE:
        return None
    board = db.query(DisplayBoard).filter_by(id=device.board_id).first()
    if board is None or not board.active or board.name != board_name:
        return None
    secret_hash = device.secret_hash
    if not secret_hash or not verify_password(secret, secret_hash):
        return None

    # Mint with the pre-consumption version. If rotation races the commit,
    # the returned grants remain on the old version and are rejected.
    board_name = board.name
    access_token = _issue_display_device_token(device, board)
    session_token = _issue_display_device_session_token(device, board)
    consumed_secret_hash = get_password_hash(_new_device_secret())

    # The provisioning code is single-use. Compare-and-replace the verifier so
    # concurrent exchanges cannot both mint a persistent device session.
    consumed = (
        db.query(DisplayBoardDevice)
        .filter(
            DisplayBoardDevice.id == device_id,
            DisplayBoardDevice.status == DISPLAY_DEVICE_ACTIVE,
            DisplayBoardDevice.secret_hash == secret_hash,
        )
        .update(
            {DisplayBoardDevice.secret_hash: consumed_secret_hash},
            synchronize_session=False,
        )
    )
    if consumed != 1:
        db.rollback()
        return None
    db.commit()

    return (
        access_token,
        DISPLAY_DEVICE_TOKEN_TTL_SECONDS,
        board_name,
        session_token,
    )


def exchange_display_device_session(
    db: Session,
    *,
    device_id: int,
    board_name: str,
    session_token: str,
) -> tuple[str, int, str, str] | None:
    try:
        payload = jwt.decode(
            session_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
    except PyJWTError:
        return None

    token_device_id = payload.get("device_id")
    board_id = payload.get("board_id")
    credential_version = payload.get("credential_version")
    if (
        payload.get("typ") != DISPLAY_DEVICE_SESSION_TYPE
        or not isinstance(token_device_id, int)
        or isinstance(token_device_id, bool)
        or token_device_id != device_id
        or not isinstance(board_id, int)
        or isinstance(board_id, bool)
        or not isinstance(credential_version, int)
        or isinstance(credential_version, bool)
        or payload.get("board_name") != board_name
    ):
        return None

    row = (
        db.query(DisplayBoardDevice, DisplayBoard)
        .join(DisplayBoard, DisplayBoard.id == DisplayBoardDevice.board_id)
        .filter(
            DisplayBoardDevice.id == device_id,
            DisplayBoard.name == board_name,
        )
        .populate_existing()
        .first()
    )
    if row is None:
        return None
    device, board = row

    if (
        not board.active
        or board.id != board_id
        or device.status != DISPLAY_DEVICE_ACTIVE
        or device.credential_version != credential_version
    ):
        return None

    return (
        _issue_display_device_token(device, board),
        DISPLAY_DEVICE_TOKEN_TTL_SECONDS,
        board.name,
        _issue_display_device_session_token(device, board),
    )


def authenticate_display_device_token(
    db: Session,
    token: str | None,
    *,
    board_name: str,
    touch_connection: bool = False,
) -> DisplayDevicePrincipal | None:
    if not token:
        return None
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
    except PyJWTError:
        return None

    if payload.get("typ") != DISPLAY_DEVICE_TOKEN_TYPE:
        return None
    device_id = payload.get("device_id")
    board_id = payload.get("board_id")
    credential_version = payload.get("credential_version")
    jti = payload.get("jti")
    if (
        not isinstance(device_id, int)
        or isinstance(device_id, bool)
        or not isinstance(board_id, int)
        or isinstance(board_id, bool)
        or not isinstance(credential_version, int)
        or isinstance(credential_version, bool)
        or not isinstance(jti, str)
        or not jti
    ):
        return None

    row = (
        db.query(DisplayBoardDevice, DisplayBoard)
        .join(DisplayBoard, DisplayBoard.id == DisplayBoardDevice.board_id)
        .filter(
            DisplayBoardDevice.id == device_id,
            DisplayBoardDevice.board_id == board_id,
        )
        .populate_existing()
        .first()
    )
    if row is None:
        return None
    device, board = row
    if (
        not board.active
        or board.name != board_name
        or payload.get("board_name") != board.name
        or device.status != DISPLAY_DEVICE_ACTIVE
        or device.credential_version != credential_version
        or TokenBlacklistService.is_token_blacklisted(db, jti)
    ):
        return None

    if touch_connection:
        device.last_connected_at = datetime.now(UTC)
        db.add(device)
        db.commit()

    return DisplayDevicePrincipal(
        device_id=device.id,
        board_id=board.id,
        board_name=board.name,
        device_name=device.device_name,
        credential_version=device.credential_version,
    )
