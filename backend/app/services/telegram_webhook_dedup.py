"""PR-3: atomic update_id dedup shared by both Telegram ingress paths.

Telegram re-delivers bot updates whenever a delivery is not ACKed in
time (handler timeout, deploy, crash, network blip). Without dedup every
redelivery re-runs the bot handlers for an update that was already
processed — duplicated patient replies, double staff actions.

This service is the single source of truth for update_id dedup:

- The ledger key is ``(bot_identity, update_id)``. Telegram update_id
  sequences are PER BOT: claims carry a stable, non-secret per-credential
  identity (:func:`ledger_bot_identity`) so a row retained from a
  previous bot can never interact with the replacement bot's claims
  (codex round 20). NULL identity (credential unresolvable) degrades
  dedup to OFF for that claim — unique indexes treat NULLs as distinct —
  instead of ever suppressing another bot's updates.
- ``claim_update`` inserts the claim atomically (the UNIQUE index on
  (bot_identity, update_id) rejects a concurrent second claim). A
  rejected claim is disambiguated into DUPLICATE (already processed),
  IN_FLIGHT (a live handler owns it — the delivery must NOT be ACKed as
  handled, or a later failure of that handler loses the update; codex
  round 20) or a stale-crash reclaim.
- ``mark_processed`` flips the claim to 'processed' after the handler
  succeeded.
- ``release_claim`` deletes the claim after a failure so Telegram's
  redelivery is reprocessed (at-least-once; dedup must not turn a
  failed handling into a permanently swallowed update).
- A claim stranded in 'processing' by a hard crash is reclaimed by a
  later delivery of the same update_id once it is older than
  ``DEDUP_STALE_SECONDS`` — no update is ever lost to a crashed worker.
- Every database failure fails OPEN (returns ``UNAVAILABLE`` / no-op)
  and logs: dedup reduces duplicates, it must never reduce delivery
  availability.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.telegram_webhook_dedup import (
    UNKNOWN_BOT_IDENTITY,
    TelegramWebhookDedup,
)

logger = logging.getLogger(__name__)

# claim_update() results.
CLAIMED = "claimed"  # this call owns the update — process it
DUPLICATE = "duplicate"  # already processed by this bot — suppress (ACK ok)
IN_FLIGHT = "in_flight"  # a live handler owns it — NOT safe to ACK as handled
UNAVAILABLE = "unavailable"  # dedup store unreachable — fail open

# A 'processing' claim older than this is assumed dead (hard crash
# between claim and release) and is reclaimable. Live handlers complete
# in seconds; the ASGI/polling timeouts are far below this threshold.
DEDUP_STALE_SECONDS = 600

# Ledger retention — comfortably above Telegram's maximum redelivery
# horizon for a single update. Purged daily by data_retention.
DEDUP_RETENTION_DAYS = 7

_STATUS_PROCESSING = "processing"
_STATUS_PROCESSED = "processed"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def ledger_bot_identity(token: str | None) -> str | None:
    """Credential-scoped fallback identity (used when getMe is unreachable).

    Deterministic per credential: the same bot token always yields the
    same identity, so both ingress paths stay cross-consistent even in
    the degraded mode. NEVER the token itself (one-way hash).
    """
    if not token:
        return None
    return "cred:" + hashlib.sha256(str(token).encode("utf-8")).hexdigest()[:32]


# Resolved identities per credential (per process). Telegram bot ids are
# STABLE across token rotations — this is what keeps the dedup key
# unchanged when the same bot's token is rotated (codex round 22) — so
# the cache is keyed by the raw credential and never expires: the
# identity of a given token cannot change. FAILURES ARE NEVER CACHED
# (codex round 24): a worker that caches the credential-scoped fallback
# while another worker resolves the real getMe id would claim the same
# update under a DIFFERENT key — double execution. Every failed
# resolution is retried on the next call until it converges on the
# persisted id.
_IDENTITY_BY_TOKEN: dict[str, str] = {}

# Clinic-settings key for the persisted, SHARED bot identity (codex
# rounds 24-25). The value is a JSON object binding the identity to the
# credential fingerprint it was resolved for:
#   {"cred": "cred:<sha256[:32]>", "identity": "tgbot:<id>"}
# A credential change invalidates the row by fingerprint comparison — no
# clearing is needed; the next successful getMe overwrites it for the
# new credential. Unlike telegram_configs this covers env/.env-backed
# credentials too, so every worker resolves ONE namespace regardless of
# where the credential came from.
BOT_IDENTITY_SETTING_KEY = "telegram_bot_dedup_identity"


def _read_persisted_identity(token_text: str) -> str | None:
    """Read the credential-bound persisted identity (own session,
    fail-open).

    The clinic_settings row is the ONE identity value shared by every
    uvicorn worker and the polling worker (codex round 24) — and it
    covers env/.env-backed credentials too, where telegram_configs is
    absent (codex round 25). The stored credential fingerprint makes the
    row self-invalidating: a credential change (replacement bot or
    rotation) simply stops matching, and the next successful getMe
    overwrites the row for the new credential.
    """
    try:
        import json as _json

        from app.crud import clinic as crud_clinic
        from app.db.session import SessionLocal

        db = SessionLocal()
        try:
            setting = crud_clinic.get_setting_by_key(
                db, BOT_IDENTITY_SETTING_KEY
            )
            raw = getattr(setting, "value", None)
            if not raw:
                return None
            payload = _json.loads(raw)
            if payload.get("cred") != ledger_bot_identity(token_text):
                # Bound to a superseded credential.
                return None
            return payload.get("identity") or None
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001 — best-effort read, fail open
        logger.warning(
            "Telegram persisted bot identity read failed error_type=%s",
            type(exc).__name__,
        )
    return None


def _persist_bot_identity(token_text: str, identity: str) -> None:
    """Best-effort persist of the getMe-resolved identity (own session).

    Works for ANY credential source (config row, legacy setting, or env
    fallback — codex round 25): the row binds the identity to the
    credential fingerprint it was resolved for. Concurrent resolvers
    store the SAME value (a token's bot id cannot change), so the write
    is idempotent; failures are logged and the next successful
    resolution retries the write.
    """
    try:
        import json as _json

        from app.crud import clinic as crud_clinic
        from app.db.session import SessionLocal
        from app.models.clinic import ClinicSettings

        payload = _json.dumps(
            {
                "cred": ledger_bot_identity(token_text),
                "identity": identity,
            }
        )
        db = SessionLocal()
        try:
            setting = crud_clinic.get_setting_by_key(
                db, BOT_IDENTITY_SETTING_KEY
            )
            if setting is None:
                db.add(
                    ClinicSettings(
                        key=BOT_IDENTITY_SETTING_KEY,
                        value=payload,
                        category="telegram",
                    )
                )
            elif setting.value != payload:
                setting.value = payload
            else:
                return
            db.commit()
        finally:
            db.close()
    except SQLAlchemyError as exc:
        logger.warning(
            "Telegram persisted bot identity write failed error_type=%s",
            type(exc).__name__,
        )


async def _fetch_bot_id(token: str) -> str | None:
    """Return the bot's numeric id via getMe, or None on any failure."""
    try:
        import httpx

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"https://api.telegram.org/bot{token}/getMe"
            )
            payload = response.json()
            if payload.get("ok"):
                return str(payload["result"]["id"])
    except Exception as exc:  # noqa: BLE001 — identity resolution is best-effort
        logger.warning(
            "Telegram getMe identity lookup failed — falling back to the "
            "credential-scoped identity error_type=%s",
            type(exc).__name__,
        )
    return None


async def resolve_ledger_bot_identity(token: str | None) -> str | None:
    """STABLE per-bot ledger identity for the claim key.

    Telegram update_id sequences belong to a BOT, not to a credential:
    resolving the bot's numeric id via getMe keeps the key unchanged
    across same-bot token rotations (codex round 22) while a replacement
    bot (a different id) naturally gets a different namespace. The id is
    public and non-secret; the token itself is never stored.

    Resolution order (codex rounds 24-25):
    1. in-process cache (successful resolutions only);
    2. the PERSISTED identity (clinic_settings[
       telegram_bot_dedup_identity], credential-fingerprint-bound) — the
       ONE value shared by every uvicorn worker and the polling worker
       for ANY credential source (config row, legacy setting, or env
       fallback), so retries routed across workers always claim under
       the same key;
    3. getMe — persisted on success so the other workers converge;
    4. when getMe is unreachable: the deterministic credential-scoped
       identity, deliberately NOT cached — the next resolution retries
       getMe / re-reads the persisted value. All workers failing
       together still agree on the same fallback (same credential), so
       the namespace only ever diverges transiently instead of
       permanently.

    None means no credential at all (the claim lands in the "unknown"
    namespace).
    """
    if not token:
        return None
    token_text = str(token)
    cached = _IDENTITY_BY_TOKEN.get(token_text)
    if cached is not None:
        return cached

    persisted = _read_persisted_identity(token_text)
    if persisted:
        _IDENTITY_BY_TOKEN[token_text] = persisted
        return persisted

    bot_id = await _fetch_bot_id(token_text)
    if bot_id:
        identity = f"tgbot:{bot_id}"
        _persist_bot_identity(token_text, identity)
        _IDENTITY_BY_TOKEN[token_text] = identity
        return identity

    # Degraded mode — deterministic, shared while the outage lasts, and
    # never cached: every worker keeps retrying for the persisted id.
    return ledger_bot_identity(token_text)


def _log_db_failure(operation: str, update_id: int | None, exc: Exception) -> None:
    logger.warning(
        "Telegram webhook dedup %s failed — failing open "
        "operation=%s update_id=%s error_type=%s",
        operation,
        operation,
        update_id,
        type(exc).__name__,
    )


def _key_identity(bot_identity: str | None) -> str:
    """Normalize a claim key: an unresolvable credential lands in the
    shared "unknown" namespace (NOT NULL column — NULLs would never
    collide in the unique index and would disable dedup)."""
    return bot_identity or UNKNOWN_BOT_IDENTITY


def claim_update(
    db: Session, update_id: int | None, bot_identity: str | None = None
) -> str:
    """Try to claim ``update_id`` for exclusive processing.

    Returns CLAIMED, DUPLICATE, IN_FLIGHT or UNAVAILABLE (fail-open).
    ``None`` update_ids (payloads Telegram does not dedup on) are always
    CLAIMED and never written to the ledger. The claim commits in its own
    transaction, before any handler work runs on ``db``.

    IN_FLIGHT means another live handler currently owns the update: the
    caller must NOT acknowledge the delivery as successfully handled (a
    premature ACK plus a later failure of the owning handler would lose
    the update) — the webhook answers 503 so Telegram retries later.
    """
    if update_id is None:
        return CLAIMED

    for _ in range(2):
        try:
            db.add(
                TelegramWebhookDedup(
                    update_id=int(update_id),
                    bot_identity=_key_identity(bot_identity),
                )
            )
            db.commit()
            return CLAIMED
        except IntegrityError:
            # The UNIQUE index rejected a concurrent/previous claim of the
            # SAME bot identity. Either a live claim holds it (IN_FLIGHT),
            # a processed row already exists (DUPLICATE), or a crashed
            # worker left it in 'processing' past the stale threshold
            # (re-claim).
            db.rollback()
        except SQLAlchemyError as exc:
            db.rollback()
            _log_db_failure("claim", update_id, exc)
            return UNAVAILABLE

        disposition = _reclaim_stale_or_duplicate(
            db, int(update_id), _key_identity(bot_identity)
        )
        if disposition is not None:
            return disposition
        # The conflicting row vanished (the in-flight owner failed and
        # released between our failed INSERT and the lookup) — retry the
        # INSERT once so this delivery leaves a proper ledger row.

    # Pathological churn: both the INSERT and the lookup kept losing the
    # race. Fail open without a ledger row — at-least-once is preserved
    # (a later redelivery re-claims cleanly).
    return CLAIMED


def _reclaim_stale_or_duplicate(
    db: Session, update_id: int, bot_identity: str | None
) -> str | None:
    """Disambiguate a rejected claim (same bot identity only).

    Returns CLAIMED (stale-crash reclaim), DUPLICATE (already processed),
    IN_FLIGHT (a fresh 'processing' row owned by a live handler) or None
    when the conflicting row vanished — the caller retries the INSERT.
    """
    cutoff = _utcnow() - timedelta(seconds=DEDUP_STALE_SECONDS)
    try:
        result = db.execute(
            update(TelegramWebhookDedup)
            .where(
                TelegramWebhookDedup.update_id == update_id,
                TelegramWebhookDedup.bot_identity == bot_identity,
                TelegramWebhookDedup.status == _STATUS_PROCESSING,
                TelegramWebhookDedup.processed_at < cutoff,
            )
            .values(processed_at=_utcnow())
            .execution_options(synchronize_session=False)
        )
        db.commit()
        if result.rowcount == 1:
            logger.warning(
                "Telegram webhook dedup reclaimed stale claim "
                "update_id=%s stale_after_seconds=%s",
                update_id,
                DEDUP_STALE_SECONDS,
            )
            return CLAIMED

        row_status = db.execute(
            select(TelegramWebhookDedup.status).where(
                TelegramWebhookDedup.update_id == update_id,
                TelegramWebhookDedup.bot_identity == bot_identity,
            )
        ).scalar_one_or_none()
    except SQLAlchemyError as exc:
        db.rollback()
        _log_db_failure("stale-reclaim", update_id, exc)
        return UNAVAILABLE

    if row_status == _STATUS_PROCESSED:
        return DUPLICATE
    if row_status == _STATUS_PROCESSING:
        # Fresh 'processing' row → a live handler owns the update. The
        # delivery must NOT be ACKed as handled: if that handler later
        # fails and releases, only an un-ACKed delivery is retried by
        # Telegram (codex round 20).
        return IN_FLIGHT
    # Row gone — retry the INSERT.
    return None


def mark_processed(
    db: Session, update_id: int | None, bot_identity: str | None = None
) -> None:
    """Flip the claim to 'processed' (best effort, never raises).

    Scoped to the claiming bot identity so a concurrent claim of another
    bot for the same numeric update_id is never touched. If this fails
    the row stays 'processing' and the stale-reclaim path remains
    available; nothing is lost.
    """
    if update_id is None:
        return
    try:
        db.execute(
            update(TelegramWebhookDedup)
            .where(
                TelegramWebhookDedup.update_id == int(update_id),
                TelegramWebhookDedup.bot_identity == _key_identity(bot_identity),
            )
            .values(status=_STATUS_PROCESSED, processed_at=_utcnow())
            .execution_options(synchronize_session=False)
        )
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        _log_db_failure("mark-processed", update_id, exc)


def release_claim(
    db: Session, update_id: int | None, bot_identity: str | None = None
) -> None:
    """Delete the claim so a redelivery of this update is reprocessed.

    Scoped to the claiming bot identity (see ``mark_processed``). Best
    effort, never raises. Call on ANY failure path after a successful
    claim (handler exception, HTTP error response) — otherwise the failed
    update would be suppressed forever.
    """
    if update_id is None:
        return
    try:
        db.execute(
            delete(TelegramWebhookDedup).where(
                TelegramWebhookDedup.update_id == int(update_id),
                TelegramWebhookDedup.bot_identity == _key_identity(bot_identity),
            )
        )
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        _log_db_failure("release", update_id, exc)


def reset_ledger(
    db: Session, bot_identity: str | None = None, *, commit: bool = True
) -> int:
    """Delete ledger rows. Returns the number of deleted rows.

    With ``bot_identity`` the delete is SCOPED to that identity's rows
    (codex round 24): the polling worker wiping the superseded bot's
    namespace must not delete a claim the webhook workers already made
    or completed for the NEW bot — the composite key isolates the two
    namespaces, so only the superseded one is purged. With
    ``bot_identity=None`` EVERY row is deleted (all identities).

    ... (commit semantics unchanged)
    """
    try:
        stmt = delete(TelegramWebhookDedup)
        if bot_identity is not None:
            stmt = stmt.where(
                TelegramWebhookDedup.bot_identity == _key_identity(bot_identity)
            )
        result = db.execute(stmt)
        if commit:
            db.commit()
    except SQLAlchemyError as exc:
        if not commit:
            # Caller-owned transaction: surface the failure so the
            # caller's error handling (rollback / retry) applies.
            raise
        db.rollback()
        _log_db_failure("reset", None, exc)
        return 0
    deleted = int(result.rowcount or 0)
    if deleted:
        logger.info(
            "Telegram webhook dedup ledger reset rows_deleted=%s", deleted
        )
    return deleted


def purge_expired(
    db: Session, retention_days: int = DEDUP_RETENTION_DAYS
) -> int:
    """Delete ledger rows older than ``retention_days``. Returns count."""
    cutoff = _utcnow() - timedelta(days=retention_days)
    try:
        result = db.execute(
            delete(TelegramWebhookDedup).where(
                TelegramWebhookDedup.processed_at < cutoff
            )
        )
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        _log_db_failure("purge", None, exc)
        return 0

    deleted = int(result.rowcount or 0)
    if deleted:
        logger.info(
            "Telegram webhook dedup purged rows count=%s retention_days=%s",
            deleted,
            retention_days,
        )
    return deleted
