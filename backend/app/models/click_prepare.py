"""Durable Click phase bindings; these records do not prove settlement."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class ClickIssuedAttempt(Base):
    __tablename__ = "click_issued_attempts"
    __table_args__ = (ForeignKeyConstraint(
        ["attempt_id", "order_ref", "merchant_hash", "fingerprint", "amount_minor", "currency",
         "currency_exponent", "provider", "target_kind", "actor_user_id_snapshot"],
        ["provider_attempts.id", "provider_attempts.order_ref", "provider_attempts.merchant_hash", "provider_attempts.fingerprint",
         "provider_attempts.amount_minor", "provider_attempts.currency", "provider_attempts.currency_exponent",
         "provider_attempts.provider", "provider_attempts.target_kind", "provider_attempts.actor_user_id_snapshot"],
        name="fk_click_issued_attempt_snapshot", ondelete="RESTRICT"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    attempt_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    order_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    merchant_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    amount_minor: Mapped[str] = mapped_column(String(128), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    currency_exponent: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    target_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_user_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    allocations_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ClickPrepare(Base):
    __tablename__ = "click_prepares"
    __table_args__ = (UniqueConstraint("service_id", "click_trans_id", name="uq_click_prepare_service_transaction"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("click_issued_attempts.attempt_id", ondelete="RESTRICT"), nullable=False, unique=True)
    receipt_id: Mapped[int] = mapped_column(ForeignKey("click_callback_receipts.id", ondelete="RESTRICT"), nullable=False, unique=True)
    click_trans_id: Mapped[str] = mapped_column(String(128), nullable=False)
    service_id: Mapped[str] = mapped_column(String(128), nullable=False)
    merchant_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    order_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    amount_minor: Mapped[str] = mapped_column(String(128), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ClickReceiptReconciliationLink(Base):
    __tablename__ = "click_receipt_reconciliation_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    receipt_id: Mapped[int] = mapped_column(ForeignKey("click_callback_receipts.id", ondelete="RESTRICT"), nullable=False, unique=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("provider_reconciliation_events.id", ondelete="RESTRICT"), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
