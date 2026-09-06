"""QueueResource Model — routing owner of doctorless queues (QD-2).

QD-2 replaces the synthetic ``*_resource`` User+Doctor bridge (provisioned
by 0055, demoted to the internal-only 'Resource' sentinel by 0056/0057)
with a dedicated routing entity: a doctorless queue (lab, ecg, ...) is
owned by a ``QueueResource`` row, NOT by a Doctor row. Human doctor
selectors are clean by construction — a QueueResource physically lives in
its own table and can never leak into a Doctor query.

Stage note (QD-2A EXPAND, migration 0058): the table and the
``daily_queues.queue_resource_id`` FK exist, but NO XOR constraint and NO
uniqueness are enforced yet — those land in QD-2D after the backfill
(QD-2B) and the runtime switch (QD-2C) prove the ownership shape. At this
stage every existing daily_queues row is doctor-owned exactly as before,
and the registry is EMPTY (seeding exact doctorless tags is QD-2B; never
auto-inferred — stomatology requires a real dentist, so it never gets a
QueueResource row).

Fields (owner decision, QD-2 FINAL D-spec 2026-09-06):
- ``code`` — stable machine code, UNIQUE (API/config reference);
- ``queue_tag`` — the queue tag this resource owns, UNIQUE (one routing
  owner per doctorless tag — this table IS the explicit registry);
- ``display_name`` — human-facing owner name for queue UI / boards;
- ``active`` — routing availability switch;
- ``start_number_online`` / ``max_online_per_day`` — queue configuration
  carried over from the synthetic Doctor rows (0055 seeded 1/15), so the
  QD-2C resolvers keep the numbering/caps contract without a Doctor;
- ``default_cabinet`` — optional default cabinet for resource queues;
- timestamps.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base_class import Base


class QueueResource(Base):
    """Routing owner of a doctorless queue (lab, ecg, ...)."""

    __tablename__ = "queue_resources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Stable machine code (e.g. "lab") — unique registry key
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    # The queue_tag this resource owns — one routing owner per tag
    queue_tag: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)

    # Human-facing owner name (queue UI, display boards)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)

    # Routing availability
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Queue configuration carried from the synthetic Doctor rows (0055:
    # start_number_online=1, max_online_per_day=15) — QD-2C resolvers read
    # these from QueueResource instead of Doctor.
    start_number_online: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_online_per_day: Mapped[int] = mapped_column(Integer, default=15, nullable=False)

    # Optional default cabinet for resource-owned DailyQueue rows
    default_cabinet: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Timestamps
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
