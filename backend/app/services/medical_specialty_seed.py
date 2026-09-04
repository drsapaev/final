"""Baseline seed data + deterministic seeder for the Medical Specialty Catalog.

Import-light by design: this module is imported by Alembic migration 0051 and
by test fixtures alike, so it must not import app modules (same contract as
``app.core.specialties``).

Baseline covers the pilot clinic's production reality (DISTINCT
doctors.specialty = cardiology). Canonical codes ONLY: the "general"
incomplete sentinel and legacy dental-family aliases are deliberately absent.

Seeding is deterministic and non-destructive: an existing row with the same
``code`` is never overwritten (``ON CONFLICT (code) DO NOTHING``), so admin-
edited display titles survive re-runs.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text


# (code, title_ru, title_uz, title_en, sort_order)
MEDICAL_SPECIALTY_BASELINE: tuple[tuple[str, str, str | None, str | None, int], ...] = (
    ("cardiology", "Кардиология", "Kardiologiya", "Cardiology", 10),
    ("dermatology", "Дерматология", "Dermatologiya", "Dermatology", 20),
    ("dentistry", "Стоматология", "Stomatologiya", "Dentistry", 30),
)


def seed_medical_specialties(bind: Any) -> int:
    """Idempotently insert missing baseline rows using ``bind`` (a connection).

    Existing rows (by ``code``) are left untouched. Returns the number of
    inserted rows.

    Literals are inlined deliberately: values are static module constants
    (never user input), and inline SQL keeps ``alembic upgrade --sql``
    offline mode correct (bind parameters render as NULL there).
    """
    inserted = 0
    for code, title_ru, title_uz, title_en, sort_order in MEDICAL_SPECIALTY_BASELINE:
        result = bind.execute(
            text(
                f"INSERT INTO medical_specialties "
                f"(code, title_ru, title_uz, title_en, active, sort_order) "
                f"VALUES ('{code}', '{title_ru}', "
                f"{_sql_nullable(title_uz)}, {_sql_nullable(title_en)}, true, {sort_order}) "
                f"ON CONFLICT (code) DO NOTHING"
            )
        )
        inserted += max(getattr(result, "rowcount", 0) or 0, 0)
    return inserted


def _sql_nullable(value: str | None) -> str:
    """Render a nullable title as SQL NULL or a single-quoted literal."""
    if value is None:
        return "NULL"
    return f"'{value}'"
