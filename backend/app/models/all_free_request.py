"""All-free request records; schema alone never authorizes a discount.

Live nullable references are not authority. Writers must verify actor rights,
current target, locked context and all baseline lines, enforce audit integrity,
and fence confirmation and payment before these records can be used.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class AllFreeRequest(Base):
    __tablename__ = "all_free_requests"
    __table_args__ = (
        UniqueConstraint("id", "visit_id_snapshot", name="uq_allfree_request_visit_snapshot"),
        ForeignKeyConstraint(["visit_id", "patient_id", "allfree_encounter_identity"], ["visits.id", "visits.patient_id", "visits.allfree_encounter_identity"], name="fk_allfree_visit_identity", deferrable=True, initially="DEFERRED"),
        Index("uq_allfree_active_visit", "visit_id", unique=True, postgresql_where=text("visit_id IS NOT NULL AND status IN ('pending','approved')"), sqlite_where=text("visit_id IS NOT NULL AND status IN ('pending','approved')")),
        CheckConstraint("visit_id_snapshot > 0 AND patient_id_snapshot > 0 AND requested_by_user_id_snapshot > 0", name="ck_allfree_request_snapshot_ids"),
        CheckConstraint("encounter_id_snapshot IS NULL OR encounter_id_snapshot > 0", name="ck_allfree_encounter_snapshot"),
        CheckConstraint("visit_id IS NULL OR visit_id = visit_id_snapshot", name="ck_allfree_visit_snapshot"),
        CheckConstraint("patient_id IS NULL OR patient_id = patient_id_snapshot", name="ck_allfree_patient_snapshot"),
        CheckConstraint("encounter_id IS NULL OR (encounter_id_snapshot IS NOT NULL AND encounter_id = encounter_id_snapshot)", name="ck_allfree_encounter_live_snapshot"),
        CheckConstraint("visit_id IS NULL OR patient_id IS NOT NULL", name="ck_allfree_live_patient"),
        CheckConstraint("requested_by_user_id IS NULL OR requested_by_user_id = requested_by_user_id_snapshot", name="ck_allfree_requester_snapshot"),
        CheckConstraint("decided_by_user_id IS NULL OR (decided_by_user_id_snapshot IS NOT NULL AND decided_by_user_id = decided_by_user_id_snapshot)", name="ck_allfree_decider_snapshot"),
        CheckConstraint("visit_context_epoch > 0 AND (decision_context_epoch IS NULL OR decision_context_epoch > 0) AND (encounter_generation IS NULL OR encounter_generation > 0)", name="ck_allfree_epochs"),
        CheckConstraint("baseline_total >= 0 AND baseline_total <= 9999999999.99 AND baseline_total = round(baseline_total, 2)", name="ck_allfree_baseline"),
        CheckConstraint("status IN ('pending','approved','rejected','invalidated')", name="ck_allfree_status"),
        CheckConstraint("decision_kind IS NULL OR decision_kind IN ('admin','policy')", name="ck_allfree_decision_kind"),
        CheckConstraint("length(trim(requested_by_role_snapshot)) > 0", name="ck_allfree_requester_role"),
        CheckConstraint("policy_auto_approve IN (TRUE, FALSE)", name="ck_allfree_policy_boolean"),
        CheckConstraint("decided_by_user_id_snapshot IS NULL OR decided_by_user_id_snapshot > 0", name="ck_allfree_decider_id"),
        CheckConstraint("status NOT IN ('approved','rejected') OR (decision_kind IS NOT NULL AND decided_at IS NOT NULL)", name="ck_allfree_decision_recorded"),
        CheckConstraint("decision_kind != 'admin' OR (decided_by_user_id_snapshot IS NOT NULL AND decided_by_role_snapshot IS NOT NULL AND length(trim(decided_by_role_snapshot)) > 0)", name="ck_allfree_admin_decision_actor"),
        CheckConstraint("status != 'rejected' OR decision_kind = 'admin'", name="ck_allfree_reject_admin"),
        CheckConstraint("decision_kind != 'policy' OR policy_auto_approve", name="ck_allfree_policy_decision"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    visit_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("visits.id", ondelete="SET NULL"))
    patient_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("patients.id", ondelete="SET NULL"))
    encounter_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("encounters.id", ondelete="SET NULL"))
    allfree_encounter_identity: Mapped[str | None] = mapped_column(
        String(24), Computed("CASE WHEN encounter_id IS NULL THEN 'N' ELSE 'I' || CAST(encounter_id AS TEXT) END", persisted=True)
    )
    visit_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    patient_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    encounter_id_snapshot: Mapped[int | None] = mapped_column(Integer)
    visit_context_epoch: Mapped[int] = mapped_column(BigInteger, nullable=False)
    decision_context_epoch: Mapped[int | None] = mapped_column(BigInteger)
    encounter_generation: Mapped[int | None] = mapped_column(BigInteger)
    baseline_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="pending")
    requested_by_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    requested_by_user_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    requested_by_role_snapshot: Mapped[str] = mapped_column(String(32), nullable=False)
    policy_auto_approve: Mapped[bool] = mapped_column(Boolean, nullable=False)
    decision_kind: Mapped[str | None] = mapped_column(String(16))
    decided_by_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    decided_by_user_id_snapshot: Mapped[int | None] = mapped_column(Integer)
    decided_by_role_snapshot: Mapped[str | None] = mapped_column(String(32))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AllFreeRequestLine(Base):
    __tablename__ = "all_free_request_lines"
    __table_args__ = (
        Index("ix_allfree_lines_request", "request_id"),
        UniqueConstraint("request_id", "visit_service_id_snapshot", name="uq_allfree_request_line"),
        ForeignKeyConstraint(["request_id", "visit_id_snapshot"], ["all_free_requests.id", "all_free_requests.visit_id_snapshot"], name="fk_allfree_line_request_visit", deferrable=True, initially="DEFERRED"),
        ForeignKeyConstraint(["visit_service_id", "visit_id_snapshot", "service_id_snapshot"], ["visit_services.id", "visit_services.visit_id", "visit_services.service_id"], name="fk_allfree_line_visit_service", deferrable=True, initially="DEFERRED"),
        CheckConstraint("visit_id_snapshot > 0 AND visit_service_id_snapshot > 0 AND service_id_snapshot > 0", name="ck_allfree_line_snapshot_ids"),
        CheckConstraint("visit_service_id IS NULL OR visit_service_id = visit_service_id_snapshot", name="ck_allfree_line_live_snapshot"),
        CheckConstraint("quantity > 0 AND quantity <= 2147483647 AND quantity = CAST(quantity AS INTEGER)", name="ck_allfree_line_quantity"),
        CheckConstraint("unit_price >= 0 AND unit_price <= 9999999999.99 AND unit_price = round(unit_price, 2)", name="ck_allfree_line_unit"),
        CheckConstraint("gross_amount >= 0 AND gross_amount <= 9999999999.99 AND gross_amount = round(gross_amount, 2) AND round(unit_price * quantity, 2) = gross_amount", name="ck_allfree_line_gross"),
        CheckConstraint("length(trim(currency)) > 0", name="ck_allfree_line_currency"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(Integer, ForeignKey("all_free_requests.id", ondelete="RESTRICT"), nullable=False)
    visit_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    visit_service_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("visit_services.id", ondelete="SET NULL"))
    visit_service_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    service_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)


class AllFreeRequestEvent(Base):
    __tablename__ = "all_free_request_events"
    __table_args__ = (
        Index("ix_allfree_events_request", "request_id"),
        CheckConstraint("event_type IN ('requested','approved','rejected','invalidated')", name="ck_allfree_event_type"),
        CheckConstraint("actor_user_id_snapshot IS NULL OR actor_user_id_snapshot > 0", name="ck_allfree_event_actor_id"),
        CheckConstraint("actor_user_id IS NULL OR (actor_user_id_snapshot IS NOT NULL AND actor_user_id = actor_user_id_snapshot)", name="ck_allfree_event_actor_snapshot"),
        CheckConstraint("length(trim(actor_role_snapshot)) > 0", name="ck_allfree_event_actor_role"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(Integer, ForeignKey("all_free_requests.id", ondelete="RESTRICT"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(24), nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    actor_user_id_snapshot: Mapped[int | None] = mapped_column(Integer)
    actor_role_snapshot: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
