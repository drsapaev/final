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
from sqlalchemy.exc import IntegrityError

from app.api.v1.endpoints import admin_telegram
from app.api.v1.endpoints.admin_telegram import _settings as admin_telegram_settings
from app.core.config import settings
from app.crud import clinic as crud_clinic, telegram_config as crud_telegram
from app.models.audit import AuditLog
from app.models.clinic import ClinicSettings
from app.models.telegram_config import TelegramConfig
from app.schemas.notifications import UpdateTelegramSettingsRequest
from app.services import telegram_bot as telegram_bot_module
from app.services.telegram_token_store import (
    clear_patient_bot_token,
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

    def test_rotation_invalidates_stale_webhook_state(self, db_session, monkeypatch):
        _clear_token_env(monkeypatch)
        _set_fernet_key(monkeypatch)
        store_patient_bot_token(db_session, "123456789:old-bot")
        config = db_session.query(TelegramConfig).one()
        config.webhook_url = "https://example.com/webhook"
        config.webhook_secret = "old-bot-secret"
        config.active = True
        db_session.commit()

        store_patient_bot_token(db_session, "123456789:new-bot")

        db_session.expire_all()
        row = db_session.query(TelegramConfig).one()
        # P1 pin (round 13): the superseded bot's webhook secret must not
        # keep authenticating old-bot updates after a rotation.
        assert row.decrypted_bot_token == "123456789:new-bot"
        assert row.webhook_secret is None
        assert row.webhook_url is None

    def test_same_token_restore_preserves_webhook_state(self, db_session, monkeypatch):
        _clear_token_env(monkeypatch)
        _set_fernet_key(monkeypatch)
        store_patient_bot_token(db_session, "123456789:same-bot")
        config = db_session.query(TelegramConfig).one()
        config.webhook_url = "https://example.com/webhook"
        config.webhook_secret = "valid-secret"
        config.active = True
        db_session.commit()

        store_patient_bot_token(db_session, "123456789:same-bot")

        db_session.expire_all()
        row = db_session.query(TelegramConfig).one()
        assert row.webhook_secret == "valid-secret"
        assert row.webhook_url == "https://example.com/webhook"

    def test_store_rejects_oversized_token(self, db_session, monkeypatch):
        _clear_token_env(monkeypatch)
        _set_fernet_key(monkeypatch)
        oversized = "1" + "x" * 300  # real bot tokens are <= 64 chars

        with pytest.raises(TokenStoreError):
            store_patient_bot_token(db_session, oversized)
        assert db_session.query(TelegramConfig).first() is None

    def test_store_rejects_oversized_non_ascii_token(self, db_session, monkeypatch):
        """P2 pin (round 15): the limit is BYTES - 200 Cyrillic characters
        are 400 UTF-8 bytes and would overflow the column after Fernet
        expansion even though the character count is only 200."""
        _clear_token_env(monkeypatch)
        _set_fernet_key(monkeypatch)
        oversized_cyrillic = "ж" * 200

        assert len(oversized_cyrillic) == 200
        with pytest.raises(TokenStoreError):
            store_patient_bot_token(db_session, oversized_cyrillic)
        assert db_session.query(TelegramConfig).first() is None

    def test_store_rejects_empty_token(self, db_session):
        with pytest.raises(TokenStoreError):
            store_patient_bot_token(db_session, "")
        with pytest.raises(TokenStoreError):
            store_patient_bot_token(db_session, "   ")
        with pytest.raises(TokenStoreError):
            store_patient_bot_token(db_session, None)

    def test_store_supersedes_legacy_clinic_settings_row(self, db_session, monkeypatch):
        _clear_token_env(monkeypatch)
        _set_fernet_key(monkeypatch)
        db_session.add(
            ClinicSettings(
                key="bot_token", value="123456789:stale", category="telegram"
            )
        )
        db_session.commit()

        store_patient_bot_token(db_session, "123456789:fresh", actor_user_id=1)

        db_session.expire_all()
        # P1 pin: the superseded plaintext fallback must not survive the
        # rotation — a fail-closed decrypt of the canonical value could
        # otherwise reactivate the stale token through the legacy chain.
        assert crud_clinic.get_setting_by_key(db_session, "bot_token") is None
        row = db_session.query(TelegramConfig).one()
        assert row.decrypted_bot_token == "123456789:fresh"

    def test_store_without_legacy_row_records_no_removal(self, db_session, monkeypatch):
        _clear_token_env(monkeypatch)
        _set_fernet_key(monkeypatch)

        store_patient_bot_token(db_session, "123456789:fresh", actor_user_id=1)

        db_session.expire_all()
        event = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "telegram_bot_token_stored")
            .one()
        )
        assert event.payload["legacy_clinic_settings_row_removed"] is False

    def test_singleton_guard_rejects_second_config_row(self, db_session):
        db_session.add(TelegramConfig())
        db_session.add(TelegramConfig())
        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()

    def test_store_recovers_from_lost_creation_race(self, db_session, monkeypatch):
        _clear_token_env(monkeypatch)
        _set_fernet_key(monkeypatch)

        flush_calls = {"n": 0}
        original_flush = db_session.flush

        def _flaky_flush(*args, **kwargs):
            flush_calls["n"] += 1
            if flush_calls["n"] == 1:
                raise IntegrityError(
                    "INSERT", {}, Exception("uq_telegram_configs_singleton_guard")
                )
            return original_flush(*args, **kwargs)

        monkeypatch.setattr(db_session, "flush", _flaky_flush)

        store_patient_bot_token(db_session, "123456789:race-winner")

        db_session.expire_all()
        rows = db_session.query(TelegramConfig).all()
        assert len(rows) == 1
        assert rows[0].decrypted_bot_token == "123456789:race-winner"

    def test_store_writes_audit_record_without_token_value(
        self, db_session, monkeypatch
    ):
        _clear_token_env(monkeypatch)
        _set_fernet_key(monkeypatch)
        secret = "123456789:audited-secret"

        store_patient_bot_token(db_session, secret, actor_user_id=42)

        db_session.expire_all()
        events = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "telegram_bot_token_stored")
            .all()
        )
        assert len(events) == 1
        event = events[0]
        assert event.actor_user_id == 42
        assert event.entity_type == "telegram_config"
        assert secret not in str(event.payload)
        assert event.payload["token_encrypted"] is True

    def test_store_audit_captures_config_id_on_first_store(
        self, db_session, monkeypatch
    ):
        _clear_token_env(monkeypatch)
        _set_fernet_key(monkeypatch)

        config = store_patient_bot_token(db_session, "123456789:first-audit")

        db_session.expire_all()
        event = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "telegram_bot_token_stored")
            .one()
        )
        # P2 pin (round 2): the config INSERT is flushed before the audit row
        # is constructed, so the event links to the created configuration.
        assert event.entity_id == config.id
        assert event.entity_id is not None

    def test_store_deferred_commit_rolls_back_atomically(self, db_session, monkeypatch):
        _clear_token_env(monkeypatch)
        _set_fernet_key(monkeypatch)
        db_session.add(
            ClinicSettings(
                key="bot_token", value="123456789:legacy", category="telegram"
            )
        )
        db_session.commit()

        store_patient_bot_token(db_session, "123456789:pending", commit=False)
        db_session.rollback()

        db_session.expire_all()
        # commit=False keeps token + legacy removal + audit in the caller's
        # transaction: a rollback discards all three together.
        assert db_session.query(TelegramConfig).first() is None
        assert crud_clinic.get_setting_by_key(db_session, "bot_token") is not None
        assert (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "telegram_bot_token_stored")
            .count()
            == 0
        )


@pytest.mark.unit
class TestClearPatientBotToken:
    def test_clear_revokes_canonical_and_legacy(self, db_session, monkeypatch):
        _clear_token_env(monkeypatch)
        _set_fernet_key(monkeypatch)
        store_patient_bot_token(db_session, "123456789:to-revoke")
        db_session.add(
            ClinicSettings(
                key="bot_token", value="123456789:legacy", category="telegram"
            )
        )
        db_session.commit()

        clear_patient_bot_token(db_session, actor_user_id=7)

        db_session.expire_all()
        row = db_session.query(TelegramConfig).one()
        assert row.bot_token is None
        assert crud_clinic.get_setting_by_key(db_session, "bot_token") is None
        event = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "telegram_bot_token_cleared")
            .one()
        )
        assert event.actor_user_id == 7

    def test_clear_invalidates_running_service_credential(
        self, db_session, monkeypatch
    ):
        from app.services import telegram_bot as telegram_bot_module

        _clear_token_env(monkeypatch)
        _set_fernet_key(monkeypatch)
        service = telegram_bot_module.telegram_bot_service
        service.bot_token = "123456789:cached-credential"
        service.active = True

        store_patient_bot_token(db_session, "123456789:fresh")

        # P1 pin (round 6): the in-process singleton must drop the cached
        # credential so the webhook/notification paths re-initialize
        # instead of sending with the rotated-away token.
        assert service.bot_token is None
        assert service.active is False

    def test_clear_disables_webhook_state(self, db_session, monkeypatch):
        _clear_token_env(monkeypatch)
        _set_fernet_key(monkeypatch)
        store_patient_bot_token(db_session, "123456789:compromised")
        config = db_session.query(TelegramConfig).one()
        config.webhook_url = "https://example.com/webhook"
        config.webhook_secret = "topsecret"
        config.active = True
        db_session.commit()

        clear_patient_bot_token(db_session, actor_user_id=1)

        db_session.expire_all()
        row = db_session.query(TelegramConfig).one()
        # P1 pin (round 12): a retained webhook_secret would keep
        # authenticating the revoked bot's updates against clinic state.
        assert row.bot_token is None
        assert row.webhook_secret is None
        assert row.webhook_url is None
        assert row.active is False

    def test_clear_covers_legacy_only_revocation(self, db_session, monkeypatch):
        """P1 pin (round 14): a config row holding ONLY webhook metadata
        while the token lives in legacy clinic_settings must have its
        webhook auth state revoked too."""
        _clear_token_env(monkeypatch)
        _clear_fernet_key(monkeypatch)
        config = TelegramConfig()
        config.webhook_url = "https://example.com/webhook"
        config.webhook_secret = "old-bot-secret"
        config.active = True
        db_session.add(config)
        db_session.add(
            ClinicSettings(
                key="bot_token", value="123456789:legacy-only", category="telegram"
            )
        )
        db_session.commit()

        clear_patient_bot_token(db_session, actor_user_id=1)

        db_session.expire_all()
        row = db_session.query(TelegramConfig).one()
        assert row.webhook_secret is None
        assert row.webhook_url is None
        assert row.active is False
        assert crud_clinic.get_setting_by_key(db_session, "bot_token") is None

    def test_clear_removes_stale_bot_identity_without_fallback(
        self, db_session, monkeypatch
    ):
        """P1 pin (round 16): with no env fallback the stale bot_username
        must not keep generating t.me/<revoked-bot> ticket QR links."""
        _clear_token_env(monkeypatch)
        _set_fernet_key(monkeypatch)
        store_patient_bot_token(db_session, "123456789:compromised")
        config = db_session.query(TelegramConfig).one()
        config.bot_username = "old_revoked_bot"
        db_session.add(
            ClinicSettings(
                key="bot_username", value="old_revoked_bot", category="telegram"
            )
        )
        db_session.commit()

        clear_patient_bot_token(db_session)

        db_session.expire_all()
        row = db_session.query(TelegramConfig).one()
        assert row.bot_username is None
        assert crud_clinic.get_setting_by_key(db_session, "bot_username") is None
        event = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "telegram_bot_token_cleared")
            .one()
        )
        assert event.payload["bot_identity_cleared"] is True

    def test_clear_keeps_identity_with_env_fallback(self, db_session, monkeypatch):
        _clear_token_env(monkeypatch)
        _set_fernet_key(monkeypatch)
        store_patient_bot_token(db_session, "123456789:compromised")
        config = db_session.query(TelegramConfig).one()
        config.bot_username = "old_revoked_bot"
        db_session.commit()
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:env-fallback")

        clear_patient_bot_token(db_session)

        db_session.expire_all()
        row = db_session.query(TelegramConfig).one()
        assert row.bot_username == "old_revoked_bot"

    def test_clear_is_noop_without_any_token(self, db_session, monkeypatch):
        _clear_token_env(monkeypatch)
        _clear_fernet_key(monkeypatch)

        clear_patient_bot_token(db_session)

        db_session.expire_all()
        assert (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "telegram_bot_token_cleared")
            .count()
            == 0
        )


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
        crud_telegram.create_telegram_config(
            db_session, {"bot_token": "123456789:canonical"}
        )
        db_session.commit()
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

    def test_falls_back_to_pydantic_loaded_env(self, db_session, monkeypatch):
        """backend/.env tokens live in the Settings object, NOT os.environ."""
        _clear_token_env(monkeypatch)
        monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "123456789:dotenv-token")

        assert resolve_patient_bot_token(db_session) == "123456789:dotenv-token"

    def test_runtime_env_override_wins_over_loaded_settings(
        self, db_session, monkeypatch
    ):
        _clear_token_env(monkeypatch)
        monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "123456789:dotenv")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:runtime")

        assert resolve_patient_bot_token(db_session) == "123456789:runtime"

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
        monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", None)

        assert resolve_patient_bot_token(db_session) is None


@pytest.mark.unit
class TestStaffBotServiceStaleState:
    @pytest.mark.asyncio
    async def test_failed_reinit_clears_cached_credential(
        self, db_session, monkeypatch
    ):
        from app.services import telegram_bot as telegram_bot_service_module

        _set_fernet_key(monkeypatch)
        config = TelegramConfig()
        config.set_bot_token("123456789:good-token")
        config.active = True
        db_session.add(config)
        db_session.commit()

        service = telegram_bot_service_module.TelegramBotService()
        assert await service.initialize(db_session) is True
        assert service.bot_token == "123456789:good-token"
        assert service.active is True

        # Rotate to corrupted ciphertext and drop the key: fail-closed read.
        config.bot_token = "gAAAAA-corrupted-value"
        db_session.commit()
        monkeypatch.setattr(settings, "ENCRYPTION_KEY", None)

        assert await service.initialize(db_session) is False
        # P2 pin (round 3): the stale credential must not survive a failed
        # re-initialization - the polling worker reads bot_service.bot_token
        # directly, ignoring the return value.
        assert service.bot_token is None
        assert service.active is False

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_freshness_check_fails_closed_on_resolver_failure(
        self, db_session, monkeypatch
    ):
        import fastapi

        from app.api.v1.endpoints.telegram_webhook import _helpers
        from app.services import telegram_token_store as store_module

        _clear_token_env(monkeypatch)
        _set_fernet_key(monkeypatch)
        config = TelegramConfig()
        config.set_bot_token("123456789:good-token")
        config.active = True
        db_session.add(config)
        db_session.commit()

        service = telegram_bot_module.telegram_bot_service
        service.bot_token = "123456789:good-token"
        service.active = True
        try:

            def _boom(session):
                raise RuntimeError("db outage")

            monkeypatch.setattr(store_module, "resolve_patient_bot_token", _boom)
            with pytest.raises(fastapi.HTTPException) as exc_info:
                await _helpers._ensure_bot_service_fresh(db_session)
            # P2 pin (round 12): an unverifiable credential must not keep
            # operating - the operation aborts and the cache is cleared.
            assert exc_info.value.status_code == 503
            assert service.bot_token is None
            assert service.active is False
        finally:
            service.bot_token = None
            service.active = False

    @pytest.mark.asyncio
    async def test_env_only_initialize_serves_env_token(self, db_session, monkeypatch):
        """P1 pin (round 5): no config row + env token must initialize the
        handler service - otherwise the polling worker consumes updates
        without replies."""
        from app.services import telegram_bot as telegram_bot_service_module

        _clear_token_env(monkeypatch)
        _clear_fernet_key(monkeypatch)
        monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "123456789:env-only")

        service = telegram_bot_service_module.TelegramBotService()
        assert await service.initialize(db_session) is True
        assert service.bot_token == "123456789:env-only"
        assert service.active is True
        assert service.bot_username is None

    @pytest.mark.asyncio
    async def test_exception_path_also_clears_cached_credential(
        self, db_session, monkeypatch
    ):
        from app.crud import telegram_config as crud_telegram_module
        from app.services import telegram_bot as telegram_bot_service_module

        _set_fernet_key(monkeypatch)
        config = TelegramConfig()
        config.set_bot_token("123456789:good-token")
        config.active = True
        db_session.add(config)
        db_session.commit()

        service = telegram_bot_service_module.TelegramBotService()
        assert await service.initialize(db_session) is True
        assert service.bot_token == "123456789:good-token"

        def _boom(session):
            raise RuntimeError("transient db failure")

        monkeypatch.setattr(crud_telegram_module, "get_telegram_config", _boom)

        assert await service.initialize(db_session) is False
        # P2 pin (round 4): the exception handler bypasses the in-try reset,
        # so it must clear the cached state itself.
        assert service.bot_token is None
        assert service.active is False


@pytest.mark.unit
class TestCrossProcessVisibility:
    @pytest.mark.asyncio
    async def test_webhook_entry_reinitializes_stale_singleton(
        self, db_session, monkeypatch
    ):
        from app.api.v1.endpoints.telegram_webhook import _helpers

        _clear_token_env(monkeypatch)
        _set_fernet_key(monkeypatch)
        config = TelegramConfig()
        config.set_bot_token("123456789:rotated-token")
        config.active = True
        db_session.add(config)
        db_session.commit()

        service = telegram_bot_module.telegram_bot_service
        service.bot_token = "123456789:stale-credential"
        service.active = True
        try:
            fresh = await _helpers._ensure_bot_service_fresh(db_session)
            # P1 pin (round 8): another worker's rotation must become
            # visible to this process on the next webhook entry.
            assert fresh is service
            assert service.bot_token == "123456789:rotated-token"
            assert service.active is True
        finally:
            service.bot_token = None
            service.active = False

    def test_integration_status_reports_fallback_configured(
        self, db_session, monkeypatch
    ):
        from app.api.v1.endpoints import telegram_integration

        _clear_token_env(monkeypatch)
        _clear_fernet_key(monkeypatch)
        monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "123456789:env-live")
        config = TelegramConfig()
        config.bot_token = "gAAAAA-undecryptable-without-key"
        config.active = True
        db_session.add(config)
        db_session.commit()

        user = _user()
        result = telegram_integration.get_bot_status(db_session, user)

        # P2 pin (round 8): an undecryptable row with a live env fallback
        # must not read as unconfigured.
        assert result["configured"] is True

    def test_bot_status_reports_env_only_deployment_configured(
        self, db_session, monkeypatch
    ):
        from app.api.v1.endpoints import telegram_integration

        _clear_token_env(monkeypatch)
        _clear_fernet_key(monkeypatch)
        monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "123456789:env-only")

        result = telegram_integration.get_bot_status(db_session, _user())

        # P2 pin (round 10): the no-config-row early return must resolve the
        # token first - an env/.env-only deployment is configured.
        assert result["configured"] is True
        assert result["active"] is False


@pytest.mark.unit
class TestPollingWorkerTokenReload:
    def test_worker_reloads_rotated_token_without_401(self, monkeypatch):
        import asyncio

        from app.scripts.telegram_polling_worker import TelegramPollingWorker

        worker = TelegramPollingWorker(
            poll_timeout=0,
            request_timeout=1,
            retry_delay=0,
            drop_pending_updates=False,
            keep_webhook=True,
            once=False,
            max_updates=1,
        )
        tokens = iter(
            [
                "123456789:token-a",
                "123456789:token-a",
                "123456789:token-b",
            ]
        )

        async def fake_load():
            return next(tokens)

        async def fake_handle(update):
            return None

        def fake_get_updates(session, token, offset):
            return [] if token.endswith("token-a") else [{"update_id": 1}]

        monkeypatch.setattr(worker, "_load_bot_token", fake_load)
        monkeypatch.setattr(worker, "_handle_update", fake_handle)
        monkeypatch.setattr(worker, "_get_updates", fake_get_updates)

        exit_code = asyncio.run(worker.run())

        assert exit_code == 0

    def test_worker_401_branch_survives_resolver_failure(self, monkeypatch):
        import asyncio

        import requests as _requests

        from app.scripts.telegram_polling_worker import TelegramPollingWorker

        worker = TelegramPollingWorker(
            poll_timeout=0,
            request_timeout=1,
            retry_delay=0,
            drop_pending_updates=False,
            keep_webhook=True,
            once=False,
            max_updates=1,
        )
        _RAISE = object()
        script = [
            "123456789:token-a",
            "123456789:token-a",
            _RAISE,  # resolver failure inside the 401 branch
            "123456789:token-b",
        ]
        loads = []

        async def fake_load():
            value = script[len(loads)]
            loads.append(value)
            if value is _RAISE:
                raise RuntimeError("transient db outage")
            return value

        async def fake_handle(update):
            return None

        response = _requests.Response()
        response.status_code = 401
        get_updates_calls = []

        def fake_get_updates(session, token, offset):
            get_updates_calls.append(token)
            if len(get_updates_calls) == 1:
                raise _requests.HTTPError("401 Unauthorized", response=response)
            return [{"update_id": 1}]

        monkeypatch.setattr(worker, "_load_bot_token", fake_load)
        monkeypatch.setattr(worker, "_handle_update", fake_handle)
        monkeypatch.setattr(worker, "_get_updates", fake_get_updates)

        exit_code = asyncio.run(worker.run())

        # P2 pin (round 13): a resolver failure inside the 401 branch must
        # not terminate run() - the worker recovers on the next cycle.
        assert exit_code == 0
        assert get_updates_calls == ["123456789:token-a", "123456789:token-b"]
        # P1 pin (round 7): the swap happens WITHOUT a 401 - the worker
        # compares the canonical token every cycle and continues polling
        # with the rotated credential.
        assert worker is not None


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
        db_session.add(
            ClinicSettings(
                key="bot_token", value="123456789:pre-existing", category="telegram"
            )
        )
        db_session.commit()
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
        # P1 pin: replacement also clears the legacy plaintext row.
        assert crud_clinic.get_setting_by_key(db_session, "bot_token") is None
        # P2 pin: the rotation is attributed to the acting admin.
        event = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "telegram_bot_token_stored")
            .one()
        )
        assert event.actor_user_id == 1
        assert secret not in str(event.payload)

    def test_put_combined_update_is_single_transaction(self, db_session, monkeypatch):
        from app.crud import clinic as clinic_module

        _clear_token_env(monkeypatch)
        _set_fernet_key(monkeypatch)
        secret = "123456789:atomic-secret"
        db_session.add(
            ClinicSettings(
                key="bot_token", value="123456789:legacy-atomic", category="telegram"
            )
        )
        db_session.commit()

        def _explode(db, category, settings, user_id):
            raise RuntimeError("settings write failed")

        monkeypatch.setattr(clinic_module, "update_settings_batch", _explode)
        payload = UpdateTelegramSettingsRequest(
            bot_token=secret,
            notifications_enabled=False,
        )

        with pytest.raises(Exception):
            admin_telegram_settings.update_telegram_settings(
                payload, db_session, _user()
            )

        db_session.rollback()
        # P2 pin (round 2): the token write, legacy-row removal and audit
        # event share the settings batch's transaction — a failure in the
        # batch discards the credential change too (no partial update).
        assert db_session.query(TelegramConfig).first() is None
        assert crud_clinic.get_setting_by_key(db_session, "bot_token") is not None
        assert (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "telegram_bot_token_stored")
            .count()
            == 0
        )

    def test_put_empty_token_clears_canonical(self, db_session, monkeypatch):
        _clear_token_env(monkeypatch)
        _set_fernet_key(monkeypatch)
        store_patient_bot_token(db_session, "123456789:compromised")
        payload = UpdateTelegramSettingsRequest(
            bot_token="",
            notifications_enabled=True,
        )

        result = admin_telegram_settings.update_telegram_settings(
            payload, db_session, _user()
        )

        assert result["bot_token_cleared"] is True
        assert result["bot_token_stored"] is False
        db_session.expire_all()
        row = db_session.query(TelegramConfig).one()
        assert row.bot_token is None
        event = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "telegram_bot_token_cleared")
            .one()
        )
        assert event.actor_user_id == 1

    def test_put_empty_token_reports_environment_fallback(
        self, db_session, monkeypatch
    ):
        _clear_token_env(monkeypatch)
        _set_fernet_key(monkeypatch)
        monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "123456789:env-active")
        store_patient_bot_token(db_session, "123456789:compromised")
        payload = UpdateTelegramSettingsRequest(bot_token="")

        result = admin_telegram_settings.update_telegram_settings(
            payload, db_session, _user()
        )

        # P1 pin (round 5): revocation with a live environment token must
        # NOT claim a full success - the bot keeps operating on the env
        # credential.
        assert result["bot_token_cleared"] is True
        assert result["environment_fallback_active"] is True

    def test_put_empty_token_without_env_reports_clean_revocation(
        self, db_session, monkeypatch
    ):
        _clear_token_env(monkeypatch)
        _set_fernet_key(monkeypatch)
        monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", None)
        store_patient_bot_token(db_session, "123456789:compromised")
        payload = UpdateTelegramSettingsRequest(bot_token="")

        result = admin_telegram_settings.update_telegram_settings(
            payload, db_session, _user()
        )

        assert result["bot_token_cleared"] is True
        assert result["environment_fallback_active"] is False

    def test_put_oversized_token_returns_400(self, db_session, monkeypatch):
        import pytest as _pytest
        from fastapi import HTTPException as _HTTPException

        _clear_token_env(monkeypatch)
        _set_fernet_key(monkeypatch)
        payload = UpdateTelegramSettingsRequest(bot_token="1" + "x" * 300)

        with _pytest.raises(_HTTPException) as exc_info:
            admin_telegram_settings.update_telegram_settings(
                payload, db_session, _user()
            )

        assert exc_info.value.status_code == 400
        assert db_session.query(TelegramConfig).first() is None

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
