"""
Unit tests for WebAuthn/Passkey Service (M4-P1-4).

Tests the graceful fallback when webauthn library is not installed,
and the passkey management functions (list, deactivate).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestWebAuthnAvailability:
    """Tests for WebAuthn library availability check."""

    def test_is_webauthn_available_returns_bool(self):
        """is_webauthn_available returns a boolean."""
        from app.services.webauthn_service import is_webauthn_available
        result = is_webauthn_available()
        assert isinstance(result, bool)

    def test_webauthn_not_available_in_cloud_env(self):
        """In cloud dev env, webauthn library is not installed."""
        from app.services.webauthn_service import is_webauthn_available
        # In this environment, webauthn is not installed
        assert is_webauthn_available() is False


class TestPasskeyManagement:
    """Tests for passkey list/deactivate (no webauthn library needed)."""

    def test_list_patient_passkeys_returns_empty_list(self):
        """Returns empty list when patient has no passkeys."""
        from app.services.webauthn_service import list_patient_passkeys

        db = MagicMock()
        query = MagicMock()
        query.filter.return_value.order_by.return_value.all.return_value = []
        db.query.return_value = query

        result = list_patient_passkeys(db, patient_id=42)
        assert result == []

    def test_list_patient_passkeys_returns_active_only(self):
        """Returns only active passkeys."""
        from app.services.webauthn_service import list_patient_passkeys

        db = MagicMock()
        mock_passkey = MagicMock()
        mock_passkey.id = 1
        mock_passkey.name = "iPhone 15"
        mock_passkey.active = True

        query = MagicMock()
        query.filter.return_value.order_by.return_value.all.return_value = [mock_passkey]
        db.query.return_value = query

        result = list_patient_passkeys(db, patient_id=42)
        assert len(result) == 1
        assert result[0].name == "iPhone 15"

    def test_deactivate_passkey_returns_true_on_success(self):
        """Deactivate returns True when passkey exists."""
        from app.services.webauthn_service import deactivate_passkey

        db = MagicMock()
        mock_passkey = MagicMock()
        mock_passkey.id = 1
        mock_passkey.patient_id = 42
        mock_passkey.active = True

        query = MagicMock()
        query.filter.return_value.first.return_value = mock_passkey
        db.query.return_value = query

        result = deactivate_passkey(db, patient_id=42, credential_id=1)
        assert result is True
        assert mock_passkey.active is False
        assert db.commit.called

    def test_deactivate_passkey_returns_false_when_not_found(self):
        """Deactivate returns False when passkey doesn't exist."""
        from app.services.webauthn_service import deactivate_passkey

        db = MagicMock()
        query = MagicMock()
        query.filter.return_value.first.return_value = None
        db.query.return_value = query

        result = deactivate_passkey(db, patient_id=42, credential_id=999)
        assert result is False


class TestPasskeyCredentialModel:
    """Tests for PasskeyCredential model."""

    def test_model_has_expected_fields(self):
        """PasskeyCredential model has expected attributes."""
        from app.models.passkey_credential import PasskeyCredential

        # Check table name
        assert PasskeyCredential.__tablename__ == "passkey_credentials"

        # Check key columns exist in mapping
        mapper = PasskeyCredential.__mapper__
        column_keys = set(mapper.columns.keys())
        expected = {
            "id", "patient_id", "credential_id", "public_key",
            "sign_count", "transports", "device_type", "name",
            "active", "created_at", "last_used_at",
        }
        assert expected.issubset(column_keys), f"Missing: {expected - column_keys}"
