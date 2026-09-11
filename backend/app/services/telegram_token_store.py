"""PR-2: Single source of truth for Telegram bot token storage and resolution.

Storage contract (patient bot token)
------------------------------------
1. ``telegram_configs.bot_token`` — canonical store. Written ONLY through
   :func:`store_patient_bot_token` (Fernet-encrypted at write when an
   ``ENCRYPTION_KEY`` is configured).
2. ``clinic_settings[key="bot_token"]`` — legacy fallback, read-only from
   this module's perspective (decrypt-if-encrypted so migration-period rows
   keep resolving).
3. ``settings.TELEGRAM_BOT_TOKEN`` — last-resort environment fallback.

Staff bot token contract (unchanged precedence, decrypt-if-encrypted):
``STAFF_BOT_TOKEN_ENV_KEYS`` environment variables first, then
``STAFF_BOT_TOKEN_SETTING_KEYS`` clinic settings.

The two-bot split (P1-18) is intentionally preserved: the patient bot
(``services/telegram/bot.py``) and the notifications sender read the env
token directly by contract; this module owns every DB-backed token access.

Crypto contract
---------------
* ``encrypt_token`` returns a Fernet token when a key is configured. Without
  a key (dev/test only — production startup validation requires
  ``ENCRYPTION_KEY``) it returns the plaintext unchanged so local
  environments keep working.
* ``decrypt_token`` is fail-closed for anything Fernet-shaped: a missing key
  or an undecryptable value yields ``None`` (never the ciphertext, never an
  exception leak). Plaintext values pass through unchanged — migration
  period.
"""

from __future__ import annotations

import logging

from sqlalchemy.exc import IntegrityError

from app.core.config import settings

logger = logging.getLogger(__name__)

FERNET_PREFIX = "gAAAAA"

# Legacy patient-bot-token clinic-settings key (read-only fallback).
PATIENT_BOT_TOKEN_SETTING_KEY = "bot_token"

# Staff bot token sources. Canonical home for these tuples (endpoints
# re-export them for backwards compatibility).
STAFF_BOT_TOKEN_ENV_KEYS = (
    "TELEGRAM_STAFF_BOT_TOKEN",
    "STAFF_TELEGRAM_BOT_TOKEN",
)
STAFF_BOT_TOKEN_SETTING_KEYS = (
    "staff_bot_token",
    "telegram_staff_bot_token",
)


class TokenStoreError(ValueError):
    """Raised when a token cannot be stored or the input is invalid."""


def is_encrypted_token(value: str | None) -> bool:
    """True when the value looks like a Fernet token."""
    return bool(value) and str(value).startswith(FERNET_PREFIX)


def encrypt_token(value: str | None) -> str | None:
    """Encrypt a secret for DB storage (no-op plaintext without a key)."""
    if not value:
        return None
    encryption_key = getattr(settings, "ENCRYPTION_KEY", None)
    if not encryption_key:
        # Dev/test only: production startup validation requires ENCRYPTION_KEY.
        logger.warning(
            "ENCRYPTION_KEY not configured — storing Telegram token as plaintext"
        )
        return value
    from cryptography.fernet import Fernet

    cipher = Fernet(str(encryption_key).encode())
    return cipher.encrypt(value.encode()).decode()


def decrypt_token(value: str | None) -> str | None:
    """Decrypt a stored secret; fail-closed for Fernet-shaped values."""
    if not value:
        return None
    value_text = str(value)
    if not is_encrypted_token(value_text):
        # Plaintext row (migration period) — pass through.
        return value_text
    encryption_key = getattr(settings, "ENCRYPTION_KEY", None)
    if not encryption_key:
        logger.error(
            "Telegram token is encrypted but ENCRYPTION_KEY is not configured — "
            "refusing to return the ciphertext (fail-closed)"
        )
        return None
    from cryptography.fernet import Fernet, InvalidToken

    try:
        cipher = Fernet(str(encryption_key).encode())
        return cipher.decrypt(value_text.encode()).decode()
    except (InvalidToken, ValueError):
        logger.error(
            "Telegram token decryption failed (wrong key or corrupted value) — "
            "refusing to return the ciphertext (fail-closed)"
        )
        return None


def resolve_patient_bot_token(db) -> str | None:
    """Resolve the patient bot token: config -> clinic settings -> env."""
    import os

    from app.crud import clinic as crud_clinic, telegram_config as crud_telegram

    config = crud_telegram.get_telegram_config(db)
    if config is not None:
        token = decrypt_token(config.bot_token)
        if token:
            return token

    setting = crud_clinic.get_setting_by_key(db, PATIENT_BOT_TOKEN_SETTING_KEY)
    if setting is not None:
        token = decrypt_token(getattr(setting, "value", None))
        if token:
            return token

    # Runtime os.environ wins (post-import overrides), then the pydantic
    # Settings value — TELEGRAM_BOT_TOKEN configured only in backend/.env is
    # loaded into the settings object WITHOUT being present in os.environ,
    # so a bare os.getenv() would miss it (codex round 3).
    env_token = str(os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    if not env_token:
        env_token = str(getattr(settings, "TELEGRAM_BOT_TOKEN", None) or "").strip()
    return env_token or None


def resolve_staff_bot_token(db, patient_token: str | None = None) -> str | None:
    """Resolve the dedicated staff bot token: env keys -> setting keys."""
    import os

    from app.crud import clinic as crud_clinic

    patient_token_text = str(patient_token or "").strip()

    for env_key in STAFF_BOT_TOKEN_ENV_KEYS:
        token_text = str(os.getenv(env_key) or "").strip()
        if token_text and token_text != patient_token_text:
            return token_text

    for setting_key in STAFF_BOT_TOKEN_SETTING_KEYS:
        setting = crud_clinic.get_setting_by_key(db, setting_key)
        raw_value = getattr(setting, "value", None)
        token_text = str(decrypt_token(raw_value) or "").strip()
        if token_text and token_text != patient_token_text:
            return token_text

    return None


def _invalidate_running_service_credential() -> None:
    """Drop the cached credential of the in-process bot service singleton.

    The webhook/notification paths read ``telegram_bot_service.bot_token``
    directly and re-initialize only while ``active`` is false, so a DB-side
    rotation or revocation must reset the cached state or the process keeps
    operating with the old credential until restart (codex round 6).
    """
    # get_telegram_bot_service() is async; the store is sync — read the
    # module-level singleton directly.
    from app.services import telegram_bot as telegram_bot_module

    service = telegram_bot_module.telegram_bot_service
    if service.bot_token or service.active:
        service.bot_token = None
        service.active = False
        service.bot_username = None
        service.webhook_url = None
        logger.info("Invalidated cached Telegram bot credential after token write")


def store_patient_bot_token(
    db, token: str | None, *, actor_user_id: int | None = None, commit: bool = True
) -> object:
    """Create-or-update the TelegramConfig bot token (encrypted at write).

    This is the ONLY sanctioned write path for ``telegram_configs.bot_token``.

    Storing a replacement also removes the legacy plaintext
    ``clinic_settings[bot_token]`` row in the same transaction — otherwise a
    fail-closed decrypt of the canonical value (missing/wrong key) could
    silently reactivate the superseded credential through the legacy
    fallback. An audit record is appended attributing the rotation to
    ``actor_user_id`` WITHOUT recording the token value.

    With ``commit=False`` the whole write (token + legacy-row removal +
    audit event) stays pending in the caller's transaction so an endpoint
    can land it together with the rest of the request in ONE commit; any
    later ``db.commit()`` on the same session finalizes it atomically.

    A concurrent first-store race (two transactions both observing "no
    config") is resolved by the DB-level singleton guard (unique
    ``singleton_guard``, migration 0061): the losing INSERT raises
    ``IntegrityError`` at flush, this function rolls back and updates the
    committed winner instead.
    """
    from app.crud import (
        audit as crud_audit,
        clinic as crud_clinic,
        telegram_config as crud_telegram,
    )
    from app.models.telegram_config import TelegramConfig

    if not token or not str(token).strip():
        raise TokenStoreError("patient bot token must be a non-empty string")
    token_text = str(token).strip()

    for attempt in range(2):
        try:
            # Every ORM lookup below can autoflush a pending INSERT, so the
            # whole body lives inside the retry block: a singleton-guard
            # violation escaping via autoflush must roll back and re-resolve
            # exactly like an explicit flush would (codex round 9).
            config = crud_telegram.get_telegram_config(db)
            if config is None:
                config = TelegramConfig()
                db.add(config)
            config.set_bot_token(token_text)

            legacy_setting = crud_clinic.get_setting_by_key(
                db, PATIENT_BOT_TOKEN_SETTING_KEY
            )
            legacy_removed = False
            if legacy_setting is not None:
                db.delete(legacy_setting)
                legacy_removed = True

            # Flush the pending config INSERT first so the audit row below
            # captures the real config id, and so a singleton-guard violation
            # (lost creation race) surfaces before the audit event is built.
            db.flush()
        except IntegrityError:
            db.rollback()
            if attempt:
                raise
            # Lost the race: the winner row is committed and visible after
            # the rollback — loop once more and update it instead.
            continue

        _invalidate_running_service_credential()
        crud_audit.log(
            db,
            action="telegram_bot_token_stored",
            entity_type="telegram_config",
            entity_id=config.id,
            actor_user_id=actor_user_id,
            payload={
                "legacy_clinic_settings_row_removed": legacy_removed,
                "token_encrypted": is_encrypted_token(config.bot_token),
            },
        )
        break

    if commit:
        db.commit()
        db.refresh(config)
    return config


def clear_patient_bot_token(
    db, *, actor_user_id: int | None = None, commit: bool = True
) -> object | None:
    """Revoke the stored patient bot token (canonical + legacy fallback).

    Writes ``NULL`` to ``telegram_configs.bot_token``, removes the legacy
    ``clinic_settings[bot_token]`` row and appends an audit event — all in
    the caller's transaction (see ``commit`` semantics above).
    """
    from app.crud import audit as crud_audit
    from app.crud import clinic as crud_clinic
    from app.crud import telegram_config as crud_telegram

    config = crud_telegram.get_telegram_config(db)
    legacy_setting = crud_clinic.get_setting_by_key(db, PATIENT_BOT_TOKEN_SETTING_KEY)

    cleared = False
    if config is not None and config.bot_token:
        config.set_bot_token(None)
        cleared = True
    if legacy_setting is not None:
        db.delete(legacy_setting)
        cleared = True
    if not cleared:
        return config

    _invalidate_running_service_credential()
    db.flush()
    crud_audit.log(
        db,
        action="telegram_bot_token_cleared",
        entity_type="telegram_config",
        entity_id=config.id if config is not None else None,
        actor_user_id=actor_user_id,
        payload={},
    )

    if commit:
        db.commit()
        if config is not None:
            db.refresh(config)
    return config
