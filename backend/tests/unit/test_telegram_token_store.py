"""PR-2: Telegram bot token SSOT + encryption-at-write contracts.

Covers:
- crypto primitives (roundtrip, plaintext passthrough, fail-closed decrypt);
- store_patient_bot_token as the only sanctioned write path;
- crud create/update routing bot_token through encrypted-at-write;
- resolve_patient_bot_token precedence (config -> legacy setting -> env);
- resolve_staff_bot_token (env keys -> setting keys, decrypt-if-encrypted);
- admin settings endpoints (GET mask from config, PUT routing to config).
"""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from app.api.v1.endpoints import admin_telegram
from app.api.v1.endpoints.admin_telegram import _settings as admin_telegram_settings
from app.core.config import settings
from app.crud import clinic as crud_clinic, telegram_config as crud_telegram
from app.models.clinic import ClinicSettings
from app.models.telegram_config import TelegramConfig
from app.schemas.notifications import UpdateTelegramSettingsRequest
from app.services import telegram_token_store as store
from app.services.telegram_token_store import (
    decrypt_token,
    encrypt_token,
    is_encrypted_token,
    resolve_patient_bot_token,
    resolve_staff_bot_token,
    store_patient_bot_token,
    TokenStoreError,
)

TOKEN_ENV_KEYS = (
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_STAFF_BOT_TOKEN",
    "STAFF_TELEGRAM_BOT_TOKEN",
)


def _set_fernet_key(monkeypatch) -> str:
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "ENCRYPTION_KEY", key)
    return key


def _clear_fernet_key(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ENCRYPTION_KEY", None)


def _clear_token_env(monkeypatch) -> None:
    for env_key in TOKEN_ENV_KEYS:
        monkeypatch.delenv(env_key, raising=False)


@pytest.mark.unit
class TestTokenCrypto:
    def test_roundtrip_with_key(self, monkeypatch):
        _set_fernet_key(monkeypatch)
        secret = "123456789:roundtrip-secret-value"
        ciphertext = encrypt_token(secret)

        assert ciphertext != secret
        assert is_encrypted_token(ciphertext)
        assert decrypt_token(ciphertext) == secret

    def test_plaintext_passthrough_without_key(self, monkeypatch):
        _clear_fernet_key(monkeypatch)
        secret = "123456789:legacy-plaintext"

        assert is_encrypted_token(secret) is False
        assert encrypt_token(secret) == secret
        assert decrypt_token(secret) == secret

    def test_decrypt_fail_closed_without_key(self, monkeypatch):
        _set_fernet_key(monkeypatch)
        ciphertext = encrypt_token("123456789:secret")
        _clear_fernet_key(monkeypatch)

        assert ciphertext is not None
        assert decrypt_token(ciphertext) is None

    def test_decrypt_fail_closed_with_wrong_key(self, monkeypatch):
        _set_fernet_key(monkeypatch)
        ciphertext = encrypt_token("123456789:secret")
        monkeypatch.setattr(settings, "ENCRYPTION_KEY", Fernet.generate_key().decode())

        assert decrypt_token(ciphertext) is None

    def test_decrypt_fail_closed_on_corrupted_value(self, monkeypatch):
        _set_fernet_key(monkeypatch)
        corrupted = "gAAAAA" + "not-a-valid-fernet-token"

        assert decrypt_token(corrupted) is None

    def test_empty_values(self, monkeypatch):
        _set_fernet_key(monkeypatch)
        assert encrypt_token("") is None
        assert encrypt_token(None) is None
        assert decrypt_token("") is None
        assert decrypt_token(None) is None


@pytest.mark.unit
class TestStorePatientBotToken:
    def test_store_creates_encrypted_row(self, db_session, monkeypatch):
        _clear_token_env(monkeypatch)
        _set_fernet_key(monkeypatch)
        secret = "123456789:stored-secret"

        config = store_patient_bot_token(db_session, secret)

        db_session.expire_all()
        row = db_session.query(TelegramConfig).first()
        assert row is not None
        assert row.id == config.id
        assert row.bot_token != secret
        assert is_encrypted_token(row.bot_token)
        assert row.decrypted_bot_token == secret

    def test_store_upserts_single_row(self, db_session, monkeypatch):
        _clear_token_env(monkeypatch)
        _set_fernet_key(monkeypatch)

        store_patient_bot_token(db_session, "123456789:first")
        store_patient_bot_token(db_session, "123456789:second")

        db_session.expire_all()
        rows = db_session.query(TelegramConfig).all()
        assert len(rows) == 1
        assert rows[0].decrypted_bot_token == "123456789:second"

    def test_store_rejects_empty_token(self, db_session):
        with pytest.raises(TokenStoreError):
            store_patient_bot_token(db_session, "")
        with pytest.raises(TokenStoreError):
            store_patient_bot_token(db_session, "   ")
        with pytest.raises(TokenStoreError):
            store_patient_bot_token(db_session, None)


@pytest.mark.unit
class TestCrudEncryptionAtWrite:
    def test_create_telegram_config_encrypts(self, db_session, monkeypatch):
        _clear_token_env(monkeypatch)
        _set_fernet_key(monkeypatch)
        secret = "123456789:crud-create-secret"

        crud_telegram.create_telegram_config(
            db_session, {"bot_token": secret, "bot_username": "clinic_bot"}
        )

        db_session.expire_all()
        row = db_session.query(TelegramConfig).one()
        assert row.bot_token != secret
        assert is_encrypted_token(row.bot_token)
        assert row.decrypted_bot_token == secret
        assert row.bot_username == "clinic_bot"

    def test_update_telegram_config_encrypts(self, db_session, monkeypatch):
        _clear_token_env(monkeypatch)
        _set_fernet_key(monkeypatch)
        first = "123456789:crud-first"
        second = "123456789:crud-second"

        crud_telegram.create_telegram_config(db_session, {"bot_token": first})
        crud_telegram.update_telegram_config(
            db_session, {"bot_token": second, "active": True}
        )

        db_session.expire_all()
        rows = db_session.query(TelegramConfig).all()
        assert len(rows) == 1
        assert rows[0].bot_token != second
        assert rows[0].decrypted_bot_token == second
        assert rows[0].active is True

    def test_update_without_key_keeps_plaintext_migration_behavior(
        self, db_session, monkeypatch
    ):
        _clear_token_env(monkeypatch)
        _clear_fernet_key(monkeypatch)
        secret = "123456789:dev-plaintext"

        crud_telegram.create_telegram_config(db_session, {"bot_token": secret})

        db_session.expire_all()
        row = db_session.query(TelegramConfig).one()
        assert row.bot_token == secret
        assert row.decrypted_bot_token == secret


@pytest.mark.unit
class TestResolvePatientBotToken:
    def test_precedence_config_over_setting_over_env(self, db_session, monkeypatch):
        _clear_token_env(monkeypatch)
        _set_fernet_key(monkeypatch)

        db_session.add(
            ClinicSettings(
                key="bot_token", value="123456789:legacy", category="telegram"
            )
        )
        store_patient_bot_token(db_session, "123456789:canonical")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:env")

        assert resolve_patient_bot_token(db_session) == "123456789:canonical"

    def test_falls_back_to_legacy_plaintext_setting(self, db_session, monkeypatch):
        _clear_token_env(monkeypatch)
        db_session.add(
            ClinicSettings(
                key="bot_token", value="123456789:legacy", category="telegram"
            )
        )
        db_session.commit()

        assert resolve_patient_bot_token(db_session) == "123456789:legacy"

    def test_falls_back_to_encrypted_setting(self, db_session, monkeypatch):
        _clear_token_env(monkeypatch)
        _set_fernet_key(monkeypatch)
        db_session.add(
            ClinicSettings(
                key="bot_token",
                value=encrypt_token("123456789:encrypted-setting"),
                category="telegram",
            )
        )
        db_session.commit()

        assert resolve_patient_bot_token(db_session) == "123456789:encrypted-setting"

    def test_falls_back_to_env(self, db_session, monkeypatch):
        _clear_token_env(monkeypatch)
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:env-token")

        assert resolve_patient_bot_token(db_session) == "123456789:env-token"

    def test_encrypted_config_without_key_falls_through(self, db_session, monkeypatch):
        _clear_token_env(monkeypatch)
        _set_fernet_key(monkeypatch)
        store_patient_bot_token(db_session, "123456789:sealed")
        monkeypatch.setattr(settings, "ENCRYPTION_KEY", None)
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:env")

        assert resolve_patient_bot_token(db_session) == "123456789:env"

    def test_none_when_nothing_configured(self, db_session, monkeypatch):
        _clear_token_env(monkeypatch)
        _clear_fernet_key(monkeypatch)

        assert resolve_patient_bot_token(db_session) is None


@pytest.mark.unit
class TestResolveStaffBotToken:
    def test_env_keys_precedence(self, db_session, monkeypatch):
        _clear_token_env(monkeypatch)
        monkeypatch.setenv("STAFF_TELEGRAM_BOT_TOKEN", "123456789:staff-legacy")
        monkeypatch.setenv("TELEGRAM_STAFF_BOT_TOKEN", "123456789:staff-primary")

        assert resolve_staff_bot_token(db_session) == "123456789:staff-primary"

    def test_setting_key_decrypts_encrypted_value(self, db_session, monkeypatch):
        _clear_token_env(monkeypatch)
        _set_fernet_key(monkeypatch)
        db_session.add(
            ClinicSettings(
                key="telegram_staff_bot_token",
                value=encrypt_token("123456789:staff-sealed"),
                category="telegram",
            )
        )
        db_session.commit()

        assert resolve_staff_bot_token(db_session) == "123456789:staff-sealed"

    def test_skips_patient_token_reuse(self, db_session, monkeypatch):
        _clear_token_env(monkeypatch)
        monkeypatch.setenv("TELEGRAM_STAFF_BOT_TOKEN", "123456789:shared")

        assert (
            resolve_staff_bot_token(db_session, patient_token="123456789:shared")
            is None
        )

    def test_returns_none_without_sources(self, db_session, monkeypatch):
        _clear_token_env(monkeypatch)
        _clear_fernet_key(monkeypatch)

        assert resolve_staff_bot_token(db_session) is None


@pytest.mark.unit
class TestAdminSettingsEndpoints:
    def test_get_masks_config_only_token(self, db_session, monkeypatch):
        _clear_token_env(monkeypatch)
        _set_fernet_key(monkeypatch)
        secret = "123456789:get-mask-secret"
        store_patient_bot_token(db_session, secret)

        response = admin_telegram.get_telegram_settings(db_session, _user())

        assert response["bot_token_masked"]
        assert response["bot_token"] != secret
        assert secret not in str(response)
        assert "bot_token_length" not in response
        legacy = crud_clinic.get_setting_by_key(db_session, "bot_token")
        assert legacy is None

    def test_put_routes_bot_token_to_config_not_clinic_settings(
        self, db_session, monkeypatch
    ):
        _clear_token_env(monkeypatch)
        _set_fernet_key(monkeypatch)
        secret = "123456789:put-routed-secret"
        payload = UpdateTelegramSettingsRequest(
            bot_token=secret,
            notifications_enabled=False,
        )

        result = admin_telegram_settings.update_telegram_settings(
            payload, db_session, _user()
        )

        assert result["bot_token_stored"] is True
        db_session.expire_all()
        config = db_session.query(TelegramConfig).one()
        assert config.bot_token != secret
        assert config.decrypted_bot_token == secret
        assert crud_clinic.get_setting_by_key(db_session, "bot_token") is None

    def test_put_masked_placeholder_is_ignored(self, db_session, monkeypatch):
        _clear_token_env(monkeypatch)
        _clear_fernet_key(monkeypatch)
        payload = UpdateTelegramSettingsRequest(
            bot_token="***скрыт***",
            notifications_enabled=False,
        )

        result = admin_telegram_settings.update_telegram_settings(
            payload, db_session, _user()
        )

        assert result["bot_token_stored"] is False
        assert db_session.query(TelegramConfig).first() is None
        assert crud_clinic.get_setting_by_key(db_session, "bot_token") is None

    def test_get_masks_legacy_clinic_setting_row(self, db_session, monkeypatch):
        _clear_token_env(monkeypatch)
        _clear_fernet_key(monkeypatch)
        secret = "123456789:legacy-get-secret"
        db_session.add(
            ClinicSettings(key="bot_token", value=secret, category="telegram")
        )
        db_session.commit()

        response = admin_telegram.get_telegram_settings(db_session, _user())

        assert response["bot_token_masked"]
        assert secret not in str(response)


def _user():
    from types import SimpleNamespace

    return SimpleNamespace(id=1)
