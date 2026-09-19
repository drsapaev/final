"""Regression: GET /admin/departments tolerates departments with icon=NULL.

QD-0 provisioning (0055) inserts departments with icon=NULL via RAW SQL —
the column is nullable by design. DepartmentResponse.icon was a REQUIRED
str, so one NULL row failed the WHOLE list with a 400 (pydantic str
validation) — the AdminDoctors departments section was broken in production
since the 0055 deploy. The response schema now coerces the cosmetic NULL
to the empty string.
"""

from __future__ import annotations

import sqlalchemy as sa

from app.models.department import Department


def _seed_null_icon_department(db_session) -> None:
    """Reproduce the production state: a RAW-SQL NULL icon (the ORM default
    "folder" fires on INSERT, so the NULL must be applied after the commit)."""
    probe = Department(
        key="icon-null-probe",
        name_ru="ICON NULL probe",
        display_order=99,
        active=True,
    )
    db_session.add(probe)
    db_session.commit()
    db_session.execute(
        sa.update(Department)
        .where(Department.key == "icon-null-probe")
        .values(icon=None)
    )
    db_session.commit()
    db_session.expire_all()


def test_departments_list_tolerates_null_icon(client, auth_headers, db_session) -> None:
    _seed_null_icon_department(db_session)

    response = client.get("/api/v1/admin/departments", headers=auth_headers)
    assert response.status_code == 200, response.text

    rows = [d for d in response.json()["data"] if d["key"] == "icon-null-probe"]
    assert len(rows) == 1, response.json()["data"][:5]
    assert rows[0]["icon"] == ""


def test_departments_list_keeps_present_icon(client, auth_headers, db_session) -> None:
    probe = Department(
        key="icon-present-probe",
        name_ru="ICON present probe",
        display_order=98,
        active=True,
        icon="stethoscope",
    )
    db_session.add(probe)
    db_session.commit()

    response = client.get("/api/v1/admin/departments", headers=auth_headers)
    assert response.status_code == 200, response.text

    rows = [d for d in response.json()["data"] if d["key"] == "icon-present-probe"]
    assert len(rows) == 1
    assert rows[0]["icon"] == "stethoscope"
