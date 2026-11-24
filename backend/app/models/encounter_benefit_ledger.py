"""Schema-only encounter benefit records.

These tables do not implement authorization, locking, finalized line
closure, append-only enforcement, quotas or generation invalidation. A future
transactional writer must implement those invariants before this ledger is
used to grant or apply a benefit. Snapshot IDs are historical labels, never a
substitute for a live foreign key or authorization check.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class EncounterBenefitApplication(Base):
    """A recorded application occupies the encounter's slot while retained."""

    __tablename__ = "encounter_benefit_applications"
    __table_args__ = (
        UniqueConstraint("encounter_id", name="uq_encounter_benefit_once"),
        Index("uq_enc_benefit_app_identity", "id", "encounter_id", "patient_id", unique=True),
        ForeignKeyConstraint(
            ["encounter_id", "patient_id"], ["encounters.id", "encounters.patient_id"],
            name="fk_enc_benefit_encounter_patient", onupdate="CASCADE",
            deferrable=True, initially="DEFERRED",
        ),
        CheckConstraint("patient_id IS NULL OR patient_id = patient_id_snapshot", name="ck_enc_benefit_patient_snapshot"),
        CheckConstraint("patient_benefit_id IS NULL OR patient_benefit_id = patient_benefit_id_snapshot", name="ck_enc_benefit_assignment_snapshot"),
        CheckConstraint("benefit_id IS NULL OR benefit_id = benefit_id_snapshot", name="ck_enc_benefit_benefit_snapshot"),
        CheckConstraint("approved_by_user_id IS NULL OR approved_by_user_id = approved_by_user_id_snapshot", name="ck_enc_benefit_actor_snapshot"),
        CheckConstraint("patient_id_snapshot > 0 AND patient_benefit_id_snapshot > 0 AND benefit_id_snapshot > 0 AND approved_by_user_id_snapshot > 0", name="ck_enc_benefit_snapshot_ids"),
        CheckConstraint("encounter_generation > 0", name="ck_enc_benefit_generation"),
        CheckConstraint("percentage >= 0 AND percentage <= 100", name="ck_enc_benefit_percentage"),
        CheckConstraint("gross_total >= 0 AND gross_total <= 9999999999.99 AND gross_total = round(gross_total, 2)", name="ck_enc_benefit_gross"),
        CheckConstraint("benefit_total > 0 AND benefit_total <= gross_total AND benefit_total = round(benefit_total, 2)", name="ck_enc_benefit_discount"),
        CheckConstraint("net_total >= 0 AND net_total <= 9999999999.99 AND net_total = round(net_total, 2) AND round(gross_total - benefit_total, 2) = net_total", name="ck_enc_benefit_net"),
        CheckConstraint("max_discount IS NULL OR (max_discount >= 0 AND max_discount <= 9999999999.99 AND max_discount = round(max_discount, 2))", name="ck_enc_benefit_max"),
        CheckConstraint("monthly_limit IS NULL OR (monthly_limit >= 0 AND monthly_limit <= 9999999999.99 AND monthly_limit = round(monthly_limit, 2))", name="ck_enc_benefit_monthly_limit"),
        CheckConstraint("yearly_limit IS NULL OR (yearly_limit >= 0 AND yearly_limit <= 9999999999.99 AND yearly_limit = round(yearly_limit, 2))", name="ck_enc_benefit_yearly_limit"),
        CheckConstraint("monthly_used_before >= 0 AND monthly_used_before <= 9999999999.99 AND monthly_used_before = round(monthly_used_before, 2)", name="ck_enc_benefit_monthly_before"),
        CheckConstraint("yearly_used_before >= 0 AND yearly_used_before <= 9999999999.99 AND yearly_used_before = round(yearly_used_before, 2)", name="ck_enc_benefit_yearly_before"),
        CheckConstraint("length(trim(approved_by_role_snapshot)) > 0", name="ck_enc_benefit_actor_role"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    encounter_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("encounters.id", ondelete="RESTRICT"), nullable=False
    )
    patient_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("patients.id", ondelete="SET NULL"), nullable=True)
    patient_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    patient_benefit_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("patient_benefits.id", ondelete="SET NULL"), nullable=True)
    patient_benefit_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    benefit_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("benefits.id", ondelete="SET NULL"), nullable=True)
    benefit_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    approved_by_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by_user_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    approved_by_role_snapshot: Mapped[str] = mapped_column(String(32), nullable=False)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    period_timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    period_month: Mapped[date] = mapped_column(Date, nullable=False)
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    encounter_generation: Mapped[int] = mapped_column(BigInteger, nullable=False)
    percentage: Mapped[Decimal] = mapped_column(Numeric(7, 4), nullable=False)
    max_discount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    monthly_limit: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    yearly_limit: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    monthly_used_before: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    yearly_used_before: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    gross_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    benefit_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    net_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)


class EncounterBenefitAllocation(Base):
    """One observed eligible line and its monetary allocation."""

    __tablename__ = "encounter_benefit_allocations"
    __table_args__ = (
        UniqueConstraint("application_id", "visit_service_id_snapshot", name="uq_enc_benefit_alloc_line"),
        CheckConstraint("visit_id IS NULL OR visit_id = visit_id_snapshot", name="ck_enc_benefit_alloc_visit_snapshot"),
        CheckConstraint("visit_service_id IS NULL OR visit_service_id = visit_service_id_snapshot", name="ck_enc_benefit_alloc_line_snapshot"),
        CheckConstraint("visit_id_snapshot > 0 AND visit_service_id_snapshot > 0 AND service_id_snapshot > 0", name="ck_enc_benefit_alloc_snapshot_ids"),
        CheckConstraint("visit_context_epoch > 0", name="ck_enc_benefit_alloc_epoch"),
        CheckConstraint("quantity > 0 AND quantity <= 2147483647 AND quantity = CAST(quantity AS INTEGER)", name="ck_enc_benefit_alloc_qty"),
        CheckConstraint("unit_price >= 0 AND unit_price <= 9999999999.99 AND unit_price = round(unit_price, 2)", name="ck_enc_benefit_alloc_unit"),
        CheckConstraint("gross_amount >= 0 AND gross_amount <= 9999999999.99 AND gross_amount = round(gross_amount, 2) AND round(unit_price * quantity, 2) = gross_amount", name="ck_enc_benefit_alloc_gross"),
        CheckConstraint("benefit_amount >= 0 AND benefit_amount <= gross_amount AND benefit_amount = round(benefit_amount, 2)", name="ck_enc_benefit_alloc_discount"),
        CheckConstraint("net_amount >= 0 AND net_amount <= 9999999999.99 AND net_amount = round(net_amount, 2) AND round(gross_amount - benefit_amount, 2) = net_amount", name="ck_enc_benefit_alloc_net"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(Integer, ForeignKey("encounter_benefit_applications.id", ondelete="RESTRICT"), nullable=False, index=True)
    visit_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("visits.id", ondelete="SET NULL"), nullable=True)
    visit_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    visit_service_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("visit_services.id", ondelete="SET NULL"), nullable=True)
    visit_service_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    service_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    visit_context_epoch: Mapped[int] = mapped_column(BigInteger, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    benefit_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    net_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)


class EncounterBenefitVisitSnapshot(Base):
    """Every visit's context, including visits with no eligible line.

    This is evidence for a future authorized benefit writer, never authority
    by itself. Nullable live IDs cannot be reconstructed from snapshots.
    """

    __tablename__ = "encounter_benefit_visit_snapshots"
    __table_args__ = (
        UniqueConstraint("application_id", "visit_id_snapshot", name="uq_enc_benefit_visit_snapshot"),
        ForeignKeyConstraint(
            ["application_id", "encounter_id", "patient_id"],
            ["encounter_benefit_applications.id", "encounter_benefit_applications.encounter_id", "encounter_benefit_applications.patient_id"],
            name="fk_enc_benefit_visit_application_identity", onupdate="CASCADE", deferrable=True, initially="DEFERRED",
        ),
        ForeignKeyConstraint(
            ["visit_id", "patient_id", "encounter_id"], ["visits.id", "visits.patient_id", "visits.encounter_id"],
            name="fk_enc_benefit_visit_live_identity", deferrable=True, initially="DEFERRED",
        ),
        CheckConstraint("visit_id_snapshot > 0 AND visit_context_epoch > 0", name="ck_enc_benefit_visit_context"),
        CheckConstraint("visit_id IS NULL OR visit_id = visit_id_snapshot", name="ck_enc_benefit_visit_live_snapshot"),
        CheckConstraint("visit_id IS NULL OR (encounter_id IS NOT NULL AND patient_id IS NOT NULL)", name="ck_enc_benefit_visit_identity_present"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(Integer, ForeignKey("encounter_benefit_applications.id", ondelete="RESTRICT"), nullable=False, index=True)
    visit_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("visits.id", ondelete="SET NULL"), nullable=True)
    encounter_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    patient_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    visit_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    visit_context_epoch: Mapped[int] = mapped_column(BigInteger, nullable=False)


class EncounterBenefitEvent(Base):
    """A future writer records reversal without releasing the encounter slot."""

    __tablename__ = "encounter_benefit_events"
    __table_args__ = (
        CheckConstraint("event_type IN ('reversed', 'voided', 'corrected')", name="ck_enc_benefit_event_type"),
        CheckConstraint("actor_user_id IS NULL OR actor_user_id = actor_user_id_snapshot", name="ck_enc_benefit_event_actor_snapshot"),
        CheckConstraint("actor_user_id_snapshot > 0 AND length(trim(actor_role_snapshot)) > 0", name="ck_enc_benefit_event_actor"),
        CheckConstraint("length(trim(reason_code)) > 0", name="ck_enc_benefit_event_reason"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(Integer, ForeignKey("encounter_benefit_applications.id", ondelete="RESTRICT"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    actor_user_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_role_snapshot: Mapped[str] = mapped_column(String(32), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class EncounterBenefitQuotaAnchor(Base):
    """Permanent pair-scoped mutex; it is never an entitlement or a balance.

    IDs are snapshots deliberately without cascading FKs: deleting a source
    assignment must not release a historic patient/benefit quota lock.
    """

    __tablename__ = "encounter_benefit_quota_anchors"
    __table_args__ = (
        CheckConstraint("patient_id > 0 AND benefit_id > 0", name="ck_enc_benefit_anchor_positive"),
    )

    patient_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    benefit_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
