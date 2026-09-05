"""CRUD service for the Medical Specialty Catalog (admin-managed).

Contract notes (owner decisions 2026-09-01..05):
- ``code`` is canonical: lowercase identifier, unique. It is stored verbatim
  into ``Doctor.specialty`` by the onboarding flow, so renames of the CODE
  are forbidden after creation (title edits are fine).
- ``active`` = available for NEW doctor onboarding. Deactivation never
  cascades to existing doctors/visits/EMR (no-cascade rule).
- Deletion is forbidden while any Doctor references the code — the endpoint
  deactivates instead; physical delete only for rows never used.
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.clinic import Doctor
from app.models.medical_specialty import MedicalSpecialty

_CODE_RE = re.compile(r"^[a-z][a-z0-9_]{1,99}$")


class SpecialtyCatalogValidationError(ValueError):
    """400-class catalog validation failure."""


class SpecialtyCatalogConflictError(RuntimeError):
    """409-class failure (e.g. deleting a catalog row still referenced)."""


def validate_code(code: str) -> str:
    code = (code or "").strip()
    if not _CODE_RE.match(code):
        raise SpecialtyCatalogValidationError(
            "code: строчные латинские буквы/цифры/подчёркивание, "
            "начинается с буквы (например, cardiology)"
        )
    return code


def list_all(db: Session) -> list[MedicalSpecialty]:
    return list(
        db.execute(
            select(MedicalSpecialty).order_by(
                MedicalSpecialty.sort_order.asc(), MedicalSpecialty.code.asc()
            )
        )
        .scalars()
        .all()
    )


def get_by_code(db: Session, code: str) -> MedicalSpecialty | None:
    return (
        db.execute(select(MedicalSpecialty).where(MedicalSpecialty.code == code))
        .scalars()
        .first()
    )


def create(
    db: Session, *, code: str, title_ru: str,
    title_uz: str | None = None, title_en: str | None = None,
    active: bool = True, sort_order: int = 0,
) -> MedicalSpecialty:
    code = validate_code(code)
    if get_by_code(db, code):
        raise SpecialtyCatalogConflictError(
            f"Специальность '{code}' уже есть в каталоге"
        )
    row = MedicalSpecialty(
        code=code,
        title_ru=(title_ru or "").strip(),
        title_uz=(title_uz or "").strip() or None,
        title_en=(title_en or "").strip() or None,
        active=active,
        sort_order=sort_order,
    )
    if not row.title_ru:
        raise SpecialtyCatalogValidationError("title_ru обязателен")
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update(
    db: Session, code: str, *, title_ru: str | None = None,
    title_uz: str | None = None, title_en: str | None = None,
    active: bool | None = None, sort_order: int | None = None,
) -> MedicalSpecialty | None:
    row = get_by_code(db, code)
    if row is None:
        return None
    if title_ru is not None:
        row.title_ru = title_ru.strip()
    if title_uz is not None:
        row.title_uz = title_uz.strip() or None
    if title_en is not None:
        row.title_en = title_en.strip() or None
    if sort_order is not None:
        row.sort_order = sort_order
    if active is not None:
        row.active = active  # no-cascade: existing doctors untouched
    db.commit()
    db.refresh(row)
    return row


def delete(db: Session, code: str) -> tuple[bool, int]:
    """Physical delete only when NO doctor references the code.

    Returns (deleted, referencing_doctors_count).
    """
    used = (
        db.execute(select(Doctor.id).where(Doctor.specialty == code).limit(1))
        .scalars()
        .first()
    )
    if used is not None:
        return False, 1
    row = get_by_code(db, code)
    if row is None:
        return False, 0
    db.delete(row)
    db.commit()
    return True, 0
