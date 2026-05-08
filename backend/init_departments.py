"""Seed initial departments into the configured database.

Schema ownership belongs to Alembic. Run `alembic upgrade head` before this
helper; it intentionally does not create tables.
"""
from __future__ import annotations

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


INITIAL_DEPARTMENTS = [
    {
        "key": "cardio",
        "name_ru": "Кардиология",
        "name_uz": "Kardiologiya",
        "icon": "heart",
        "display_order": 1,
        "active": True,
    },
    {
        "key": "echokg",
        "name_ru": "ЭКГ",
        "name_uz": "EKG",
        "icon": "activity",
        "display_order": 2,
        "active": True,
    },
    {
        "key": "derma",
        "name_ru": "Дерматология",
        "name_uz": "Dermatologiya",
        "icon": "droplet",
        "display_order": 3,
        "active": True,
    },
    {
        "key": "dental",
        "name_ru": "Стоматология",
        "name_uz": "Stomatologiya",
        "icon": "smile",
        "display_order": 4,
        "active": True,
    },
    {
        "key": "lab",
        "name_ru": "Лаборатория",
        "name_uz": "Laboratoriya",
        "icon": "flask",
        "display_order": 5,
        "active": True,
    },
    {
        "key": "procedures",
        "name_ru": "Процедуры",
        "name_uz": "Protseduralar",
        "icon": "clipboard-list",
        "display_order": 6,
        "active": True,
    },
]


def require_init_departments_confirmation() -> None:
    if os.getenv("CONFIRM_INIT_DEPARTMENTS") != "1":
        raise RuntimeError(
            "Refusing to seed departments. "
            "Set CONFIRM_INIT_DEPARTMENTS=1 only for an explicit catalog seed run."
        )


def require_postgres_database_url() -> None:
    from app.core.config import settings

    database_url = str(settings.DATABASE_URL).strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL must be set before seeding departments.")
    if database_url.lower().startswith("sqlite"):
        raise RuntimeError("init_departments.py requires a PostgreSQL DATABASE_URL.")


def init_departments() -> bool:
    """Seed departments if the configured database has none yet."""
    require_init_departments_confirmation()
    require_postgres_database_url()

    from app.db.session import SessionLocal
    from app.models.department import Department

    print("Seeding departments...")
    db = SessionLocal()
    try:
        existing_count = db.query(Department).count()
        if existing_count > 0:
            print(f"Departments already exist ({existing_count} records)")
            return True

        for department_data in INITIAL_DEPARTMENTS:
            db.add(Department(**department_data))

        db.commit()
        print(f"Created {len(INITIAL_DEPARTMENTS)} departments")

        departments = db.query(Department).order_by(Department.display_order).all()
        for department in departments:
            print(
                f"   {department.display_order}. "
                f"{department.key}: {department.name_ru} ({department.icon})"
            )
        return True

    except Exception as exc:
        print(f"Department seed failed: {exc}")
        db.rollback()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(0 if init_departments() else 1)
