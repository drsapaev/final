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


class TestScheduleCreateDoctorBoundary:
    """#3402 review round (owner P2-1): the doctor validation previously ran
    only when a department was ALSO supplied — `{"doctor_id": 999999,
    "department": null}` bypassed the controlled `doctor_unknown` 400 and
    died as an FK IntegrityError (500-class) at INSERT time; and even with
    a department the validator never applied the booking ELIGIBILITY
    contract (`ensure_doctor_eligible_for_appointment`), so a deactivated /
    incomplete doctor or a doctor with an inactive / non-doctor owner could
    receive an ACTIVE schedule template and surface in /available-slots
    while patient booking refuses the same doctor. The doctor boundary now
    runs FIRST (canonical lock order doctor → department) and independently
    of the department payload."""

    def _payload(self, **overrides) -> dict:
        payload = {
            "department": None,
            "weekday": 4,
            "start_time": "08:00",
            "end_time": "10:00",
            "active": True,
        }
        payload.update(overrides)
        return payload

    def _template_count(self, db_session) -> int:
        from sqlalchemy import select

        return len(
            db_session.execute(select(ScheduleTemplate)).scalars().all()
        )

    def test_dangling_doctor_id_without_department_is_refused(
        self, client, db_session, admin_auth_headers
    ):
        """The exact review shape: doctor_id set, department null — the
        controlled `doctor_unknown` 400 must fire BEFORE any INSERT, never
        an FK IntegrityError 500 from `crud.create_schedule(...)`."""
        before = self._template_count(db_session)
        refused = client.post(
            "/api/v1/schedule",
            headers=admin_auth_headers,
            json=self._payload(doctor_id=999999),
        )
        assert refused.status_code == 400, refused.text
        assert refused.json()["detail"]["reason"] == "doctor_unknown"
        assert (
            self._template_count(db_session) == before
        ), "a refused create persists nothing"

    def test_deactivated_doctor_is_refused_before_insert(
        self, client, db_session, admin_auth_headers, test_doctor, portal_department
    ):
        """Eligibility must gate the template independent of the department
        payload — pinned for BOTH shapes (department=null and the doctor's
        canonical department): booking refuses an inactive doctor with the
        409 contract, so the schedule must never publish one."""
        test_doctor.active = False
        db_session.commit()

        for department in (None, portal_department.key):
            refused = client.post(
                "/api/v1/schedule",
                headers=admin_auth_headers,
                json=self._payload(department=department, doctor_id=test_doctor.id),
            )
            assert refused.status_code == 409, refused.text
        assert (
            self._template_count(db_session) == 0
        ), "an ineligible doctor must not receive an ACTIVE template"

    def test_incomplete_doctor_profile_is_refused(
        self, client, db_session, admin_auth_headers, cardio_user
    ):
        """The "general" placeholder specialty is the incomplete-profile
        marker the booking contract refuses — the schedule boundary refuses
        it too."""
        from app.models.clinic import Doctor

        doctor = Doctor(
            user_id=cardio_user.id,
            specialty="general",
            active=True,
        )
        db_session.add(doctor)
        db_session.commit()
        db_session.refresh(doctor)

        refused = client.post(
            "/api/v1/schedule",
            headers=admin_auth_headers,
            json=self._payload(doctor_id=doctor.id),
        )
        assert refused.status_code == 409, refused.text
        assert self._template_count(db_session) == 0

    def test_doctor_with_non_doctor_owner_is_refused(
        self, client, db_session, admin_auth_headers
    ):
        """An owner account without a doctor-family role makes the doctor
        ineligible for booking (Codex round-8 P2) — the schedule template
        boundary enforces the same owner contract."""
        from app.core.security import get_password_hash
        from app.models.clinic import Doctor
        from app.models.user import User

        owner = User(
            username="sched_non_doctor_owner",
            email="sched_nda@test.com",
            hashed_password=get_password_hash("x12345678"),
            role="Registrar",
            is_active=True,
            is_superuser=False,
        )
        db_session.add(owner)
        db_session.flush()
        doctor = Doctor(
            user_id=owner.id,
            specialty="Кардиология",
            active=True,
        )
        db_session.add(doctor)
        db_session.commit()
        db_session.refresh(doctor)

        refused = client.post(
            "/api/v1/schedule",
            headers=admin_auth_headers,
            json=self._payload(doctor_id=doctor.id),
        )
        assert refused.status_code == 409, refused.text
        assert self._template_count(db_session) == 0

    def test_eligible_doctor_only_template_is_allowed(
        self, client, db_session, admin_auth_headers, test_doctor
    ):
        """Contract decision: a doctor-only template (department=null) stays
        a legal shape — for an ELIGIBLE doctor (active, completed profile,
        active owner with a doctor-family role)."""
        created = client.post(
            "/api/v1/schedule",
            headers=admin_auth_headers,
            json=self._payload(doctor_id=test_doctor.id),
        )
        assert created.status_code == 200, created.text
        row = db_session.get(ScheduleTemplate, created.json()["id"])
        assert row is not None
        assert int(row.doctor_id) == int(test_doctor.id)
        assert row.department_id is None


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


class TestScheduleReadSideConsistency:
    """Review round 3 (owner P2, #3402): the CREATE boundary validates
    department activity and doctor eligibility under row locks, but a row
    lock cannot outlive its transaction — an admin deactivation committed
    AFTER a template was created must be reflected by the ADVERTISING reads
    (available-slots, doctors/departments listings), while the template row
    itself stays active (deactivation stays reversible). The management
    view (list_schedules) deliberately keeps showing the template so an
    admin can see and re-enable it."""

    @staticmethod
    def _monday() -> date:
        return date.today() + timedelta(days=(1 - date.today().weekday()) % 7)

    @staticmethod
    def _template(db_session, *, department=None, doctor_id=None, weekday=1):
        from app.crud.schedule import create_schedule

        return create_schedule(
            db_session,
            department=department,
            doctor_id=doctor_id,
            weekday=weekday,
            start_time="08:00",
            end_time="10:00",
            room=None,
            capacity_per_hour=None,
            active=True,
        )

    @pytest.fixture
    def eligible_doctor(self, db_session: Session):
        """An eligible doctor (active profile, real specialty, active owner
        with a doctor-family role) — the mirror of the PG harness seeding."""
        from app.models.clinic import Doctor

        owner = User(
            username="rs_doctor_owner",
            email="rs_doctor_owner@test.com",
            hashed_password=get_password_hash("rs_doctor_pass"),
            role="Doctor",
            is_active=True,
            is_superuser=False,
        )
        db_session.add(owner)
        db_session.flush()
        doctor = Doctor(user_id=owner.id, specialty="Кардиология", active=True)
        db_session.add(doctor)
        db_session.commit()
        db_session.refresh(doctor)
        return doctor

    def test_inactive_department_stops_advertising_slots(
        self, db_session: Session, portal_department
    ):
        """The review's exact scenario: a template created while the
        department was active keeps ScheduleTemplate.active=True after the
        admin deactivates the department — available-slots must answer
        empty, and reactivation must restore the slots (non-destructive)."""
        from app.crud.schedule import get_available_slots

        self._template(db_session, department=portal_department.key, weekday=1)
        monday = self._monday()

        before = get_available_slots(
            db_session, target_date=monday, department="cardio"
        )
        assert [s["time"] for s in before] == ["08:00", "09:00"]

        portal_department.active = False
        db_session.commit()

        assert (
            get_available_slots(db_session, target_date=monday, department="cardio")
            == []
        )
        # The read-side exclusion must not destroy data: the template row is
        # still active — the create boundary's row lock never had the power
        # to keep this invariant past commit; the reads now carry it.
        row = (
            db_session.query(ScheduleTemplate)
            .filter(ScheduleTemplate.department_id == portal_department.id)
            .first()
        )
        assert row is not None
        assert row.active is True

        portal_department.active = True
        db_session.commit()
        after = get_available_slots(
            db_session, target_date=monday, department="cardio"
        )
        assert [s["time"] for s in after] == ["08:00", "09:00"]

    def test_inactive_department_hidden_from_advertising_listings(
        self, db_session: Session, portal_department
    ):
        """The doctors/departments listings are DERIVED from active
        templates — which outlive a deactivation — so they must re-check
        Department.active themselves. The management view keeps showing the
        template."""
        from app.crud.schedule import (
            get_departments,
            get_doctors_by_department,
            list_schedules,
        )

        self._template(db_session, department=portal_department.key, weekday=1)

        assert any(d["department"] == "cardio" for d in get_departments(db_session))
        assert any(
            d["department"] == "cardio"
            for d in get_doctors_by_department(db_session)
        )

        portal_department.active = False
        db_session.commit()

        assert not any(
            d["department"] == "cardio" for d in get_departments(db_session)
        )
        assert not any(
            d["department"] == "cardio"
            for d in get_doctors_by_department(db_session)
        )

        rows = list_schedules(db_session, department="cardio")
        assert len(rows) == 1
        assert rows[0].active is True

    def test_ineligible_doctor_template_not_advertised(
        self, db_session: Session, portal_department, eligible_doctor
    ):
        """Differential proof: the doctor leg is PER-TEMPLATE — the pinned
        doctor's template stops advertising while the same department's
        doctorless template keeps its slots."""
        from app.crud.schedule import get_available_slots

        self._template(
            db_session,
            department=portal_department.key,
            doctor_id=eligible_doctor.id,
            weekday=1,
        )
        self._template(db_session, department=portal_department.key, weekday=1)
        monday = self._monday()

        slots = get_available_slots(
            db_session, target_date=monday, department="cardio"
        )
        assert len([s for s in slots if s["doctor_id"] == eligible_doctor.id]) == 2
        assert len([s for s in slots if s["doctor_id"] is None]) == 2

        eligible_doctor.active = False
        db_session.commit()

        slots = get_available_slots(
            db_session, target_date=monday, department="cardio"
        )
        assert [s for s in slots if s["doctor_id"] == eligible_doctor.id] == []
        assert len([s for s in slots if s["doctor_id"] is None]) == 2

    def test_owner_ghost_and_incomplete_specialty_excluded(
        self, db_session: Session, portal_department, eligible_doctor
    ):
        """The legacy-ghost mirrors of the booking eligibility SSOT: an
        owner-deactivated account and the 'general' placeholder specialty
        both make the pinned template unbookable — and thus
        unadvertisable, on slots AND on the doctors listing."""
        from app.crud.schedule import (
            get_available_slots,
            get_doctors_by_department,
        )

        self._template(
            db_session,
            department=portal_department.key,
            doctor_id=eligible_doctor.id,
            weekday=1,
        )
        monday = self._monday()

        assert (
            len(get_available_slots(db_session, target_date=monday, department="cardio"))
            == 2
        )
        listed = {
            d["department"]: [x["id"] for x in d["doctors"]]
            for d in get_doctors_by_department(db_session)
        }
        assert listed.get("cardio") == [eligible_doctor.id]

        owner = db_session.get(User, eligible_doctor.user_id)
        owner.is_active = False
        db_session.commit()
        assert (
            get_available_slots(db_session, target_date=monday, department="cardio")
            == []
        )

        owner.is_active = True
        db_session.commit()
        assert (
            len(get_available_slots(db_session, target_date=monday, department="cardio"))
            == 2
        )

        eligible_doctor.specialty = "general"  # the auto-create placeholder
        db_session.commit()
        assert (
            get_available_slots(db_session, target_date=monday, department="cardio")
            == []
        )
        listed = {
            d["department"]: [x["id"] for x in d["doctors"]]
            for d in get_doctors_by_department(db_session)
        }
        assert listed.get("cardio") == []
