"""NURSE-V2 N2-2 — nurse workplace assignments (owner design-GO 2026-09-19).

D2 FINAL (owner, verbatim intent): a Nurse may hold SEVERAL active
assignments (one per QueueResource), and one QueueResource may be served
by several Nurses; at most ONE ACTIVE assignment per
(user_id, queue_resource_id) pair — enforced by the partial unique index
``uq_nurse_workplace_assignments_active_pair`` (migration 0071). The
partial index is deliberately declared ONLY in the Alembic revision
(``postgresql_where`` is PG-only DDL, the queue_entries 0065 precedent):
it is absent from ``__table_args__`` so SQLite create_all paths (test
conftest) keep the plain behavior; the pair-uniqueness contract is
asserted on real PostgreSQL by the N2-2 migration test.

Entity separation (product contract of the track):
- Nurse User = WHO works (users row, role 'Nurse');
- QueueResource = WHICH queue/cabinet is served (reference registry,
  never a login, never a human);
- NurseWorkplaceAssignment = WHERE this Nurse is allowed to work.

``cabinet_override`` is the station/cabinet for THIS assignment; NULL
falls back to ``QueueResource.default_cabinet``. Inactive assignments
are historical records (not drift): deactivation keeps the row, and a
new active row for the same pair may be created afterwards — exactly
what the partial (WHERE is_active) uniqueness permits.

No serving permission is granted by this model: N2-3 authorization is
assignment-scoped and arrives in a later slice.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class NurseWorkplaceAssignment(Base):
    """Where a Nurse User is allowed to work (NURSE-V2 N2-2)."""

    __tablename__ = "nurse_workplace_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # WHO works — a real human account with the canonical role 'Nurse'.
    # The assignment boundary validates role + is_active at the service
    # layer (user_management vocabulary admits 'Nurse' since N2-2).
    # NO ACTION FK: deleting a referenced user with live assignment
    # history must fail (0008/0054 owner-FK convention).
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    # WHICH queue/resource is served — reference registry row, never a
    # login. NO ACTION FK: deleting a referenced resource with live
    # assignment history must fail.
    queue_resource_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("queue_resources.id"),
        nullable=False,
        index=True,
    )

    # WHERE: station/cabinet override for this assignment; NULL means
    # fall back to QueueResource.default_cabinet (D2 FINAL).
    cabinet_override: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Active flag: False = historical record (kept, never deleted);
    # re-assignment creates a NEW active row for the same pair.
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=True,
    )
