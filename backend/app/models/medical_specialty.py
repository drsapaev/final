"""Medical Specialty Catalog model.

Owner decision 2026-09-01 (prerequisite for canonical doctor onboarding):
``medical_specialties`` is the runtime SSOT for the specialty vocabulary
selectable at NEW doctor onboarding. It is a validation/source-of-options
layer only — ``Doctor.specialty`` stays a plain string; an FK is a separate
future architectural decision.

Domain rules pinned by the owner:
- ``active`` means "available for NEW assignment/onboarding". Deactivating a
  specialty NEVER touches existing doctors, visits, EMR or queues.
- The catalog stores CANONICAL codes only: the "general" incomplete sentinel
  and legacy dental-family aliases are never seeded here.
- Not derived from Department / QueueProfile / queue_tags — separate domains.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class MedicalSpecialty(Base):
    """Catalog row for a medical specialty (canonical code + display titles)."""

    __tablename__ = "medical_specialties"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # Canonical domain id — the exact value stored in Doctor.specialty.
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    title_ru: Mapped[str] = mapped_column(String(200), nullable=False)
    title_uz: Mapped[str | None] = mapped_column(String(200), nullable=True)
    title_en: Mapped[str] = mapped_column(String(200), nullable=True)
    # Selectable for NEW doctor onboarding. See module docstring for the
    # strict no-cascade semantics when set to false.
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=True,
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<MedicalSpecialty code={self.code!r} active={self.active}>"
