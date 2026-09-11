"""PR-3: Telegram webhook update_id dedup table (P1-9 completion).

Both ingress paths for bot updates — the POST /telegram/webhook endpoint
and the long-polling worker — can receive the same update_id more than
once (Telegram re-delivers whenever a delivery is not ACKed in time).
This table is the dedup ledger.

The ledger key is (bot_identity, update_id). Telegram update_id
sequences are PER BOT, so a row retained from a previous bot must never
interact with the replacement bot's claims (codex round 20):
``bot_identity`` carries a stable, NON-SECRET per-credential identity
(``telegram_webhook_dedup.ledger_bot_identity`` — a SHA-256 prefix of
the resolved token; never the token itself). Claims whose identity is
NULL (fail-open paths without a resolvable credential) never collide:
unique indexes treat NULLs as distinct, so dedup simply degrades to off
for them instead of suppressing a different bot's updates.

Row lifecycle:
- A claim INSERTs a row with status='processing'. The UNIQUE index on
  (bot_identity, update_id) makes the claim atomic: two concurrent
  deliveries of the same bot cannot both win.
- After the handler succeeds the row is flipped to 'processed'.
- On handler failure the row is deleted, so Telegram's redelivery is
  reprocessed instead of suppressed forever (at-least-once semantics).
- A row stranded in 'processing' by a hard crash is reclaimable through
  a TWO-PHASE window (codex round 35): the first stale contact flips it
  to 'reclaiming' (a grace window with NO re-dispatch — the previous
  handler may still be alive), and only a 'reclaiming' row after a
  SECOND full DEDUP_STALE_SECONDS window is re-claimed ('processing'
  again, fresh owner token).
- Rows are purged after DEDUP_RETENTION_DAYS by the daily data-retention
  sweep (app.services.data_retention); superseded-identity rows simply
  age out.
- Rows are purged after DEDUP_RETENTION_DAYS by the daily data-retention
  sweep (app.services.data_retention); credential swaps additionally
  wipe the ledger (token store) and superseded-identity rows simply
  age out.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Key namespace for claims whose credential could not be resolved. The
# column is NOT NULL: NULLs never collide in a unique index (both
# PostgreSQL and SQLite treat NULLs as distinct), so a NULL would
# silently disable dedup for those claims. "unknown" groups them into
# one namespace instead — the same contract the ledger had before
# identity binding (codex round 20).
UNKNOWN_BOT_IDENTITY = "unknown"


class TelegramWebhookDedup(Base):
    """Prevents duplicate processing of the same Telegram update_id."""

    __tablename__ = "telegram_webhook_dedup"
    __table_args__ = (
        # Unique — not just an index: the claim must fail, not silently
        # coexist, when a concurrent delivery inserts the same
        # (bot_identity, update_id). update_id alone is NOT a key:
        # Telegram sequences are per-bot (codex round 20).
        Index(
            "uq_telegram_webhook_dedup_bot_update_id",
            "bot_identity",
            "update_id",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Stable, non-secret per-credential identity (SHA-256 prefix of the
    # resolved bot token); "unknown" when no credential resolves. NOT
    # NULL — NULLs never collide in a unique index and would silently
    # disable dedup for those claims.
    bot_identity: Mapped[str] = mapped_column(
        String(64), nullable=False, default=UNKNOWN_BOT_IDENTITY
    )
    # BigInteger: Telegram update_ids are a growing per-bot sequence and
    # can exceed the PostgreSQL INT4 range.
    update_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # Ownership token (codex round 29): regenerated on insert AND on
    # stale-reclaim, so a handler whose claim was handed to a later
    # delivery can never mark/release the new owner's row. Fenced
    # mark/release use it; unowned calls (owner_token=None) stay
    # unfenced for tests/ops.
    owner_token: Mapped[str] = mapped_column(
        String(64), nullable=False, default=lambda: uuid.uuid4().hex
    )
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), default="processing", nullable=False
    )
