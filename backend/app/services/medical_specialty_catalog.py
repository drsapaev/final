"""Read layer for the Medical Specialty Catalog.

Runtime SSOT contract (owner decision 2026-09-01): after migration 0051 the
``medical_specialties`` table is the ONLY runtime source of the doctor
onboarding vocabulary. There is deliberately NO hardcoded fallback — an empty
catalog means migrations/seed did not run and must surface as an explicit
configuration error, never as a silent python-tuple registry.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.medical_specialty import MedicalSpecialty


class MedicalSpecialtyCatalogError(RuntimeError):
    """Raised when the catalog is in an unusable configuration state.

    Covers BOTH failure modes of "catalog is not a usable runtime SSOT":
    no active rows (seed/migration never ran) and the table being entirely
    missing (app rollout started before migration 0051) — the latter is a
    raw SQLAlchemyError from the driver, wrapped here so the API layer can
    translate the whole class into the documented 503 instead of a generic
    500 (Codex P2).
    """


class MedicalSpecialtyCatalogService:
    """Read-only accessor for the medical specialty catalog."""

    def __init__(self, db: Session):
        self.db = db

    def list_active(self) -> list[MedicalSpecialty]:
        """Active rows ordered by sort_order, then code (deterministic).

        Raises MedicalSpecialtyCatalogError when the table has no ACTIVE
        rows: that state means migrations/seed never ran — an explicit
        configuration failure instead of a silent fallback.
        """
        try:
            rows = list(
                self.db.execute(
                    select(MedicalSpecialty)
                    .where(MedicalSpecialty.active.is_(True))
                    .order_by(
                        MedicalSpecialty.sort_order.asc(),
                        MedicalSpecialty.code.asc(),
                    )
                )
                .scalars()
                .all()
            )
        except SQLAlchemyError as exc:
            raise MedicalSpecialtyCatalogError(
                "medical_specialties table is unavailable — "
                "migration 0051 has not been applied"
            ) from exc
        if not rows:
            raise MedicalSpecialtyCatalogError(
                "medical_specialties catalog has no active rows — "
                "run Alembic migrations (baseline seed 0051)"
            )
        return rows

    def get_by_code(self, code: str) -> MedicalSpecialty | None:
        """Row by canonical code (active or inactive), or None."""
        return (
            self.db.execute(
                select(MedicalSpecialty).where(MedicalSpecialty.code == code)
            )
            .scalars()
            .first()
        )

    def is_selectable_for_onboarding(self, code: str) -> bool:
        """True iff the code exists AND is active (new-doctor assignment)."""
        row = self.get_by_code(code)
        return bool(row and row.active)
