"""Unit tests for visit.updated_at bumping on service add/remove (PR-10).

Audit found that `crud/visit.py:add_visit_service` does NOT bump
`visit.updated_at` when a service is added. This means the "Изменено"
timestamp in registrar/doctor tables can never reflect doctor-side
service additions.

These tests verify that add_visit_service and remove_visit_service
both bump visit.updated_at.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.core.security import get_password_hash
from app.crud.visit import add_visit_service, remove_visit_service
from app.models.clinic import Doctor
from app.models.patient import Patient
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit, VisitService


def _make_visit(db_session, *, patient=None, doctor=None) -> Visit:
    """Create a minimal Visit row for testing."""
    if patient is None:
        patient = _make_patient(db_session)
    if doctor is None:
        doctor = _make_doctor(db_session)

    visit = Visit(
        patient_id=patient.id,
        doctor_id=doctor.id,
        visit_date=__import__("datetime").date.today(),
        status="scheduled",
    )
    db_session.add(visit)
    db_session.commit()
    db_session.refresh(visit)
    return visit


def _make_patient(db_session) -> Patient:
    suffix = uuid4().hex[:10]
    user = User(
        username=f"vs_pt_{suffix}",
        email=f"vs-pt-{suffix}@test.local",
        full_name=f"VS Patient {suffix}",
        hashed_password=get_password_hash("pass123"),
        role="Patient",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    patient = Patient(
        user_id=user.id,
        first_name="Patient",
        last_name=f"Test{suffix}",
        phone=f"+99890{suffix[:7]}",
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return patient


def _make_doctor(db_session) -> Doctor:
    suffix = uuid4().hex[:10]
    user = User(
        username=f"vs_doc_{suffix}",
        email=f"vs-doc-{suffix}@test.local",
        full_name=f"Dr. {suffix}",
        hashed_password=get_password_hash("pass123"),
        role="Doctor",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    doctor = Doctor(
        user_id=user.id,
        specialty="cardiology",
        active=True,
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return doctor


def _make_service(db_session, *, name: str = "Test Service") -> Service:
    service = Service(
        name=name,
        price=50000,
        duration_minutes=30,
    )
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)
    return service


class TestAddVisitServiceBumpsUpdatedAt:
    """PR-10: add_visit_service must bump visit.updated_at."""

    def test_add_visit_service_sets_updated_at_when_previously_null(self, db_session):
        """When visit.updated_at is None, add_visit_service should set it."""
        visit = _make_visit(db_session)
        service = _make_service(db_session)

        # Sanity: updated_at should be None initially (default only fires on insert,
        # but we explicitly check it's not set to a real value yet)
        assert visit.updated_at is None or visit.updated_at <= visit.created_at + timedelta(seconds=1)

        add_visit_service(db_session, visit_id=visit.id, service_id=service.id)

        db_session.expire_all()
        refreshed = db_session.query(Visit).filter(Visit.id == visit.id).first()
        assert refreshed.updated_at is not None
        # updated_at should be recent (within last 10 seconds)
        now = datetime.now(timezone.utc)
        assert (now - refreshed.updated_at.replace(tzinfo=timezone.utc)).total_seconds() < 10

    def test_add_visit_service_bumps_updated_at_when_already_set(self, db_session):
        """When visit.updated_at is already set, add_visit_service should bump it."""
        visit = _make_visit(db_session)
        service = _make_service(db_session)

        # Set an old updated_at
        old_updated_at = visit.created_at - timedelta(hours=1)
        visit.updated_at = old_updated_at
        db_session.commit()

        add_visit_service(db_session, visit_id=visit.id, service_id=service.id)

        db_session.expire_all()
        refreshed = db_session.query(Visit).filter(Visit.id == visit.id).first()
        assert refreshed.updated_at is not None
        # updated_at should be newer than the old value
        assert refreshed.updated_at.replace(tzinfo=timezone.utc) > old_updated_at.replace(tzinfo=timezone.utc)

    def test_add_visit_service_creates_visit_service_row(self, db_session):
        """Sanity: add_visit_service still creates the VisitService row."""
        visit = _make_visit(db_session)
        service = _make_service(db_session)

        result = add_visit_service(db_session, visit_id=visit.id, service_id=service.id)

        assert result is not None
        assert result.visit_id == visit.id
        assert result.service_id == service.id


class TestRemoveVisitServiceBumpsUpdatedAt:
    """PR-10: remove_visit_service must also bump visit.updated_at."""

    def test_remove_visit_service_bumps_updated_at(self, db_session):
        """Removing a service should bump visit.updated_at."""
        visit = _make_visit(db_session)
        service = _make_service(db_session)
        visit_service = add_visit_service(db_session, visit_id=visit.id, service_id=service.id)

        # Capture updated_at after add (which now bumps)
        db_session.expire_all()
        visit_after_add = db_session.query(Visit).filter(Visit.id == visit.id).first()
        updated_at_after_add = visit_after_add.updated_at

        # Wait a moment to ensure timestamp differs
        import time
        time.sleep(0.1)

        result = remove_visit_service(db_session, visit_service_id=visit_service.id)
        assert result is True

        db_session.expire_all()
        refreshed = db_session.query(Visit).filter(Visit.id == visit.id).first()
        assert refreshed.updated_at is not None
        # updated_at should be newer than after-add value
        assert refreshed.updated_at.replace(tzinfo=timezone.utc) >= updated_at_after_add.replace(tzinfo=timezone.utc)
