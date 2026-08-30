"""Round-2 Codex findings (P1 appointment writers + P2 patient selectors).

The appointment eligibility contract must hold across EVERY live writer and
every patient-facing doctor selector — not only the web POST /appointments:

- POST /mobile/appointments/book (mobile booking writer);
- GET /mobile/doctors (mobile booking selector);
- GET /queue/available-specialists (public QR self-registration selector).

An inactive (ghost-mirrored) or incomplete ("general" sentinel) doctor must
be neither bookable nor selectable by patients on any of these surfaces.
"""
from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest

from app.core.security import get_password_hash
from app.models.clinic import Doctor
from app.models.patient import Patient
from app.models.user import User


def _suffix() -> str:
    return uuid4().hex[:10]


def _make_patient_user(db_session) -> tuple[User, Patient]:
    s = _suffix()
    user = User(
        username=f"elg_pt_{s}",
        email=f"elg-pt-{s}@test.local",
        full_name=f"Eligibility Patient {s}",
        hashed_password=get_password_hash("patient123"),
        role="Patient",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    patient = Patient(
        user_id=user.id,
        first_name="Patient",
        last_name=f"Test{s}",
        phone=f"+99890{s[:7]}",
        birth_date=date(1990, 1, 1),
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return user, patient


def _make_doctor(db_session, specialty: str, active: bool = True) -> Doctor:
    s = _suffix()
    user = User(
        username=f"elg_doc_{s}",
        email=f"elg-doc-{s}@test.local",
        full_name=f"Dr. Eligibility {s}",
        hashed_password=get_password_hash("docpass"),
        role="Doctor",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    doctor = Doctor(
        user_id=user.id,
        specialty=specialty,
        active=active,
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return doctor


def _patient_login(client, user: User) -> dict[str, str]:
    response = client.post(
        "/api/v1/authentication/login",
        json={"username": user.username, "password": "patient123"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _admin_headers(client, auth_headers) -> dict:
    return auth_headers


def _deactivate_owner(client, auth_headers, user_id: int) -> None:
    """Deactivate the doctor's owner User via the admin API — the lifecycle
    mirror then deactivates the linked Doctor profile (ghost-doctor
    prevention), which is exactly the state the selectors/writers must
    respect."""
    response = client.put(
        f"/api/v1/users/users/{user_id}",
        json={"is_active": False},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text


class TestMobileBookingEligibility:
    def test_book_deactivated_doctor_rejected(
        self, client, db_session, auth_headers
    ):
        owner = _make_doctor(db_session, "cardiology", active=True)
        patient_user, _ = _make_patient_user(db_session)
        _deactivate_owner(client, auth_headers, owner.user_id)

        headers = _patient_login(client, patient_user)
        response = client.post(
            "/api/v1/mobile/appointments/book",
            json={
                "doctor_id": owner.id,
                "preferred_date": str(date.today() + timedelta(days=2)),
                "complaint": "тест",
            },
            headers=headers,
        )
        assert response.status_code == 409, response.text
        assert "деактивирован" in response.json()["detail"]

    def test_book_incomplete_doctor_rejected(
        self, client, db_session, auth_headers
    ):
        owner = _make_doctor(db_session, "general", active=True)
        patient_user, _ = _make_patient_user(db_session)

        headers = _patient_login(client, patient_user)
        response = client.post(
            "/api/v1/mobile/appointments/book",
            json={
                "doctor_id": owner.id,
                "preferred_date": str(date.today() + timedelta(days=2)),
                "complaint": "тест",
            },
            headers=headers,
        )
        assert response.status_code == 409, response.text
        assert "не завершён" in response.json()["detail"]

    def test_book_eligible_doctor_ok(self, client, db_session, auth_headers):
        owner = _make_doctor(db_session, "cardiology", active=True)
        patient_user, _ = _make_patient_user(db_session)

        headers = _patient_login(client, patient_user)
        response = client.post(
            "/api/v1/mobile/appointments/book",
            json={
                "doctor_id": owner.id,
                "preferred_date": str(date.today() + timedelta(days=2)),
                "complaint": "тест",
            },
            headers=headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body.get("id") is not None
        assert body.get("status") == "scheduled"


class TestPatientFacingSelectors:
    def test_mobile_doctors_hides_incomplete(
        self, client, db_session, auth_headers
    ):
        good = _make_doctor(db_session, "cardiology", active=True)
        incomplete = _make_doctor(db_session, "general", active=True)
        patient_user, _ = _make_patient_user(db_session)

        headers = _patient_login(client, patient_user)
        response = client.get("/api/v1/mobile/doctors", headers=headers)
        assert response.status_code == 200, response.text
        ids = [d["id"] for d in response.json()]
        assert good.id in ids
        assert incomplete.id not in ids, (
            "incomplete ('general' sentinel) doctor must not be offered to "
            "patients in the mobile booking selector"
        )

    def test_available_specialists_hides_inactive_and_incomplete(
        self, client, db_session, auth_headers
    ):
        """Public QR self-registration selector: an inactive (ghost-mirrored)
        or incomplete doctor must not appear as selectable — the queue join
        would reject the same doctor, producing a patient-visible dead end
        (Codex round-2 P2)."""
        good = _make_doctor(db_session, "cardiology", active=True)
        incomplete = _make_doctor(db_session, "general", active=True)
        inactive_owner = _make_doctor(db_session, "dermatology", active=True)
        _deactivate_owner(client, auth_headers, inactive_owner.user_id)

        response = client.get("/api/v1/queue/available-specialists")
        assert response.status_code == 200, response.text
        specialists = response.json()

        # The endpoint may return {"specialists": [...]} or a bare list
        rows = (
            specialists.get("specialists", specialists)
            if isinstance(specialists, dict)
            else specialists
        )
        doctor_ids = {
            row.get("id") if isinstance(row, dict) else None
            for row in rows
        }
        assert good.id in doctor_ids
        assert incomplete.id not in doctor_ids
        assert inactive_owner.id not in doctor_ids


class TestMobileBookingRound3Fixes:
    """Round-3 Codex findings on the repaired mobile booking endpoint:
    slot-occupancy guard, complaint+notes preservation, service persistence."""

    def _book(self, client, headers, doctor_id: int, **overrides) -> dict:
        payload = {
            "doctor_id": doctor_id,
            "preferred_date": str(date.today() + timedelta(days=2)),
            "preferred_time": "10:00",
            "complaint": "болит голова",
            "notes": "аллергия на лидокаин",
        }
        payload.update(overrides)
        return client.post(
            "/api/v1/mobile/appointments/book", json=payload, headers=headers
        )

    def test_book_occupied_slot_rejected(
        self, client, db_session, auth_headers
    ):
        owner = _make_doctor(db_session, "cardiology", active=True)
        patient_user, _ = _make_patient_user(db_session)
        headers = _patient_login(client, patient_user)

        # First booking occupies the slot
        first = self._book(client, headers, owner.id)
        assert first.status_code == 200, first.text

        # Second patient must be rejected for the same doctor/date/time
        other_user, _ = _make_patient_user(db_session)
        other_headers = _patient_login(client, other_user)
        second = self._book(client, other_headers, owner.id)
        assert second.status_code == 409, second.text
        assert "занято" in second.json()["detail"]

    def test_book_preserves_complaint_and_notes(
        self, client, db_session, auth_headers
    ):
        owner = _make_doctor(db_session, "cardiology", active=True)
        patient_user, _ = _make_patient_user(db_session)
        headers = _patient_login(client, patient_user)

        response = self._book(client, headers, owner.id)
        assert response.status_code == 200, response.text

        from app.models.appointment import Appointment

        row = (
            db_session.query(Appointment)
            .filter(Appointment.doctor_id == owner.id)
            .one()
        )
        assert "болит голова" in (row.notes or "")
        assert "аллергия на лидокаин" in (row.notes or "")

    def test_book_persists_requested_services(
        self, client, db_session, auth_headers
    ):
        owner = _make_doctor(db_session, "cardiology", active=True)
        patient_user, _ = _make_patient_user(db_session)

        from app.models.service import Service

        s1 = Service(name="ЭКГ", price=50000)
        s2 = Service(name="Консультация кардиолога", price=150000)
        db_session.add_all([s1, s2])
        db_session.commit()
        db_session.refresh(s1)
        db_session.refresh(s2)

        headers = _patient_login(client, patient_user)
        response = self._book(
            client, headers, owner.id, services=[s1.id, s2.id]
        )
        assert response.status_code == 200, response.text

        from app.models.appointment import Appointment

        row = (
            db_session.query(Appointment)
            .filter(Appointment.doctor_id == owner.id)
            .one()
        )
        assert "ЭКГ" in (row.services or [])
        assert "Консультация кардиолога" in (row.services or [])

    def test_book_unknown_service_rejected(
        self, client, db_session, auth_headers
    ):
        owner = _make_doctor(db_session, "cardiology", active=True)
        patient_user, _ = _make_patient_user(db_session)
        headers = _patient_login(client, patient_user)

        response = self._book(
            client, headers, owner.id, services=[999999]
        )
        assert response.status_code == 400, response.text


class TestMobileBookingRound4Fixes:
    """Round-4 Codex findings: no false slot-conflict for date-only bookings;
    inactive services are unavailable to mobile bookings."""

    def test_date_only_bookings_do_not_conflict(
        self, client, db_session, auth_headers
    ):
        """preferred_time is optional: the occupancy query must be skipped
        when no time was selected — otherwise the FIRST date-only booking
        for a doctor+date (appointment_time IS NULL) would 409 every later
        date-only request although no concrete slot was ever chosen."""
        owner = _make_doctor(db_session, "cardiology", active=True)
        first_user, _ = _make_patient_user(db_session)
        second_user, _ = _make_patient_user(db_session)

        first = client.post(
            "/api/v1/mobile/appointments/book",
            json={
                "doctor_id": owner.id,
                "preferred_date": str(date.today() + timedelta(days=3)),
            },
            headers=_patient_login(client, first_user),
        )
        assert first.status_code == 200, first.text

        second = client.post(
            "/api/v1/mobile/appointments/book",
            json={
                "doctor_id": owner.id,
                "preferred_date": str(date.today() + timedelta(days=3)),
            },
            headers=_patient_login(client, second_user),
        )
        assert second.status_code == 200, second.text + (
            " — date-only bookings must not collide with each other"
        )

    def test_book_inactive_service_rejected(
        self, client, db_session, auth_headers
    ):
        owner = _make_doctor(db_session, "cardiology", active=True)
        patient_user, _ = _make_patient_user(db_session)

        from app.models.service import Service

        inactive = Service(name="Светящаяся аура", price=1000, active=False)
        db_session.add(inactive)
        db_session.commit()
        db_session.refresh(inactive)

        headers = _patient_login(client, patient_user)
        response = client.post(
            "/api/v1/mobile/appointments/book",
            json={
                "doctor_id": owner.id,
                "preferred_date": str(date.today() + timedelta(days=3)),
                "services": [inactive.id],
            },
            headers=headers,
        )
        assert response.status_code == 400, response.text
        assert "недоступны" in response.json()["detail"]

    def test_book_active_service_still_persists(
        self, client, db_session, auth_headers
    ):
        owner = _make_doctor(db_session, "cardiology", active=True)
        patient_user, _ = _make_patient_user(db_session)

        from app.models.service import Service

        active = Service(name="УЗИ сердца", price=200000, active=True)
        db_session.add(active)
        db_session.commit()
        db_session.refresh(active)

        headers = _patient_login(client, patient_user)
        response = client.post(
            "/api/v1/mobile/appointments/book",
            json={
                "doctor_id": owner.id,
                "preferred_date": str(date.today() + timedelta(days=3)),
                "services": [active.id],
            },
            headers=headers,
        )
        assert response.status_code == 200, response.text

        from app.models.appointment import Appointment

        row = (
            db_session.query(Appointment)
            .filter(Appointment.doctor_id == owner.id)
            .one()
        )
        assert row.services == ["УЗИ сердца"]
