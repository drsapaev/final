"""Revocable patient-only Telegram JWT sessions with rotating refresh secrets."""

from __future__ import annotations

import hashlib
import hmac
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qsl

import jwt
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.telegram_mini_app_session import TelegramMiniAppSession
from app.repositories.telegram_mini_app_session_repository import (
    TelegramMiniAppSessionRepository,
)
from app.services.telegram_mini_app_init_data import (
    DEFAULT_MAX_AUTH_AGE_SECONDS,
    TelegramMiniAppInitDataError,
    TelegramMiniAppSessionScope,
    TelegramMiniAppSessionScopeError,
    resolve_telegram_mini_app_session_scope,
    validate_telegram_mini_app_init_data,
)

PATIENT_JWT_ALGORITHM = "HS256"
PATIENT_JWT_AUDIENCE = "telegram-mini-app-patient"
PATIENT_JWT_ISSUER = "clinic-telegram-mini-app"
PATIENT_ACCESS_TOKEN_EXPIRE_MINUTES = 15
PATIENT_REFRESH_TOKEN_EXPIRE_DAYS = 7


class TelegramMiniAppAuthExchangeError(ValueError):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class TelegramMiniAppPatientAuth:
    session: TelegramMiniAppSession
    scope: TelegramMiniAppSessionScope


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _device_label(user_agent: str | None) -> str:
    # Only coarse allowlisted labels reach the UI; never echo raw headers.
    ua = (user_agent or "").lower()
    for fragment, label in (
        ("android", "Android"),
        ("iphone", "iPhone"),
        ("ipad", "iPad"),
        ("windows", "Windows"),
        ("macintosh", "macOS"),
        ("linux", "Linux"),
    ):
        if fragment in ua:
            return label
    return "Telegram"


def _encode_token(
    row: TelegramMiniAppSession,
    token_type: str,
    now: datetime,
    expiry: datetime,
) -> str:
    return jwt.encode(
        {
            # Namespaced subject and audience isolate staff authentication.
            "sub": f"telegram-patient:{row.patient_id}",
            "sid": row.id,
            "scope": "patient",
            "type": token_type,
            "jti": str(uuid.uuid4()),
            "iat": now,
            "exp": expiry,
            "iss": PATIENT_JWT_ISSUER,
            "aud": PATIENT_JWT_AUDIENCE,
        },
        settings.SECRET_KEY,
        algorithm=PATIENT_JWT_ALGORITHM,
    )


def _new_refresh_token(row: TelegramMiniAppSession) -> str:
    return _encode_token(row, "refresh", datetime.now(UTC), _utc(row.expires_at))


def _token_pair(row: TelegramMiniAppSession, refresh_token: str) -> dict[str, Any]:
    now = datetime.now(UTC)
    expiry = min(
        now + timedelta(minutes=PATIENT_ACCESS_TOKEN_EXPIRE_MINUTES),
        _utc(row.expires_at),
    )
    access_token = _encode_token(row, "access", now, expiry)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": max(0, int((expiry - now).total_seconds())),
    }


def exchange_init_data_for_jwt(
    db: Session,
    init_data_payload: str,
    *,
    bot_token: str,
    request_user_agent: str | None = None,
) -> dict[str, Any]:
    if not init_data_payload or len(init_data_payload) > 16384:
        raise TelegramMiniAppAuthExchangeError("init_data_invalid")
    try:
        # UNIQUE signed-initData digest consumes exchange atomically with the
        # session. Cache get/set cannot provide this cross-worker guarantee.
        init_data = validate_telegram_mini_app_init_data(
            init_data_payload,
            bot_token=bot_token,
            max_age_seconds=DEFAULT_MAX_AUTH_AGE_SECONDS,
            replay_check=False,
        )
        scope = resolve_telegram_mini_app_session_scope(
            db,
            init_data,
            expected_scope="patient",
        )
    except (TelegramMiniAppInitDataError, TelegramMiniAppSessionScopeError) as exc:
        raise TelegramMiniAppAuthExchangeError(exc.reason) from exc

    repo = TelegramMiniAppSessionRepository(db)
    repo.lock_patient(scope.patient_id)
    patient_link_epoch = repo.lock_patient_link_epoch(
        telegram_user_id=scope.telegram_user_id,
        patient_id=scope.patient_id,
        chat_id=scope.telegram_chat_id,
    )
    if patient_link_epoch is None:
        raise TelegramMiniAppAuthExchangeError("patient_link_invalid")

    now = datetime.now(UTC)
    session_id = str(uuid.uuid4())
    row = TelegramMiniAppSession(
        id=session_id,
        patient_id=scope.patient_id,
        telegram_user_id=scope.telegram_user_id,
        patient_link_epoch=patient_link_epoch,
        init_data_hash=_digest(dict(parse_qsl(init_data_payload))["hash"]),
        refresh_token_hash="",
        device_label=_device_label(request_user_agent),
        created_at=now,
        last_active_at=now,
        expires_at=now + timedelta(days=PATIENT_REFRESH_TOKEN_EXPIRE_DAYS),
    )
    refresh_token = _new_refresh_token(row)
    row.refresh_token_hash = _digest(refresh_token)
    repo.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise TelegramMiniAppAuthExchangeError("init_data_replayed") from exc
    return _token_pair(row, refresh_token)


def init_data_already_exchanged(db: Session, init_data_payload: str) -> bool:
    """Consumed patient launch credentials cannot bypass session revocation."""
    signature = dict(parse_qsl(init_data_payload)).get("hash", "")
    return bool(signature) and TelegramMiniAppSessionRepository(db).init_data_exchanged(
        _digest(signature),
    )


def _decode_token(token: str, token_type: str) -> dict[str, Any]:
    try:
        if not token or len(token) > 4096:
            raise ValueError
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[PATIENT_JWT_ALGORITHM],
            audience=PATIENT_JWT_AUDIENCE,
            issuer=PATIENT_JWT_ISSUER,
            options={
                "require": ["exp", "iat", "sub", "aud", "iss", "jti", "sid"],
            },
        )
        if payload.get("type") != token_type or payload.get("scope") != "patient":
            raise ValueError
        uuid.UUID(payload["sid"])
        if not payload.get("jti"):
            raise ValueError
        return payload
    except (jwt.InvalidTokenError, ValueError, KeyError, TypeError) as exc:
        raise TelegramMiniAppAuthExchangeError("session_invalid") from exc


def authenticate_patient_session(
    db: Session,
    token: str,
    *,
    lock: bool = False,
) -> TelegramMiniAppPatientAuth:
    payload = _decode_token(token, "access")
    repo = TelegramMiniAppSessionRepository(db)
    if lock:
        existing = repo.get(payload["sid"])
        if existing is None:
            raise TelegramMiniAppAuthExchangeError("session_invalid")
        repo.lock_patient(existing.patient_id)
    context = repo.active_context(payload["sid"], datetime.now(UTC))
    if context is None:
        raise TelegramMiniAppAuthExchangeError("session_invalid")
    row, chat_id = context
    if payload["sub"] != f"telegram-patient:{row.patient_id}":
        raise TelegramMiniAppAuthExchangeError("session_invalid")
    return TelegramMiniAppPatientAuth(
        row,
        TelegramMiniAppSessionScope(
            scope_type="patient",
            patient_id=row.patient_id,
            telegram_user_id=row.telegram_user_id,
            telegram_chat_id=chat_id,
        ),
    )


def verify_patient_jwt(token: str, db: Session) -> dict[str, Any] | None:
    """Signature, server session, current account link and patient must be valid."""
    try:
        authenticate_patient_session(db, token)
        return _decode_token(token, "access")
    except TelegramMiniAppAuthExchangeError:
        return None


def refresh_patient_session(db: Session, refresh_token: str) -> dict[str, Any]:
    # Verify signature before a mismatch can invalidate a session family.
    # Otherwise knowledge of a public session id would allow a logout DoS.
    payload = _decode_token(refresh_token, "refresh")
    session_id = payload["sid"]
    repo = TelegramMiniAppSessionRepository(db)
    existing = repo.get(session_id)
    if existing is None:
        raise TelegramMiniAppAuthExchangeError("session_invalid")
    repo.lock_patient(existing.patient_id)
    now = datetime.now(UTC)
    context = repo.active_context(session_id, now)
    if context is None:
        raise TelegramMiniAppAuthExchangeError("session_invalid")
    row, _chat_id = context
    if payload["sub"] != f"telegram-patient:{row.patient_id}":
        raise TelegramMiniAppAuthExchangeError("session_invalid")
    if not hmac.compare_digest(row.refresh_token_hash, _digest(refresh_token)):
        # Reuse of a rotated secret invalidates the whole session family.
        row.revoked_at = now
        db.commit()
        raise TelegramMiniAppAuthExchangeError("session_invalid")
    rotated = _new_refresh_token(row)
    row.refresh_token_hash = _digest(rotated)
    row.last_active_at = now
    db.commit()
    return _token_pair(row, rotated)


def list_patient_sessions(
    db: Session, token: str
) -> tuple[TelegramMiniAppPatientAuth, dict]:
    auth = authenticate_patient_session(db, token)
    rows = TelegramMiniAppSessionRepository(db).list_active(
        auth.session.patient_id,
        datetime.now(UTC),
    )
    return auth, {
        "sessions": [
            {
                "id": row.id,
                "device_label": row.device_label,
                "created_at": row.created_at,
                "last_active_at": row.last_active_at,
                "expires_at": row.expires_at,
                "is_current": row.id == auth.session.id,
            }
            for row in rows
        ],
        "total": len(rows),
    }


def revoke_patient_sessions(
    db: Session,
    token: str,
    *,
    target_id: str | None = None,
    logout: bool = False,
) -> tuple[TelegramMiniAppPatientAuth, int]:
    auth = authenticate_patient_session(db, token, lock=True)
    repo = TelegramMiniAppSessionRepository(db)
    now = datetime.now(UTC)
    if target_id is not None or logout:
        target = repo.get(auth.session.id if logout else target_id)
        if target is None or target.patient_id != auth.session.patient_id:
            raise TelegramMiniAppAuthExchangeError("session_not_found")
        if target.id == auth.session.id and not logout:
            raise TelegramMiniAppAuthExchangeError("current_session_requires_logout")
        count = int(target.revoked_at is None)
        target.revoked_at = target.revoked_at or now
    else:
        count = repo.revoke_others(auth.session.patient_id, auth.session.id, now)
    db.commit()
    return auth, count
