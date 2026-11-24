"""Append-only patient-scoped clinical entries. Visit notes have their own revisions."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class PatientClinicalRevision(Base):
    __tablename__ = "patient_clinical_revisions"
    __table_args__ = (
        UniqueConstraint(
            "entry_id", "version", name="uq_patient_clinical_entry_version"
        ),
        CheckConstraint("version > 0", name="ck_patient_clinical_positive_version"),
        Index("ix_patient_clinical_patient_entry", "patient_id", "entry_id", "version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    entry_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    version: Mapped[int] = mapped_column(nullable=False)
    schema_version: Mapped[int] = mapped_column(default=1, nullable=False)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False
    )
    visit_id: Mapped[int] = mapped_column(
        ForeignKey("visits.id", ondelete="RESTRICT"), nullable=False
    )
    author_id: Mapped[int] = mapped_column(nullable=False)
    source: Mapped[str] = mapped_column(String(24), nullable=False)
    clinical_details: Mapped[dict] = mapped_column(JSON, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
