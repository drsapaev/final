"""NURSE-V2 N2-2 — per-service execution facts (owner design-GO 2026-09-19).

D1 FINAL (owner): a SEPARATE entity — execution status is NOT added to
``visit_services`` (that row is the commercial/ordered line — qty is the
billed quantity, NOT a proven count of separate clinical sessions; no
execution rows are auto-created from ``qty``). Rationale recorded by the
owner: ``qty > 1`` is reachable by ordinary write paths; incomplete needs
a retry WITHOUT losing history; one service may be started by one Nurse
and finished by another; actual execution needs idempotency and audit.

Semantics:
- One row = one ATTEMPT to actually perform a concrete VisitService.
  A retry after ``incomplete`` creates a NEW row with
  ``attempt_no = previous + 1``; the previous attempt is never
  overwritten.
- Statuses (NURSE-V2 first stage): ``in_progress`` / ``completed`` /
  ``incomplete`` / ``cancelled``. ``no_show`` stays a QUEUE-level state
  (online_queue_entries.status) — an execution is created only when the
  service actually starts.
- ``started_by_user_id`` / ``performed_by_user_id`` attribute the
  attempt to REAL users (the plan's §5 "all operations attributed to a
  real User"); ``performed_by_user_id`` is set on completion and MAY
  differ from the starter.
- ``queue_entry_id``: nullable at the schema level (other serving paths
  may not have an entry); the Nurse-serving API (N2-3) is REQUIRED to
  set it — the queue entry is the serving context of the attempt.

DB invariants (migration 0072):
- ``UNIQUE(visit_service_id, attempt_no)`` — declared here AND in the
  migration (plain constraint, works on both SQLite and PostgreSQL).
- partial unique index ``uq_service_executions_one_active`` on
  (visit_service_id) WHERE status = 'in_progress' — at most ONE
  simultaneously active execution per VisitService. PG-only DDL
  (queue_entries 0065 precedent): deliberately absent from
  ``__table_args__`` so SQLite create_all paths keep the plain
  behavior; asserted on real PostgreSQL by the N2-2 migration test.

Creating/completing a ServiceExecution does NOT close the Visit:
``visits.status`` is governed by the visit lifecycle, never by
service-level execution (owner contract: "выполнить услугу" != "закрыть
визит").
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base

# NURSE-V2 first-stage status vocabulary (plain strings — repo style,
# no PG enum). 'no_show' is deliberately absent: it stays a queue-level
# state until the service actually starts.
SERVICE_EXECUTION_STATUSES: tuple[str, ...] = (
    "in_progress",
    "completed",
    "incomplete",
    "cancelled",
)

STATUS_IN_PROGRESS = "in_progress"
STATUS_COMPLETED = "completed"
STATUS_INCOMPLETE = "incomplete"
STATUS_CANCELLED = "cancelled"


class ServiceExecution(Base):
    """One actual attempt to perform a concrete VisitService (NURSE-V2 N2-2)."""

    __tablename__ = "service_executions"

    # The commercial/ordered line this attempt performs. NO ACTION FK:
    # deleting a VisitService with execution history must fail — the
    # audit of what was actually performed outranks the billing line.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    visit_service_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("visit_services.id"),
        nullable=False,
        index=True,
    )

    # The queue-entry serving context (nullable: the Nurse-serving API
    # of N2-3 MUST set it; other future serving paths may lack one).
    # SET NULL: an entry purge must not delete execution history
    # (mirrors the online_queue_entries.visit_id precedent).
    queue_entry_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("queue_entries.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # 1-based attempt ordinal within the VisitService; a retry after
    # 'incomplete' creates a NEW row with attempt_no + 1.
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # in_progress | completed | incomplete | cancelled
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=STATUS_IN_PROGRESS
    )

    # WHO started / performed — real users.id (audit attribution).
    # NO ACTION FKs: deleting a user with execution history must fail.
    started_by_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    performed_by_user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Human-readable reason when status = 'incomplete' (the N2-3 brief
    # will formalize the transition matrix; the column lands now).
    incomplete_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)

    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=True,
    )

    __table_args__ = (
        # One attempt ordinal per billed line — works on SQLite too
        # (asserted by the unit tests); the PG migration declares the
        # same constraint.
        UniqueConstraint(
            "visit_service_id",
            "attempt_no",
            name="uq_service_executions_visit_service_attempt",
        ),
    )
