"""Persistent identity of a patient registration encounter.

Provenance is server-owned. Existing visits whose grouping cannot be proved
are isolated as ``legacy_unresolved`` rather than grouped by payment or time.
The generation is an initial identifier only; it is not yet an entitlement
or pricing-change fence.
"""

from __future__ import annotations

import secrets
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class Encounter(Base):
    __tablename__ = "encounters"
    __table_args__ = (
        UniqueConstraint("id", "patient_id", name="uq_encounters_id_patient"),
        UniqueConstraint("legacy_visit_id", name="uq_encounters_legacy_visit"),
        CheckConstraint("length(trim(provenance)) > 0", name="ck_encounters_provenance_nonempty"),
        # SQLite migration uses atomic AFTER triggers to normalize provenance
        # after patient anonymization; a CHECK would fire too early there.
        CheckConstraint(
            "patient_id IS NOT NULL OR provenance = 'legacy_unresolved'",
            name="ck_encounters_unresolved_patient",
        ).ddl_if(dialect="postgresql"),
        CheckConstraint("generation > 0", name="ck_encounters_generation_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("patients.id", ondelete="SET NULL"), nullable=True, index=True
    )
    provenance: Mapped[str] = mapped_column(String(32), nullable=False)
    # Historical source identity, not a claim that unrelated visits are
    # grouped. It deliberately survives deletion of the source Visit.
    legacy_visit_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    generation: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=lambda: secrets.randbelow(2**52) + 1,
        server_default="1",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
