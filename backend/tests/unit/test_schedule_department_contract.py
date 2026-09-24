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
        assert all(
            slot["department"] == portal_department.key for slot in slots
        ), "slot payloads carry the department KEY string"

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
        assert (
            row.department_id == portal_department.id
        ), "the create path persists the department FK from the key string"
        assert created.json()["department"] == portal_department.key

        unknown = client.post(
            "/api/v1/schedule",
            headers=headers,
            json={**payload, "department": "no-such-department"},
        )
        assert unknown.status_code == 400, unknown.text
        assert unknown.json()["detail"]["reason"] == "department_unknown"


class TestScheduleCreateConsistencyContract:
    """Merged-#3340 follow-up (owner P2): the create flow resolved
    `department` and `doctor_id` INDEPENDENTLY, so (a) a DEACTIVATED
    department key produced an ACTIVE template advertising a booking route
    the patient-booking contract refuses with `department_inactive`, and
    (b) a Cardiologist could be scheduled under dentistry — the template
    advertised a doctor/department pair the booking routing refuses with
    `doctor_department_mismatch`. Both shapes are now controlled 400s
    BEFORE any INSERT (unknown → `department_unknown`, inactive →
    `department_inactive`, dangling doctor → `doctor_unknown`, doctor
    without a canonical department → `doctor_department_missing`,
    foreign department → `doctor_department_mismatch`)."""

    def _payload(self, department_key, **overrides) -> dict:
        payload = {
            "department": department_key,
            "weekday": 4,
            "start_time": "08:00",
            "end_time": "10:00",
            "active": True,
        }
        payload.update(overrides)
        return payload

    def test_inactive_department_is_refused_before_insert(
        self, client, db_session, admin_auth_headers, portal_department
    ):
        portal_department.active = False
        db_session.commit()

        refused = client.post(
            "/api/v1/schedule",
            headers=admin_auth_headers,
            json=self._payload(portal_department.key),
        )
        assert refused.status_code == 400, refused.text
        assert refused.json()["detail"]["reason"] == "department_inactive"

        from sqlalchemy import select

        orphans = (
            db_session.execute(
                select(ScheduleTemplate).where(
                    ScheduleTemplate.department_id == portal_department.id
                )
            )
            .scalars()
            .all()
        )
        assert orphans == [], "a refused create persists nothing"

    def test_doctor_department_mismatch_is_refused_before_insert(
        self,
        client,
        db_session,
        admin_auth_headers,
        portal_department,
        test_doctor,
    ):
        from app.models.department import Department as DepartmentModel

        dentistry = DepartmentModel(
            key="dentistry-sched",
            name_ru="Стоматология",
            name_uz="Stomatologiya",
            active=True,
        )
        db_session.add(dentistry)
        db_session.commit()
        db_session.refresh(dentistry)

        # The doctor's CANONICAL department is cardiology — scheduling the
        # cardiologist under dentistry is the contradictory template.
        test_doctor.department_id = portal_department.id
        db_session.commit()

        refused = client.post(
            "/api/v1/schedule",
            headers=admin_auth_headers,
            json=self._payload(dentistry.key, doctor_id=test_doctor.id),
        )
        assert refused.status_code == 400, refused.text
        assert refused.json()["detail"]["reason"] == "doctor_department_mismatch"

        from sqlalchemy import select

        orphans = db_session.execute(select(ScheduleTemplate)).scalars().all()
        assert orphans == [], "the inconsistent template is never persisted"

    def test_doctor_without_department_is_refused(
        self, client, db_session, admin_auth_headers, portal_department, test_doctor
    ):
        test_doctor.department_id = None
        db_session.commit()

        refused = client.post(
            "/api/v1/schedule",
            headers=admin_auth_headers,
            json=self._payload(portal_department.key, doctor_id=test_doctor.id),
        )
        assert refused.status_code == 400, refused.text
        assert refused.json()["detail"]["reason"] == "doctor_department_missing"

    def test_dangling_doctor_id_is_refused_not_500(
        self, client, admin_auth_headers, portal_department
    ):
        refused = client.post(
            "/api/v1/schedule",
            headers=admin_auth_headers,
            json=self._payload(portal_department.key, doctor_id=999999),
        )
        assert refused.status_code == 400, refused.text
        assert refused.json()["detail"]["reason"] == "doctor_unknown"

    def test_matching_doctor_department_is_persisted(
        self,
        client,
        db_session,
        admin_auth_headers,
        portal_department,
        test_doctor,
    ):
        test_doctor.department_id = portal_department.id
        db_session.commit()

        created = client.post(
            "/api/v1/schedule",
            headers=admin_auth_headers,
            json=self._payload(portal_department.key, doctor_id=test_doctor.id),
        )
        assert created.status_code == 200, created.text
        row = db_session.get(ScheduleTemplate, created.json()["id"])
        assert row is not None
        assert int(row.department_id) == int(portal_department.id)
        assert int(row.doctor_id) == int(test_doctor.id)

    def test_doctorless_template_is_unaffected(
        self, client, db_session, admin_auth_headers, portal_department
    ):
        """The consistency check binds doctor+department only when BOTH are
        present — the department-only template shape keeps working."""
        created = client.post(
            "/api/v1/schedule",
            headers=admin_auth_headers,
            json=self._payload(portal_department.key),
        )
        assert created.status_code == 200, created.text
        row = db_session.get(ScheduleTemplate, created.json()["id"])
        assert row is not None
        assert row.doctor_id is None
        assert int(row.department_id) == int(portal_department.id)


class TestCreateSchedulePersistence:
    """Round-10 owner P2 (PR #3340): `create_schedule` stopped at `flush()`
    and the endpoint never COMMITTED — `get_db` only closes the session
    after the response, so production rolled the INSERT back: POST
    /api/v1/schedule answered a serialized ScheduleRowOut (with a generated
    id) for a row that NEVER EXISTED.

    The default harness override shares ONE savepoint session across the
    request and the assertions, which masks exactly this defect — so this
    test runs against its OWN disposable engine (tmp file, isolated from
    the shared harness database: every seeded row is COMMITTED) with a
    PRODUCTION-LIKE get_db (each request opens its own session and
    transaction), then reads the row back through an INDEPENDENT session
    (a fresh connection) after the request dependency has closed its
    session. The unknown-key refusal must stay a rollback (no row)."""

    def test_created_template_survives_the_request_session(self, client, tmp_path):
        import uuid

        from sqlalchemy import create_engine, select
        from sqlalchemy.orm import sessionmaker

        import app.db.base  # noqa: F401 — register every model
        from app.api.deps import get_db as canonical_get_db
        from app.db.base_class import Base
        from app.main import app

        engine = create_engine(
            f"sqlite:///{tmp_path / 'persist.db'}",
            echo=False,
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=engine)
        IndependentSession = sessionmaker(
            autocommit=False, autoflush=False, bind=engine
        )

        # The committed world the request's OWN session will see.
        setup = IndependentSession()
        suffix = uuid.uuid4().hex[:8]
        dept = Department(
            key=f"cardio-persist-{suffix}",
            name_ru="Кардиология (persistence)",
            name_uz="Kardiologiya",
            active=True,
        )
        admin = User(
            username=f"admin_persist_{suffix}",
            email=f"admin_persist_{suffix}@test.com",
            full_name="Admin Persistence",
            hashed_password=get_password_hash("persist123"),
            role="Admin",
            is_active=True,
            is_superuser=False,
        )
        setup.add(dept)
        setup.add(admin)
        setup.commit()
        setup.refresh(dept)
        setup.refresh(admin)
        dept_id = dept.id
        dept_key = dept.key

        from tests.conftest import mint_access_token

        headers = {"Authorization": f"Bearer {mint_access_token(admin)}"}
        setup.close()

        # Production-like dependency: a REAL per-request session (own
        # transaction), closed — not shared — when the request ends.
        def prod_like_get_db():
            session = IndependentSession()
            try:
                yield session
            finally:
                session.close()

        app.dependency_overrides[canonical_get_db] = prod_like_get_db
        try:
            payload = {
                "department": dept_key,
                "weekday": 3,
                "start_time": "09:00",
                "end_time": "11:00",
                "active": True,
            }
            created = client.post("/api/v1/schedule", headers=headers, json=payload)
            assert created.status_code == 200, created.text
            row_id = created.json()["id"]
            assert created.json()["department"] == dept_key

            # The INDEPENDENT session sees ONLY committed rows — this is
            # the read the production deploy would run after the request.
            check = IndependentSession()
            try:
                row = check.get(ScheduleTemplate, row_id)
                assert row is not None, (
                    "the created template must survive the request's "
                    "session close (a real COMMIT, not a flushed INSERT)"
                )
                assert row.department_id == dept_id
                assert row.weekday == 3
                assert row.start_time == "09:00"
            finally:
                check.close()

            # The unknown-key refusal is still a ROLLBACK: no row.
            refused = client.post(
                "/api/v1/schedule",
                headers=headers,
                json={**payload, "department": f"no-such-{suffix}"},
            )
            assert refused.status_code == 400, refused.text
            assert refused.json()["detail"]["reason"] == "department_unknown"

            check = IndependentSession()
            try:
                orphans = (
                    check.execute(
                        select(ScheduleTemplate).where(
                            ScheduleTemplate.department_id.is_(None)
                        )
                    )
                    .scalars()
                    .all()
                )
                assert orphans == [], (
                    "a refused create persists nothing (the 400 keeps its "
                    "rollback semantics)"
                )
            finally:
                check.close()
        finally:
            app.dependency_overrides.pop(canonical_get_db, None)
            engine.dispose()
