"""PR-3: atomic update_id dedup shared by both Telegram ingress paths.

Telegram re-delivers bot updates whenever a delivery is not ACKed in
time (handler timeout, deploy, crash, network blip). Without dedup every
redelivery re-runs the bot handlers for an update that was already
processed — duplicated patient replies, double staff actions.

This service is the single source of truth for update_id dedup:

- ``claim_update`` inserts the claim atomically (the UNIQUE index on
  telegram_webhook_dedup.update_id rejects a concurrent second claim).
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

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.telegram_webhook_dedup import TelegramWebhookDedup

logger = logging.getLogger(__name__)

# claim_update() results.
CLAIMED = "claimed"  # this call owns the update — process it
DUPLICATE = "duplicate"  # another delivery owns/owned it — suppress
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


def _log_db_failure(operation: str, update_id: int | None, exc: Exception) -> None:
    logger.warning(
        "Telegram webhook dedup %s failed — failing open "
        "operation=%s update_id=%s error_type=%s",
        operation,
        operation,
        update_id,
        type(exc).__name__,
    )


def claim_update(db: Session, update_id: int | None) -> str:
    """Try to claim ``update_id`` for exclusive processing.

    Returns CLAIMED, DUPLICATE or UNAVAILABLE (fail-open). ``None``
    update_ids (payloads Telegram does not dedup on) are always CLAIMED
    and never written to the ledger. The claim commits in its own
    transaction, before any handler work runs on ``db``.
    """
    if update_id is None:
        return CLAIMED

    try:
        db.add(TelegramWebhookDedup(update_id=int(update_id)))
        db.commit()
        return CLAIMED
    except IntegrityError:
        # The UNIQUE index rejected a concurrent/previous claim. Either a
        # live claim holds it (DUPLICATE), or a crashed worker left it in
        # 'processing' past the stale threshold (re-claim).
        db.rollback()
        return _reclaim_stale_or_duplicate(db, int(update_id))
    except SQLAlchemyError as exc:
        db.rollback()
        _log_db_failure("claim", update_id, exc)
        return UNAVAILABLE


def _reclaim_stale_or_duplicate(db: Session, update_id: int) -> str:
    """Disambiguate a rejected claim: stale-crash reclaim vs duplicate."""
    cutoff = _utcnow() - timedelta(seconds=DEDUP_STALE_SECONDS)
    try:
        result = db.execute(
            update(TelegramWebhookDedup)
            .where(
                TelegramWebhookDedup.update_id == update_id,
                TelegramWebhookDedup.status == _STATUS_PROCESSING,
                TelegramWebhookDedup.processed_at < cutoff,
            )
            .values(processed_at=_utcnow())
            .execution_options(synchronize_session=False)
        )
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        _log_db_failure("stale-reclaim", update_id, exc)
        return UNAVAILABLE

    if result.rowcount == 1:
        logger.warning(
            "Telegram webhook dedup reclaimed stale claim "
            "update_id=%s stale_after_seconds=%s",
            update_id,
            DEDUP_STALE_SECONDS,
        )
        return CLAIMED
    return DUPLICATE


def mark_processed(db: Session, update_id: int | None) -> None:
    """Flip the claim to 'processed' (best effort, never raises).

    If this fails the row stays 'processing' and the stale-reclaim path
    remains available; nothing is lost.
    """
    if update_id is None:
        return
    try:
        db.execute(
            update(TelegramWebhookDedup)
            .where(TelegramWebhookDedup.update_id == int(update_id))
            .values(status=_STATUS_PROCESSED, processed_at=_utcnow())
            .execution_options(synchronize_session=False)
        )
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        _log_db_failure("mark-processed", update_id, exc)


def release_claim(db: Session, update_id: int | None) -> None:
    """Delete the claim so a redelivery of this update is reprocessed.

    Best effort, never raises. Call on ANY failure path after a
    successful claim (handler exception, HTTP error response) —
    otherwise the failed update would be suppressed forever.
    """
    if update_id is None:
        return
    try:
        db.execute(
            delete(TelegramWebhookDedup).where(
                TelegramWebhookDedup.update_id == int(update_id)
            )
        )
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        _log_db_failure("release", update_id, exc)


def reset_ledger(db: Session, *, commit: bool = True) -> int:
    """Delete EVERY ledger row. Returns the number of deleted rows.

    Telegram update_id sequences are PER BOT. When the configured bot is
    replaced, rows retained from the previous bot can make a legitimate
    update of the replacement bot look duplicate — silently skipped and
    ACKed (the ledger key is update_id alone). Callers wipe the ledger
    whenever the bot identity changes:

    - the token write path clears it IN THE SAME TRANSACTION as the
      credential swap (``commit=False`` — atomic with the change);
    - the polling worker clears it whenever it resets its offset after
      detecting a credential change (the ledger and the offset are both
      cursors of the superseded bot).

    With ``commit=True`` (standalone use) the delete commits on its own
    and follows the module's fail-open contract: a failure is logged and
    returns 0 — the retention sweep bounds any staleness. With
    ``commit=False`` the DELETE stays pending in the caller's transaction
    (and errors propagate — the caller owns the transaction).
    """
    try:
        result = db.execute(delete(TelegramWebhookDedup))
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
