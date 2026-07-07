"""SQLAlchemy model for cardio_ecg_records.

R-11 / P-003 (UX audit): backs the GET/POST /cardio/ecg endpoints that were
previously stubs returning `[]` and a fake `{id: 1}`. Each row links a
File (uploaded via /files/upload by ECGViewer) to a patient/visit and
stores the parsed ECG parameters (heart_rate, PR, QRS, QT, rhythm,
ST-segment, T-wave) plus an interpretation note.
"""

from __future__ import annotations

from datetime import date, datetime, UTC
from typing import Any

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class CardioECGRecord(Base):
    """A parsed ECG record linked to a patient/visit and an optional source file.

    The file itself is stored in the existing `files` table (uploaded by the
    frontend's ECGViewer via /files/upload). This table only stores the
    *parsed parameters* + interpretation, so the doctor can browse the ECG
    history without re-parsing the binary source.
    """

    __tablename__ = "cardio_ecg_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    visit_id: Mapped[int | None] = mapped_column(
        ForeignKey("visits.id", ondelete="SET NULL"), nullable=True, index=True
    )
    doctor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # RESTRICT: never silently lose the source file behind an ECG record.
    file_id: Mapped[int | None] = mapped_column(
        ForeignKey("files.id", ondelete="RESTRICT"), nullable=True, index=True
    )

    ecg_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # Parsed parameters (mirrors ECGParser.jsx output).
    heart_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    pr_interval: Mapped[float | None] = mapped_column(Float, nullable=True)
    qrs_duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    qt_interval: Mapped[float | None] = mapped_column(Float, nullable=True)
    qt_corrected: Mapped[float | None] = mapped_column(Float, nullable=True)
    rhythm: Mapped[str | None] = mapped_column(String(120), nullable=True)
    st_segment: Mapped[str | None] = mapped_column(String(120), nullable=True)
    t_wave: Mapped[str | None] = mapped_column(String(120), nullable=True)
    axis: Mapped[str | None] = mapped_column(String(60), nullable=True)

    # Free-form interpretation / conclusion by the doctor.
    interpretation: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Provenance: 'device' | 'manual' | 'ai'.
    source: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Catch-all JSON for additional parsed parameters without a migration.
    parameters: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
