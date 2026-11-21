"""Encrypted Click observations; none of these rows authorize a debit."""
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


class ClickReceiptKeyVersion(Base):
    __tablename__ = "click_receipt_key_versions"
    __table_args__ = (
        CheckConstraint("length(version) BETWEEN 1 AND 32", name="ck_click_key_version"),
        CheckConstraint("length(commitment) = 64", name="ck_click_key_commitment"),
    )
    version: Mapped[str] = mapped_column(String(32), primary_key=True)
    commitment: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ClickCallbackReceipt(Base):
    __tablename__ = "click_callback_receipts"
    __table_args__ = (
        UniqueConstraint("event_key", "body_digest", name="uq_click_receipt_body"),
        UniqueConstraint("event_key", "variant_slot", name="uq_click_receipt_slot"),
        CheckConstraint("length(event_key) = 64 AND length(body_digest) = 64", name="ck_click_receipt_hashes"),
        CheckConstraint("variant_slot >= 0 AND variant_slot < 32", name="ck_click_receipt_slot"),
        CheckConstraint("phase IN ('prepare', 'complete')", name="ck_click_receipt_phase"),
        CheckConstraint("confidence IN ('authenticated', 'probable')", name="ck_click_receipt_confidence"),
        CheckConstraint("media_type IN ('application/json', 'application/x-www-form-urlencoded')", name="ck_click_receipt_media"),
        CheckConstraint("body_size > 0 AND body_size <= 262144", name="ck_click_receipt_size"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    body_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    variant_slot: Mapped[int] = mapped_column(Integer, nullable=False)
    phase: Mapped[str] = mapped_column(String(8), nullable=False)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False)
    media_type: Mapped[str] = mapped_column(String(64), nullable=False)
    body_size: Mapped[int] = mapped_column(Integer, nullable=False)
    key_version: Mapped[str] = mapped_column(String(32), ForeignKey("click_receipt_key_versions.version", ondelete="RESTRICT"), nullable=False)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
