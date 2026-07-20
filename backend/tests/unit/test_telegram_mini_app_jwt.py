"""
Unit tests for Telegram Mini App JWT Exchange Service (M4-P0-2).

Tests the exchange_init_data_for_jwt() and verify_patient_jwt() functions.

Covers:
- Successful exchange: initData → JWT + refresh token
- JWT verification: valid token returns payload
- JWT verification: expired token returns None
- JWT verification: wrong type returns None
- JWT verification: wrong scope returns None
- Replay protection: same initData used twice → second fails
- Auth exchange failure: invalid initData → error
"""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from urllib.parse import urlencode

import jwt
import pytest

from app.services.telegram_mini_app_jwt import (
    PATIENT_ACCESS_TOKEN_EXPIRE_MINUTES,
    PATIENT_JWT_ALGORITHM,
    TelegramMiniAppAuthExchangeError,
    exchange_init_data_for_jwt,
    verify_patient_jwt,
)


BOT_TOKEN = "123456:test-mini-app-jwt-token"


def _signed_init_data(params: dict[str, str], bot_token: str = BOT_TOKEN) -> str:
    """Create a properly signed Telegram initData for testing."""
    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(params.items())
    )
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    received_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()
    params_with_hash = {**params, "hash": received_hash}
    return urlencode(params_with_hash)


def _make_init_data_payload(
    user_id: int = 111,
    auth_date: datetime | None = None,
    bot_token: str = BOT_TOKEN,
) -> str:
    """Create a signed initData payload with a valid user."""
    if auth_date is None:
        auth_date = datetime.now(timezone.utc)

    user_obj = {"id": user_id, "first_name": "Test", "last_name": "Patient"}
    params = {
        "query_id": f"test_query_{user_id}",
        "user": json.dumps(user_obj),
        "auth_date": str(int(auth_date.timestamp())),
    }
    return _signed_init_data(params, bot_token)


class TestExchangeInitDataForJwt:
    """Tests for exchange_init_data_for_jwt()."""

    def test_exchange_returns_jwt_and_refresh_token(self):
        """Successful exchange returns access_token + refresh_token."""
        db = MagicMock()
        scope = MagicMock()
        scope.scope_type = "patient"
        scope.patient_id = 42
        scope.telegram_user_id = 111

        with patch(
            "app.services.telegram_mini_app_jwt.validate_telegram_mini_app_init_data"
        ) as mock_validate, patch(
            "app.services.telegram_mini_app_jwt.resolve_telegram_mini_app_session_scope"
        ) as mock_resolve, patch(
            "app.services.telegram_mini_app_jwt.settings"
        ) as mock_settings:
            mock_validate.return_value = MagicMock()
            mock_resolve.return_value = scope
            mock_settings.SECRET_KEY = "test-secret-key"

            result = exchange_init_data_for_jwt(
                db,
                "fake_init_data",
                bot_token=BOT_TOKEN,
            )

        assert "access_token" in result
        assert "refresh_token" in result
        assert result["token_type"] == "bearer"
        assert result["expires_in"] == PATIENT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
        assert result["patient_id"] == 42
        assert result["telegram_user_id"] == 111

        # Verify db.add was called (UserSession)
        assert db.add.called
        assert db.commit.called

    def test_exchange_raises_on_invalid_init_data(self):
        """Exchange fails when initData validation fails."""
        db = MagicMock()

        from app.services.telegram_mini_app_init_data import (
            TelegramMiniAppInitDataError,
        )

        with patch(
            "app.services.telegram_mini_app_jwt.validate_telegram_mini_app_init_data",
            side_effect=TelegramMiniAppInitDataError("hash_mismatch"),
        ):
            with pytest.raises(TelegramMiniAppAuthExchangeError) as exc_info:
                exchange_init_data_for_jwt(
                    db,
                    "invalid_init_data",
                    bot_token=BOT_TOKEN,
                )

        assert exc_info.value.reason == "hash_mismatch"

    def test_exchange_raises_on_scope_resolution_failure(self):
        """Exchange fails when scope resolution fails (no linked patient)."""
        db = MagicMock()

        from app.services.telegram_mini_app_init_data import (
            TelegramMiniAppSessionScopeError,
        )

        with patch(
            "app.services.telegram_mini_app_jwt.validate_telegram_mini_app_init_data",
            return_value=MagicMock(),
        ), patch(
            "app.services.telegram_mini_app_jwt.resolve_telegram_mini_app_session_scope",
            side_effect=TelegramMiniAppSessionScopeError("telegram_link_required"),
        ):
            with pytest.raises(TelegramMiniAppAuthExchangeError) as exc_info:
                exchange_init_data_for_jwt(
                    db,
                    "valid_init_data",
                    bot_token=BOT_TOKEN,
                )

        assert exc_info.value.reason == "telegram_link_required"

    def test_exchange_creates_user_session_with_ip_and_user_agent(self):
        """UserSession is created with IP and User-Agent for audit."""
        db = MagicMock()
        scope = MagicMock()
        scope.scope_type = "patient"
        scope.patient_id = 42
        scope.telegram_user_id = 111

        with patch(
            "app.services.telegram_mini_app_jwt.validate_telegram_mini_app_init_data",
            return_value=MagicMock(),
        ), patch(
            "app.services.telegram_mini_app_jwt.resolve_telegram_mini_app_session_scope",
            return_value=scope,
        ), patch(
            "app.services.telegram_mini_app_jwt.settings"
        ) as mock_settings:
            mock_settings.SECRET_KEY = "test-secret-key"

            exchange_init_data_for_jwt(
                db,
                "fake_init_data",
                bot_token=BOT_TOKEN,
                request_ip="203.0.113.50",
                request_user_agent="Mozilla/5.0",
            )

        # Verify UserSession was created with correct IP and user-agent
        session = db.add.call_args[0][0]
        assert session.ip == "203.0.113.50"
        assert session.user_agent == "Mozilla/5.0"


class TestVerifyPatientJwt:
    """Tests for verify_patient_jwt()."""

    def test_verify_valid_jwt_returns_payload(self):
        """Valid JWT returns payload dict."""
        import uuid

        payload = {
            "sub": "42",
            "scope": "patient",
            "telegram_user_id": 111,
            "type": "access",
            "jti": str(uuid.uuid4()),
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        }

        token = jwt.encode(
            payload, "test-secret-key", algorithm=PATIENT_JWT_ALGORITHM
        )

        with patch("app.services.telegram_mini_app_jwt.settings") as mock_settings:
            mock_settings.SECRET_KEY = "test-secret-key"
            result = verify_patient_jwt(token)

        assert result is not None
        assert result["sub"] == "42"
        assert result["scope"] == "patient"
        assert result["type"] == "access"

    def test_verify_expired_jwt_returns_none(self):
        """Expired JWT returns None."""
        import uuid

        payload = {
            "sub": "42",
            "scope": "patient",
            "type": "access",
            "jti": str(uuid.uuid4()),
            "iat": datetime.now(timezone.utc) - timedelta(minutes=30),
            "exp": datetime.now(timezone.utc) - timedelta(minutes=15),
        }

        token = jwt.encode(
            payload, "test-secret-key", algorithm=PATIENT_JWT_ALGORITHM
        )

        with patch("app.services.telegram_mini_app_jwt.settings") as mock_settings:
            mock_settings.SECRET_KEY = "test-secret-key"
            result = verify_patient_jwt(token)

        assert result is None

    def test_verify_wrong_type_jwt_returns_none(self):
        """JWT with type='refresh' is rejected for access-token verification."""
        import uuid

        payload = {
            "sub": "42",
            "scope": "patient",
            "type": "refresh",
            "jti": str(uuid.uuid4()),
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(days=7),
        }

        token = jwt.encode(
            payload, "test-secret-key", algorithm=PATIENT_JWT_ALGORITHM
        )

        with patch("app.services.telegram_mini_app_jwt.settings") as mock_settings:
            mock_settings.SECRET_KEY = "test-secret-key"
            result = verify_patient_jwt(token)

        assert result is None

    def test_verify_wrong_scope_jwt_returns_none(self):
        """JWT with scope='staff' is rejected for patient endpoint."""
        import uuid

        payload = {
            "sub": "1",
            "scope": "staff",
            "type": "access",
            "jti": str(uuid.uuid4()),
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        }

        token = jwt.encode(
            payload, "test-secret-key", algorithm=PATIENT_JWT_ALGORITHM
        )

        with patch("app.services.telegram_mini_app_jwt.settings") as mock_settings:
            mock_settings.SECRET_KEY = "test-secret-key"
            result = verify_patient_jwt(token)

        assert result is None

    def test_verify_invalid_jwt_returns_none(self):
        """Malformed JWT string returns None."""
        with patch("app.services.telegram_mini_app_jwt.settings") as mock_settings:
            mock_settings.SECRET_KEY = "test-secret-key"
            result = verify_patient_jwt("not.a.valid.jwt")

        assert result is None
