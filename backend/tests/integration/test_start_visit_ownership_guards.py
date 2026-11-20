"""REGSTART-BE-001 + DOCSTART-BE-001 (audit #3892 group 24) — start-visit ownership/binding guards.

Two P1 gaps around clinical visit start:

* **REGSTART-BE-001** — `POST /registrar/queue/{entry_id}/start-visit`
  admits Doctor/specialty/Lab roles but loads ANY OnlineQueueEntry by
  global ID and never checks the queue's specialist against the acting
  user: Doctor A (cardiology) can start Doctor B's (dentistry) queue
  entry and flip B's visit to in_progress. The doctor-panel route already
  enforces owner/same-specialty (403) — the legacy registrar route must
  mirror it for non-Admin/Registrar callers.
* **DOCSTART-BE-001** — the doctor start path resolves the visit via
  ``_resolve_entry_visit``'s visit_id-first branch, which trusts
  ``queue_entry.visit_id`` WITHOUT comparing ``visit.patient_id`` to
  ``queue_entry.patient_id``: an inconsistent historic/imported link lets
  a doctor put P2's visit in progress from P1's queue entry. The
  registrar route already rejects this with 409 — doctor start must too.

Both fixes: deny (403/409) with NO state mutation; Admin/Registrar and
correctly-bound flows stay green.

Run: pytest backend/tests/integration/test_start_visit_ownership_guards.py -v
"""
from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from app.core.security import get_password_hash
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.patient import Patient
from app.models.user import User
from app.models.visit import Visit


def _mk_user(db, *, role: str = "Doctor") -> User:
    suffix = uuid4().hex[:8]
    user = User(
        username=f"{role.lower()}_{suffix}",
        email=f"{role.lower()}_{suffix}@t.local",
        full_name=f"Test {role}",
        hashed_password=get_password_hash("doctor123"),
        role=role,
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    db.flush()
    return user


def _mk_doctor(db, user: User, specialty: str) -> Doctor:
    doctor = Doctor(user_id=user.id, specialty=specialty, active=True)
    db.add(doctor)
    db.flush()
    return doctor


def _mk_patient(db) -> Patient:
    suffix = uuid4().hex[:8]
    patient = Patient(
        last_name="Тестов", first_name="Пациент", birth_date=date(1990, 1, 1),
        sex="M",
        # synthetic fixed phone — no real-looking numbers in fixtures
        phone="+998900000000",
        email=f"p_{suffix}@t.local",
        is_deleted=False,
    )
    db.add(patient)
    db.flush()
    return patient


def _mk_visit(db, patient: Patient, doctor: Doctor, *, status: str = "open") -> Visit:
    visit = Visit(
        patient_id=patient.id,
        doctor_id=doctor.id,
        visit_date=date.today(),
        status=status,
        source="desk",
    )
    db.add(visit)
    db.flush()
    return visit


def _mk_queue(db, owner_doctor: Doctor) -> DailyQueue:
    queue = DailyQueue(
        day=date.today(),
        specialist_id=owner_doctor.id,
        queue_tag=f"tag_{uuid4().hex[:8]}",
        active=True,
    )
    db.add(queue)
    db.flush()
    return queue


def _mk_entry(db, queue: DailyQueue, patient: Patient, *, visit: Visit | None,
              number: int, status: str = "called") -> OnlineQueueEntry:
    entry = OnlineQueueEntry(
        queue_id=queue.id,
        number=number,
        patient_id=patient.id,
        visit_id=visit.id if visit else None,
        status=status,
    )
    db.add(entry)
    db.flush()
    return entry


def _login(client, user: User) -> dict[str, str]:
    response = client.post(
        "/api/v1/authentication/login",
        json={"username": user.username, "password": "doctor123"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _entry_state(db, entry_id: int):
    e = db.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).first()
    db.refresh(e)
    return e.status


def _visit_state(db, visit_id: int):
    v = db.query(Visit).filter(Visit.id == visit_id).first()
    db.refresh(v)
    return v.status


@pytest.mark.integration
class TestRegistrarStartVisitOwnership:
    def test_foreign_doctor_cannot_start_other_doctors_queue(
        self, client, db_session
    ):
        """REGSTART-BE-001 RED: Doctor A (cardiology) must get 403 on
        Doctor B's (dentistry) queue entry — no queue or visit mutation."""
        user_a = _mk_user(db_session)
        doctor_a = _mk_doctor(db_session, user_a, "cardiology")
        user_b = _mk_user(db_session)
        doctor_b = _mk_doctor(db_session, user_b, "dentistry")
        patient = _mk_patient(db_session)
        visit = _mk_visit(db_session, patient, doctor_b)
        queue = _mk_queue(db_session, doctor_b)
        entry = _mk_entry(db_session, queue, patient, visit=visit, number=1)
        db_session.commit()

        headers = _login(client, user_a)
        response = client.post(
            f"/api/v1/registrar/queue/{entry.id}/start-visit", headers=headers
        )

        assert response.status_code == 403, (response.status_code, response.text)
        assert _entry_state(db_session, entry.id) == "called"
        assert _visit_state(db_session, visit.id) == "open"

    def test_owner_and_registrar_still_start(self, client, db_session):
        """Positives: owner doctor B and an Admin/Registrar keep the
        authorized workflow (200 + in_progress)."""
        user_b = _mk_user(db_session)
        doctor_b = _mk_doctor(db_session, user_b, "dentistry")
        registrar = _mk_user(db_session, role="Registrar")
        patient = _mk_patient(db_session)
        queue = _mk_queue(db_session, doctor_b)

        visit_own = _mk_visit(db_session, patient, doctor_b)
        entry_own = _mk_entry(db_session, queue, patient, visit=visit_own, number=1)
        visit_reg = _mk_visit(db_session, patient, doctor_b)
        entry_reg = _mk_entry(db_session, queue, patient, visit=visit_reg, number=2)
        db_session.commit()

        headers_b = _login(client, user_b)
        response = client.post(
            f"/api/v1/registrar/queue/{entry_own.id}/start-visit", headers=headers_b
        )
        assert response.status_code == 200, response.text
        assert _entry_state(db_session, entry_own.id) == "in_progress"
        assert _visit_state(db_session, visit_own.id) == "in_progress"

        headers_reg = _login(client, registrar)
        response = client.post(
            f"/api/v1/registrar/queue/{entry_reg.id}/start-visit", headers=headers_reg
        )
        assert response.status_code == 200, response.text
        assert _entry_state(db_session, entry_reg.id) == "in_progress"

    def test_same_specialty_doctor_may_start(self, client, db_session):
        """Positives: same-specialty fallback mirrors the doctor-panel
        guard — Doctor C (cardiology) may start a cardiology queue."""
        user_a = _mk_user(db_session)
        doctor_a = _mk_doctor(db_session, user_a, "cardiology")
        user_c = _mk_user(db_session)
        doctor_c = _mk_doctor(db_session, user_c, "cardiology")
        patient = _mk_patient(db_session)
        visit = _mk_visit(db_session, patient, doctor_a)
        queue = _mk_queue(db_session, doctor_a)
        entry = _mk_entry(db_session, queue, patient, visit=visit, number=1)
        db_session.commit()

        headers_c = _login(client, user_c)
        response = client.post(
            f"/api/v1/registrar/queue/{entry.id}/start-visit", headers=headers_c
        )
        assert response.status_code == 200, response.text
        assert _visit_state(db_session, visit.id) == "in_progress"


@pytest.mark.integration
class TestDoctorStartVisitPatientBinding:
    def test_inconsistent_link_rejected_no_mutation(self, client, db_session):
        """DOCSTART-BE-001 RED: queue entry belongs to P1 but visit_id
        anchors P2's visit — doctor start must 409 with no mutation."""
        user_d = _mk_user(db_session)
        doctor_d = _mk_doctor(db_session, user_d, "cardiology")
        p1 = _mk_patient(db_session)
        p2 = _mk_patient(db_session)
        v1 = _mk_visit(db_session, p1, doctor_d)
        v2 = _mk_visit(db_session, p2, doctor_d)
        queue = _mk_queue(db_session, doctor_d)
        entry_bad = _mk_entry(db_session, queue, p1, visit=v2, number=1)
        db_session.commit()

        headers = _login(client, user_d)
        response = client.post(
            f"/api/v1/doctor/queue/{entry_bad.id}/start-visit", headers=headers
        )

        assert response.status_code == 409, (response.status_code, response.text)
        assert _visit_state(db_session, v2.id) == "open"
        assert _entry_state(db_session, entry_bad.id) == "called"
        assert _visit_state(db_session, v1.id) == "open"

    def test_correct_binding_starts_own_visit(self, client, db_session):
        """Positive: the correct P1↔V1 binding starts V1 normally."""
        user_d = _mk_user(db_session)
        doctor_d = _mk_doctor(db_session, user_d, "cardiology")
        p1 = _mk_patient(db_session)
        v1 = _mk_visit(db_session, p1, doctor_d)
        queue = _mk_queue(db_session, doctor_d)
        entry = _mk_entry(db_session, queue, p1, visit=v1, number=1)
        db_session.commit()

        headers = _login(client, user_d)
        response = client.post(
            f"/api/v1/doctor/queue/{entry.id}/start-visit", headers=headers
        )
        assert response.status_code == 200, response.text
        assert _visit_state(db_session, v1.id) == "in_progress"


@pytest.mark.integration
class TestRegistrarStartVisitResourceQueue:
    """REGSTART-BE-001 residual (group95 correction): resource-owned
    DailyQueue rows use specialist_id=NULL (queue_resource_id XOR) and
    previously BYPASSED the #4088 non-operator guard — Doctor/Lab could
    start a resource queue entry and its linked Visit. The canonical
    doctor-panel route denies non-Admin/Registrar there too."""

    def _mk_resource_queue(self, db):
        from app.models.online_queue import QueueResource

        suffix = uuid4().hex[:8]
        resource = QueueResource(
            code=f"res_{suffix}",
            queue_tag=f"rtag_{suffix}",
            display_name="Тестовый ресурс",
            active=True,
        )
        db.add(resource)
        db.flush()
        queue = DailyQueue(
            day=date.today(),
            specialist_id=None,
            queue_resource_id=resource.id,
            queue_tag=f"tag_{suffix}",
            active=True,
        )
        db.add(queue)
        db.flush()
        return queue

    def test_resource_queue_denies_doctor_and_lab(self, client, db_session):
        """RED: Doctor and Lab must get 403 on a resource-owned queue
        entry — no queue or visit mutation."""
        user_a = _mk_user(db_session)
        doctor_a = _mk_doctor(db_session, user_a, "cardiology")
        user_lab = _mk_user(db_session, role="Lab")
        patient = _mk_patient(db_session)
        visit_doc = _mk_visit(db_session, patient, doctor_a)
        visit_lab = _mk_visit(db_session, patient, doctor_a)
        queue = self._mk_resource_queue(db_session)
        entry_doc = _mk_entry(db_session, queue, patient, visit=visit_doc, number=1)
        entry_lab = _mk_entry(db_session, queue, patient, visit=visit_lab, number=2)
        db_session.commit()

        headers_doc = _login(client, user_a)
        response = client.post(
            f"/api/v1/registrar/queue/{entry_doc.id}/start-visit", headers=headers_doc
        )
        assert response.status_code == 403, (response.status_code, response.text)
        assert _entry_state(db_session, entry_doc.id) == "called"
        assert _visit_state(db_session, visit_doc.id) == "open"

        headers_lab = _login(client, user_lab)
        response = client.post(
            f"/api/v1/registrar/queue/{entry_lab.id}/start-visit", headers=headers_lab
        )
        assert response.status_code == 403, (response.status_code, response.text)
        assert _entry_state(db_session, entry_lab.id) == "called"
        assert _visit_state(db_session, visit_lab.id) == "open"

    def test_resource_queue_allows_registrar(self, client, db_session):
        """Positive: Registrar keeps the legacy operator workflow on
        resource-owned queues."""
        registrar = _mk_user(db_session, role="Registrar")
        doctor = _mk_doctor(db_session, _mk_user(db_session), "cardiology")
        patient = _mk_patient(db_session)
        visit = _mk_visit(db_session, patient, doctor)
        queue = self._mk_resource_queue(db_session)
        entry = _mk_entry(db_session, queue, patient, visit=visit, number=1)
        db_session.commit()

        headers = _login(client, registrar)
        response = client.post(
            f"/api/v1/registrar/queue/{entry.id}/start-visit", headers=headers
        )
        assert response.status_code == 200, response.text
        assert _entry_state(db_session, entry.id) == "in_progress"
        assert _visit_state(db_session, visit.id) == "in_progress"
