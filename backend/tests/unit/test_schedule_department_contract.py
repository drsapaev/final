"""Round-9 (codex P2, PR #3340): the schedule readers expose the department
KEY STRING these payloads historically promised — never the SQLAlchemy
`Department` object the `department` relationship attribute now carries for
department-backed rows (which the portal booking persists since round-7/8).

The department FILTERS arrive as the canonical key string too: the previous
`Model.department == "<key>"` comparisons used the relationship attribute and
compiled against `department_id = '<key>'` (int-vs-varchar — no match on
SQLite, an operator error on Postgres)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.department import Department
from app.models.schedule import ScheduleTemplate
from app.models.user import User

# The canonical booking department + the linked-patient JWT identity —
# the same fixtures the portal suite defines (local to that module, so
# they are mirrored here for the schedule-contract coverage).


@pytest.fixture
def portal_department(db_session: Session) -> Department:
    row = db_session.query(Department).filter(Department.key == "cardio").first()
    if not row:
        row = Department(
            key="cardio",
            name_ru="Кардиология",
            name_uz="Kardiologiya",
            active=True,
        )
        db_session.add(row)
        db_session.commit()
        db_session.refresh(row)
    return row


@pytest.fixture
def linked_patient_headers(client: TestClient, db_session: Session, test_patient):
    user = db_session.query(User).filter(User.username == "portal_patient").first()
    if not user:
        user = User(
            username="portal_patient",
            email="portal_patient@test.com",
            hashed_password=get_password_hash("portal123"),
            role="Patient",
            is_active=True,
            is_superuser=False,
        )
        db_session.add(user)
        db_session.flush()
        test_patient.user_id = user.id
        db_session.commit()
        db_session.refresh(user)

    from tests.conftest import mint_access_token

    return {"Authorization": f"Bearer {mint_access_token(user)}"}


def _booking_date() -> date:
    return date.today() + timedelta(days=3)


def _week_start(d: date) -> str:
    monday = d - timedelta(days=d.weekday())
    return monday.strftime("%Y-%m-%d")


def _find_appointment_entry(payload, appointment_id: int):
    days = payload if isinstance(payload, list) else [payload]
    for day in days:
        for entry in day.get("appointments", []):
            if entry["id"] == appointment_id:
                return entry
    return None


class TestScheduleDepartmentKeyContract:
    def test_daily_schedule_appointment_department_is_key_string(
        self,
        client,
        linked_patient_headers,
        db_session,
        admin_auth_headers,
        portal_department,
    ):
        booking_date = _booking_date()
        created = client.post(
            "/api/v1/patients/booking",
            headers={**linked_patient_headers, "Idempotency-Key": "sched-daily-1"},
            json={
                "appointmentDate": booking_date.strftime("%Y-%m-%d"),
                "department": portal_department.key,
            },
        )
        assert created.status_code == 201, created.json()
        appointment_id = created.json()["appointment_id"]

        response = client.get(
            "/api/v1/schedule/daily",
            headers=admin_auth_headers,
            params={"date_str": booking_date.strftime("%Y-%m-%d")},
        )
        assert response.status_code == 200, response.text
        entry = _find_appointment_entry(response.json(), appointment_id)
        assert entry is not None, "the department-backed booking must be listed"
        assert entry["department"] == portal_department.key, (
            "the appointment payload exposes the department KEY STRING — "
            "an ORM object leak breaks every string-contract client"
        )

    def test_weekly_schedule_appointment_department_is_key_string(
        self,
        client,
        linked_patient_headers,
        db_session,
        admin_auth_headers,
        portal_department,
    ):
        booking_date = _booking_date()
        created = client.post(
            "/api/v1/patients/booking",
            headers={**linked_patient_headers, "Idempotency-Key": "sched-week-1"},
            json={
                "appointmentDate": booking_date.strftime("%Y-%m-%d"),
                "department": portal_department.key,
            },
        )
        assert created.status_code == 201, created.json()
        appointment_id = created.json()["appointment_id"]

        response = client.get(
            "/api/v1/schedule/weekly",
            headers=admin_auth_headers,
            params={"week_start": _week_start(booking_date)},
        )
        assert response.status_code == 200, response.text
        entry = _find_appointment_entry(response.json(), appointment_id)
        assert entry is not None
        assert entry["department"] == portal_department.key

    def test_department_filter_matches_canonical_key(
        self,
        client,
        linked_patient_headers,
        db_session,
        admin_auth_headers,
        portal_department,
    ):
        booking_date = _booking_date()
        created = client.post(
            "/api/v1/patients/booking",
            headers={**linked_patient_headers, "Idempotency-Key": "sched-filter-1"},
            json={
                "appointmentDate": booking_date.strftime("%Y-%m-%d"),
                "department": portal_department.key,
            },
        )
        assert created.status_code == 201, created.json()
        appointment_id = created.json()["appointment_id"]
        headers = admin_auth_headers

        hit = client.get(
            "/api/v1/schedule/daily",
            headers=headers,
            params={
                "date_str": booking_date.strftime("%Y-%m-%d"),
                "department": portal_department.key,
            },
        )
        assert hit.status_code == 200, hit.text
        assert _find_appointment_entry(hit.json(), appointment_id) is not None, (
            "the canonical key filter must match the department-backed row "
            "(the relationship comparison never did)"
        )

        miss = client.get(
            "/api/v1/schedule/daily",
            headers=headers,
            params={
                "date_str": booking_date.strftime("%Y-%m-%d"),
                "department": "no-such-department",
            },
        )
        assert miss.status_code == 200, miss.text
        assert _find_appointment_entry(miss.json(), appointment_id) is None

    def test_available_slots_expose_department_key_and_filter(
        self, client, db_session, admin_auth_headers, portal_department
    ):
        booking_date = _booking_date()
        template = ScheduleTemplate(
            department_id=portal_department.id,
            weekday=booking_date.weekday(),
            start_time="09:00",
            end_time="11:00",
            active=True,
        )
        db_session.add(template)
        db_session.commit()
        headers = admin_auth_headers

        response = client.get(
            "/api/v1/schedule/available-slots",
            headers=headers,
            params={
                "date_str": booking_date.strftime("%Y-%m-%d"),
                "department": portal_department.key,
            },
        )
        assert response.status_code == 200, response.text
        slots = response.json()
        assert slots, "the canonical key filter must surface the template's slots"
        assert all(slot["department"] == portal_department.key for slot in slots), (
            "slot payloads carry the department KEY string"
        )

        empty = client.get(
            "/api/v1/schedule/available-slots",
            headers=headers,
            params={
                "date_str": booking_date.strftime("%Y-%m-%d"),
                "department": "no-such-department",
            },
        )
        assert empty.status_code == 200, empty.text
        assert empty.json() == []

    def test_schedule_list_dto_department_is_key_string(
        self, client, db_session, admin_auth_headers, portal_department
    ):
        row = ScheduleTemplate(
            department_id=portal_department.id,
            weekday=0,
            start_time="10:00",
            end_time="12:00",
            active=True,
        )
        db_session.add(row)
        db_session.commit()
        db_session.refresh(row)

        response = client.get("/api/v1/schedule", headers=admin_auth_headers)
        assert response.status_code == 200, response.text
        mine = [r for r in response.json() if r["id"] == row.id]
        assert mine, "the department-backed template must be listed"
        assert mine[0]["department"] == portal_department.key

    def test_create_template_resolves_department_key(
        self, client, db_session, admin_auth_headers, portal_department
    ):
        headers = admin_auth_headers
        payload = {
            "department": portal_department.key,
            "weekday": 2,
            "start_time": "08:00",
            "end_time": "10:00",
            "active": True,
        }
        created = client.post("/api/v1/schedule", headers=headers, json=payload)
        assert created.status_code == 200, created.text
        row = db_session.get(ScheduleTemplate, created.json()["id"])
        assert row is not None
        assert row.department_id == portal_department.id, (
            "the create path persists the department FK from the key string"
        )
        assert created.json()["department"] == portal_department.key

        unknown = client.post(
            "/api/v1/schedule",
            headers=headers,
            json={**payload, "department": "no-such-department"},
        )
        assert unknown.status_code == 400, unknown.text
        assert unknown.json()["detail"]["reason"] == "department_unknown"
