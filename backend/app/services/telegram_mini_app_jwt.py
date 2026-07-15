"""
Telegram Mini App JWT Exchange Service — M4-P0-2 (Epic M4).

Issues short-lived JWT after Telegram initData verification.
This replaces the per-request initData-replay pattern with a proper
OAuth-like exchange: initData → JWT → JWT used for all subsequent requests.

Flow:
    POST /telegram/mini-app/auth/exchange { initData }
      → validate_telegram_mini_app_init_data(initData, max_age=5min, replay_check=True)
      → resolve_telegram_mini_app_session_scope(db, init_data, expected_scope="patient")
      → create_access_token({sub: patient_id, scope: "patient", ...})
      → create UserSession with refresh_token
      → return {access_token, refresh_token, expires_in}

Security improvements over per-request initData:
- initData used ONCE (replay protection via cache_manager)
- initData max_age reduced from 24h to 5min
- JWT short-lived (15 min) — even if leaked, small attack window
- Refresh token stored in UserSession (revocable)
"""
from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.authentication import UserSession
from app.services.telegram_mini_app_init_data import (
    DEFAULT_MAX_AUTH_AGE_SECONDS,
    TelegramMiniAppInitDataError,
    TelegramMiniAppSessionScope,
    TelegramMiniAppSessionScopeError,
    resolve_telegram_mini_app_session_scope,
    validate_telegram_mini_app_init_data,
)

logger = logging.getLogger(__name__)

# JWT configuration for patient Mini App tokens
PATIENT_JWT_ALGORITHM = "HS256"
PATIENT_ACCESS_TOKEN_EXPIRE_MINUTES = 15  # Short-lived: 15 minutes
PATIENT_REFRESH_TOKEN_EXPIRE_DAYS = 7  # Refresh: 7 days


class TelegramMiniAppAuthExchangeError(ValueError):
    """Raised when Mini App auth exchange fails."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def exchange_init_data_for_jwt(
    db: Session,
    init_data_payload: str,
    *,
    bot_token: str,
    request_ip: str | None = None,
    request_user_agent: str | None = None,
) -> dict[str, Any]:
    """Exchange Telegram initData for short-lived JWT + refresh token.

    M4-P0-2: This is the secure alternative to per-request initData replay.
    initData is validated ONCE with max_age=5min and replay protection,
    then a JWT is issued for subsequent requests.

    Args:
        db: SQLAlchemy session
        init_data_payload: Telegram.WebApp.initData string
        bot_token: Telegram bot token for HMAC verification
        request_ip: Client IP (for UserSession audit)
        request_user_agent: Client User-Agent (for UserSession audit)

    Returns:
        Dict with: access_token, refresh_token, token_type, expires_in,
        patient_id, telegram_user_id

    Raises:
        TelegramMiniAppAuthExchangeError: if validation or scope resolution fails
    """
    # Step 1: Validate initData with SECURE defaults (5min + replay protection)
    try:
        init_data = validate_telegram_mini_app_init_data(
            init_data_payload,
            bot_token=bot_token,
            max_age_seconds=DEFAULT_MAX_AUTH_AGE_SECONDS,  # 5 minutes
            replay_check=True,  # One-time use
        )
    except TelegramMiniAppInitDataError as exc:
        logger.warning(
            "Mini App auth exchange failed (init_data validation): %s",
            exc.reason,
        )
        raise TelegramMiniAppAuthExchangeError(exc.reason) from exc

    # Step 2: Resolve patient scope
    try:
        scope = resolve_telegram_mini_app_session_scope(
            db,
            init_data,
            expected_scope="patient",
        )
    except TelegramMiniAppSessionScopeError as exc:
        logger.warning(
            "Mini App auth exchange failed (scope resolution): %s",
            exc.reason,
        )
        raise TelegramMiniAppAuthExchangeError(exc.reason) from exc

    # Step 3: Create JWT access token
    now = datetime.now(UTC)
    access_token_expires = timedelta(minutes=PATIENT_ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token_jti = str(uuid.uuid4())

    access_token_payload = {
        "sub": str(scope.patient_id),
        "scope": "patient",
        "telegram_user_id": scope.telegram_user_id,
        "type": "access",
        "jti": access_token_jti,
        "iat": now,
        "exp": now + access_token_expires,
    }

    access_token = jwt.encode(
        access_token_payload,
        settings.SECRET_KEY,
        algorithm=PATIENT_JWT_ALGORITHM,
    )

    # Step 4: Create refresh token + UserSession
    refresh_token_jti = str(uuid.uuid4())
    refresh_token_expires = timedelta(days=PATIENT_REFRESH_TOKEN_EXPIRE_DAYS)

    refresh_token_payload = {
        "sub": str(scope.patient_id),
        "scope": "patient",
        "telegram_user_id": scope.telegram_user_id,
        "type": "refresh",
        "jti": refresh_token_jti,
        "iat": now,
        "exp": now + refresh_token_expires,
    }

    refresh_token = jwt.encode(
        refresh_token_payload,
        settings.SECRET_KEY,
        algorithm=PATIENT_JWT_ALGORITHM,
    )

    # Step 5: Store UserSession for revocation capability
    user_session = UserSession(
        # user_id is required by model — use patient_id as a placeholder.
        # In a future migration, we may add patient_sessions table.
        # For now, we store the session with a negative user_id to distinguish
        # patient sessions from staff sessions.
        # NOTE: This is a temporary approach until patient-specific session
        # table is created (M4-P1-3 context roles).
        user_id=-(scope.patient_id or 0),  # Negative = patient session
        refresh_token=refresh_token,
        expires_at=now + refresh_token_expires,
        ip=request_ip,
        user_agent=request_user_agent,
    )
    db.add(user_session)
    db.commit()

    # M4-P0-2: Do NOT log patient_id or telegram_user_id here —
    # CodeQL flags this as clear-text logging of sensitive information.
    # The audit trail (PatientAccessAuditLog) captures this in the DB.
    logger.info("Mini App auth exchange successful")

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": int(access_token_expires.total_seconds()),
        "patient_id": scope.patient_id,
        "telegram_user_id": scope.telegram_user_id,
    }


def verify_patient_jwt(token: str) -> dict[str, Any] | None:
    """Verify a patient JWT access token.

    M4-P0-2: Used by patient endpoints to verify Authorization: Bearer <JWT>.

    Args:
        token: JWT access token string

    Returns:
        Payload dict if valid, None if invalid/expired.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[PATIENT_JWT_ALGORITHM],
        )
        if payload.get("type") != "access":
            return None
        if payload.get("scope") != "patient":
            return None
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Patient JWT expired")
        return None
    except jwt.InvalidTokenError:
        logger.warning("Invalid patient JWT")
        return None
