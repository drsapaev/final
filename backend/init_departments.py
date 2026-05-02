"""Seed initial departments into the configured database.

Schema ownership belongs to Alembic. Run `alembic upgrade head` before this
helper; it intentionally does not create tables.
"""
from __future__ import annotations

import sys
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


def init_departments() -> bool:
    """Seed departments if the configured database has none yet."""
    from app.db.session import SessionLocal
    from app.models.department import Department

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
    print("Seeding departments...")
    raise SystemExit(0 if init_departments() else 1)
