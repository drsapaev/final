"""Commit-safe consultation classification against a disposable PostgreSQL."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.models.clinic import Doctor
from app.models.patient import Patient
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit, VisitService
from app.services.visit_completion_evidence import (
    RepeatEvidenceBusy,
    capture_completion_evidence,
)
from app.services.visit_lifecycle_service import VisitLifecycleService
from tests.integration.test_docsched_price_catalog_races_pg import catalog_pg_engine  # noqa: F401

pytestmark = pytest.mark.integration


def _case(engine):
    suffix = uuid4().hex[:12]
    with Session(engine, expire_on_commit=False) as db:
        user = User(username=f"synthetic_repeat_{suffix}", hashed_password="!synthetic", role="Doctor", is_active=True)
        patient = Patient(first_name="SYNTHETIC", last_name=suffix, phone="+998900000001", birth_date=date(1990, 1, 1))
        service = Service(code=f"SC{suffix}", name="SYNTHETIC consultation", price=Decimal("100.00"),
                          active=True, is_consultation=True, duration_minutes=30)
        db.add_all([user, patient, service])
        db.flush()
        doctor = Doctor(user_id=user.id, specialty="general", active=True, repeat_owner_generation=7)
        db.add(doctor)
        db.flush()
        visit = Visit(patient_id=patient.id, doctor_id=doctor.id, visit_date=date(2030, 1, 1),
                      status="in_progress", source="desk", discount_mode="none", repeat_evidence_generation=9,
                      repeat_assigned_doctor_user_id=user.id, repeat_assigned_owner_generation=7)
        db.add(visit)
        db.flush()
        db.add(VisitService(visit_id=visit.id, service_id=service.id, name=service.name, qty=1, price=service.price))
        db.flush()
        ids = visit.id, service.id
        db.commit()
        return ids


def test_catalog_writer_first_aborts_and_rolls_back_completion(catalog_pg_engine):
    visit_id, service_id = _case(catalog_pg_engine)
    with Session(catalog_pg_engine) as writer, Session(catalog_pg_engine) as completing:
        writer.execute(text("UPDATE services SET is_consultation=false WHERE id=:id"), {"id": service_id})
        visit = completing.query(Visit).filter_by(id=visit_id).with_for_update().one()
        visit.status = "completed"
        with pytest.raises(RepeatEvidenceBusy) as error:
            capture_completion_evidence(completing, visit)
        assert error.value.status_code == 409
        writer.commit()
        with Session(catalog_pg_engine) as verify:
            assert verify.get(Visit, visit_id).status == "in_progress"
            assert verify.get(Visit, visit_id).repeat_proof_generation is None
        with Session(catalog_pg_engine) as retry:
            visit = retry.query(Visit).filter_by(id=visit_id).with_for_update().one()
            capture_completion_evidence(retry, visit)
            visit.status = "completed"
            retry.commit()
        with Session(catalog_pg_engine) as verify:
            assert verify.get(Visit, visit_id).repeat_proof_consultation is False


def test_completion_first_holds_catalog_classification_through_commit(catalog_pg_engine):
    visit_id, service_id = _case(catalog_pg_engine)
    with Session(catalog_pg_engine) as completing, Session(catalog_pg_engine) as writer:
        visit = completing.query(Visit).filter_by(id=visit_id).with_for_update().one()
        capture_completion_evidence(completing, visit)
        visit.status = "completed"
        writer.execute(text("SET LOCAL lock_timeout='100ms'"))
        with pytest.raises(DBAPIError) as error:
            writer.execute(text("UPDATE services SET is_consultation=false WHERE id=:id"), {"id": service_id})
        assert (getattr(error.value.orig, "sqlstate", None) or getattr(error.value.orig, "pgcode", None)) == "55P03"
        writer.rollback()
        completing.commit()
        writer.execute(text("UPDATE services SET is_consultation=false WHERE id=:id"), {"id": service_id})
        writer.commit()
    with Session(catalog_pg_engine) as verify:
        visit = verify.get(Visit, visit_id)
        assert visit.status == "completed"
        assert visit.repeat_proof_generation == visit.repeat_evidence_generation
        assert visit.repeat_proof_consultation is True


def test_locked_transition_reloads_visit_cancelled_after_preload(catalog_pg_engine):
    visit_id, _ = _case(catalog_pg_engine)
    with Session(catalog_pg_engine) as completing, Session(catalog_pg_engine) as other:
        cached = completing.get(Visit, visit_id)
        assert cached.status == "in_progress"
        other.execute(text("UPDATE visits SET status='canceled' WHERE id=:id"), {"id": visit_id})
        other.commit()
        with pytest.raises(HTTPException) as error:
            VisitLifecycleService(completing).transition_status(
                visit_id, "completed", SimpleNamespace(id=1),
            )
        assert error.value.status_code == 409
        completing.rollback()
    with Session(catalog_pg_engine) as verify:
        visit = verify.get(Visit, visit_id)
        assert visit.status == "canceled"
        assert visit.repeat_proof_generation is None


def test_locked_reload_preserves_caller_staged_changes(catalog_pg_engine, monkeypatch):
    from app.services import emr_completion_policy

    visit_id, _ = _case(catalog_pg_engine)
    monkeypatch.setattr(emr_completion_policy, "require_saved_emr_for_visit", lambda *args, **kwargs: None)
    with Session(catalog_pg_engine, autoflush=False) as completing:
        visit = completing.get(Visit, visit_id)
        visit.notes = "SYNTHETIC staged note"
        VisitLifecycleService(completing).transition_status(
            visit_id, "completed", SimpleNamespace(id=1),
        )
    with Session(catalog_pg_engine) as verify:
        visit = verify.get(Visit, visit_id)
        assert visit.status == "completed"
        assert visit.notes == "SYNTHETIC staged note"
        assert visit.repeat_proof_consultation is True
