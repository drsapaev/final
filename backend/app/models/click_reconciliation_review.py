"""Encrypted, append-only administrator evidence; never a paid transition."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class ClickReconciliationReview(Base):
    __tablename__ = "click_reconciliation_reviews"
    __table_args__ = (
        UniqueConstraint("receipt_id", "review_sequence", name="uq_click_review_sequence"),
        CheckConstraint("actor_user_id_snapshot>0 AND (actor_user_id IS NULL OR actor_user_id=actor_user_id_snapshot)", name="ck_click_review_actor"),
        CheckConstraint("review_sequence BETWEEN 1 AND 64", name="ck_click_review_sequence"),
        CheckConstraint("length(receipt_sha256)=64 AND length(event_snapshot_sha256)=64 AND length(target_context_sha256)=64 AND length(proof_sha256)=64", name="ck_click_review_digests"),
        CheckConstraint("receipt_sha256 ~ '^[0-9a-f]{64}$' AND event_snapshot_sha256 ~ '^[0-9a-f]{64}$' AND target_context_sha256 ~ '^[0-9a-f]{64}$' AND proof_sha256 ~ '^[0-9a-f]{64}$'", name="ck_click_review_digest_format_pg").ddl_if(dialect="postgresql"),
        CheckConstraint("receipt_sha256 NOT GLOB '*[^0-9a-f]*' AND event_snapshot_sha256 NOT GLOB '*[^0-9a-f]*' AND target_context_sha256 NOT GLOB '*[^0-9a-f]*' AND proof_sha256 NOT GLOB '*[^0-9a-f]*'", name="ck_click_review_digest_format_sqlite").ddl_if(dialect="sqlite"),
        CheckConstraint("proof_size BETWEEN 1 AND 262144 AND length(proof_ciphertext)=proof_size+16", name="ck_click_review_size"),
        CheckConstraint("source_kind IN ('provider_portal','official_document')", name="ck_click_review_source"),
        CheckConstraint("(result='no_debit' AND reason_code IN ('provider_cancelled','provider_failed')) OR (result='debit_confirmed' AND reason_code='provider_confirmed_debit')", name="ck_click_review_result"),
        CheckConstraint("currency='UZS' AND length(amount_minor) BETWEEN 1 AND 128", name="ck_click_review_amount"),
        CheckConstraint("amount_minor ~ '^(0|[1-9][0-9]*)$'", name="ck_click_review_amount_digits_pg").ddl_if(dialect="postgresql"),
        CheckConstraint("amount_minor NOT GLOB '*[^0-9]*' AND (length(amount_minor)=1 OR substr(amount_minor,1,1)<>'0')", name="ck_click_review_amount_digits_sqlite").ddl_if(dialect="sqlite"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    receipt_id: Mapped[int] = mapped_column(ForeignKey("click_callback_receipts.id", ondelete="RESTRICT"), nullable=False)
    event_id: Mapped[int] = mapped_column(ForeignKey("provider_reconciliation_events.id", ondelete="RESTRICT"), nullable=False)
    issued_attempt_id: Mapped[int] = mapped_column(ForeignKey("click_issued_attempts.id", ondelete="RESTRICT"), nullable=False)
    prepare_id: Mapped[int] = mapped_column(ForeignKey("click_prepares.id", ondelete="RESTRICT"), nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    actor_user_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_role: Mapped[str] = mapped_column(String(32), nullable=False)
    review_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    receipt_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    event_snapshot_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    target_context_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    proof_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    proof_key_version: Mapped[str] = mapped_column(ForeignKey("click_receipt_key_versions.version", ondelete="RESTRICT"), nullable=False)
    proof_ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    proof_size: Mapped[int] = mapped_column(Integer, nullable=False)
    source_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    result: Mapped[str] = mapped_column(String(24), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(32), nullable=False)
    amount_minor: Mapped[str] = mapped_column(String(128), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
