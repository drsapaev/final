"""PR-3: Telegram webhook update_id dedup table (P1-9 completion).

Both ingress paths for bot updates — the POST /telegram/webhook endpoint
and the long-polling worker — can receive the same update_id more than
once (Telegram re-delivers whenever a delivery is not ACKed in time).
This table is the dedup ledger.

Row lifecycle:
- A claim INSERTs a row with status='processing'. The UNIQUE index on
  update_id (uq_telegram_webhook_dedup_update_id) makes the claim atomic:
  two concurrent deliveries cannot both win.
- After the handler succeeds the row is flipped to 'processed'.
- On handler failure the row is deleted, so Telegram's redelivery is
  reprocessed instead of suppressed forever (at-least-once semantics).
- A row stranded in 'processing' by a hard crash is reclaimable by a
  later delivery of the same update_id after the stale threshold
  (app.services.telegram_webhook_dedup.DEDUP_STALE_SECONDS).
- Rows are purged after DEDUP_RETENTION_DAYS by the daily data-retention
  sweep (app.services.data_retention).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TelegramWebhookDedup(Base):
    """Prevents duplicate processing of the same Telegram update_id."""

    __tablename__ = "telegram_webhook_dedup"
    __table_args__ = (
        # Unique — not just an index: the claim must fail, not silently
        # coexist, when a concurrent delivery inserts the same update_id.
        Index("uq_telegram_webhook_dedup_update_id", "update_id", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # BigInteger: Telegram update_ids are a growing per-bot sequence and
    # can exceed the PostgreSQL INT4 range.
    update_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), default="processing", nullable=False
    )
