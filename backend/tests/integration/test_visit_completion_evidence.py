"""Admin attestation of pre-migration repeat-consultation evidence.

All records here are synthetic. No notifications or providers are used.
The migration's actual SQLite/PostgreSQL invalidation triggers are covered by
test_visit_completion_evidence_pg.py; the ordinary client fixture uses
SQLAlchemy create_all and deliberately does not install migration triggers.
"""
from __future__ import annotations

import importlib.util
import json
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_db
from app.db.base_class import Base
from app.main import app
from app.models.audit import AuditLog
from app.models.clinic import Doctor
from app.models.emr_v2 import EMRRecord
from app.models.patient import Patient
from app.models.patient_access_audit import PatientAccessAuditLog
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit, VisitService
from app.services.visit_lifecycle_service import VisitLifecycleService
from tests.conftest import mint_access_token


def _historical_visit(db, doctor, *, status="completed"):
    patient = Patient(first_name="SYNTHETIC", last_name=f"SYNTHETIC-{uuid4().hex[:8]}")
    db.add(patient)
    db.flush()
    visit = Visit(
        patient_id=patient.id,
        doctor_id=doctor.id,
        visit_date=date(2025, 1, 15),
        status=status,
        discount_mode="none",
        source="desk",
        repeat_evidence_generation=101,
    )
    db.add(visit)
    db.commit()
    return visit


def _review(client, headers, visit_id, doctor_user_id):
    return client.post(
        f"/api/v1/visits/{visit_id}/repeat-evidence/review", headers=headers,
        json={"doctor_user_id": doctor_user_id},
    )


def _attest(client, headers, visit_id, doctor_user_id, reviewed_record=True, review=None):
    if review is None:
        response = _review(client, headers, visit_id, doctor_user_id)
        if response.status_code != 200:
            return response
        review = response.json()
    return client.post(
        f"/api/v1/visits/{visit_id}/repeat-evidence/attest",
        headers=headers,
        json={
            "doctor_user_id": doctor_user_id,
            "reviewed_record": reviewed_record,
            "expected_generation": review["evidence_generation"],
            "review_expires_at": review["review_expires_at"],
            "token": review["token"],
        },
    )


def _evidence(db, visit):
    db.expire_all()
    return db.get(Visit, visit.id)


def _prepare_completion(db, doctor, *, is_consultation=True, save_emr=True):
    # Use a canonical specialty key; the shared fixture's localized label is
    # intentionally not used by the EMR-required policy's key lookup.
    doctor.specialty = "cardiology"
    visit = _historical_visit(db, doctor, status="in_progress")
    # The standard test fixture uses metadata.create_all rather than Alembic.
    # The real 0103 insert trigger captures these assignment bindings.
    visit.repeat_assigned_doctor_user_id = doctor.user_id
    visit.repeat_assigned_owner_generation = doctor.repeat_owner_generation
    service = Service(
        code=f"T{uuid4().hex[:6]}", name="SYNTHETIC consultation",
        active=True, is_consultation=is_consultation, price=100,
    )
    db.add(service)
    db.flush()
    db.add(VisitService(
        visit_id=visit.id, service_id=service.id,
        name="SYNTHETIC consultation", qty=1, price=100,
    ))
    if save_emr:
        db.add(EMRRecord(
            visit_id=visit.id, patient_id=visit.patient_id, data={},
            status="in_progress", created_by=doctor.user_id,
        ))
    db.commit()
    return visit


@pytest.mark.parametrize("via", ["lifecycle", "status_route"])
@pytest.mark.parametrize("consultation", [True, False])
def test_real_completion_records_factual_proof(
    client, db_session, auth_headers, admin_user, test_doctor, via, consultation
):
    visit = _prepare_completion(db_session, test_doctor, is_consultation=consultation)
    if via == "lifecycle":
        result = VisitLifecycleService(db_session).complete_visit(visit.id, admin_user)
        assert result.status == "completed"
    else:
        response = client.post(
            f"/api/v1/visits/visits/{visit.id}/status",
            params={"status_new": "completed"}, headers=auth_headers,
        )
        assert response.status_code == 200, response.text
    saved = _evidence(db_session, visit)
    assert saved.status == "completed"
    assert saved.repeat_proof_consultation is consultation
    assert saved.repeat_proof_generation == saved.repeat_evidence_generation
    assert saved.repeat_proof_doctor_user_id == test_doctor.user_id


@pytest.mark.parametrize("via", ["lifecycle", "status_route"])
def test_completion_requires_saved_emr_and_does_not_create_proof_on_failure(
    client, db_session, auth_headers, admin_user, test_doctor, via
):
    from fastapi import HTTPException

    visit = _prepare_completion(db_session, test_doctor, save_emr=False)
    if via == "lifecycle":
        with pytest.raises(HTTPException) as exc:
            VisitLifecycleService(db_session).complete_visit(visit.id, admin_user)
        assert exc.value.status_code == 409
        db_session.rollback()
    else:
        response = client.post(
            f"/api/v1/visits/visits/{visit.id}/status",
            params={"status_new": "completed"}, headers=auth_headers,
        )
        assert response.status_code == 409, response.text
    saved = _evidence(db_session, visit)
    assert saved.status == "in_progress"
    assert saved.repeat_proof_generation is None
    assert saved.repeat_proof_consultation is None


def test_force_reopen_does_not_fabricate_unknown_legacy_proof(
    client, db_session, auth_headers, test_doctor
):
    visit = _historical_visit(db_session, test_doctor, status="closed")
    response = client.post(
        f"/api/v1/visits/visits/{visit.id}/force-reopen",
        headers=auth_headers,
        json={"target_status": "completed", "reason": "SYNTHETIC correction"},
    )
    assert response.status_code == 200, response.text
    saved = _evidence(db_session, visit)
    assert saved.status == "completed"
    assert saved.repeat_proof_generation is None
    assert saved.repeat_proof_consultation is None


def test_force_reopen_by_non_admin_is_forbidden(
    client, db_session, cardio_auth_headers, test_doctor
):
    visit = _historical_visit(db_session, test_doctor, status="closed")
    response = client.post(
        f"/api/v1/visits/visits/{visit.id}/force-reopen",
        headers=cardio_auth_headers,
        json={"target_status": "completed", "reason": "SYNTHETIC correction"},
    )
    assert response.status_code == 403
    assert _evidence(db_session, visit).status == "closed"


def test_direct_completion_rejects_unassigned_doctor(
    client, db_session, cardio_auth_headers, test_doctor_user
):
    other_doctor = Doctor(user_id=test_doctor_user.id, specialty="cardiology", active=True)
    db_session.add(other_doctor)
    db_session.commit()
    visit = _prepare_completion(db_session, other_doctor)
    response = client.post(
        f"/api/v1/visits/visits/{visit.id}/status",
        params={"status_new": "completed"}, headers=cardio_auth_headers,
    )
    assert response.status_code == 403, response.text
    saved = _evidence(db_session, visit)
    assert saved.status == "in_progress"
    assert saved.repeat_proof_generation is None


def test_confirmation_status_still_fences_late_reminder_claim(
    client, db_session, auth_headers, test_doctor, monkeypatch
):
    from app.tasks import lease

    visit = _historical_visit(db_session, test_doctor, status="pending_confirmation")

    def claim_after_wait(db, visit_id):
        row = db.get(Visit, visit_id)
        row.reminder_claimed_at = datetime.now(UTC)
        db.flush()
        return True

    monkeypatch.setattr(lease, "wait_for_reminder_lease_clear", claim_after_wait)
    response = client.post(
        f"/api/v1/visits/visits/{visit.id}/status",
        params={"status_new": "confirmed"}, headers=auth_headers,
    )
    assert response.status_code == 409, response.text
    assert _evidence(db_session, visit).status == "pending_confirmation"


@pytest.mark.parametrize("specialty", ["Кардиология", "Дерматология"])
@pytest.mark.parametrize("has_saved_emr", [True, False])
@pytest.mark.parametrize("via", ["lifecycle", "status_route"])
def test_localized_doctor_specialty_still_requires_saved_emr(
    client, db_session, auth_headers, admin_user, test_doctor,
    specialty, has_saved_emr, via,
):
    from fastapi import HTTPException

    visit = _prepare_completion(db_session, test_doctor, save_emr=has_saved_emr)
    test_doctor.specialty = specialty
    db_session.commit()
    if via == "lifecycle":
        if has_saved_emr:
            VisitLifecycleService(db_session).complete_visit(visit.id, admin_user)
        else:
            with pytest.raises(HTTPException) as exc:
                VisitLifecycleService(db_session).complete_visit(visit.id, admin_user)
            assert exc.value.status_code == 409
            db_session.rollback()
    else:
        response = client.post(
            f"/api/v1/visits/visits/{visit.id}/status",
            params={"status_new": "completed"}, headers=auth_headers,
        )
        assert response.status_code == (200 if has_saved_emr else 409), response.text
    saved = _evidence(db_session, visit)
    assert saved.status == ("completed" if has_saved_emr else "in_progress")
    assert saved.repeat_proof_consultation is (True if has_saved_emr else None)


@pytest.mark.parametrize("status", ["completed", "closed"])
def test_admin_attests_verified_historical_visit_and_audits_atomically(
    client, db_session, auth_headers, admin_user, test_doctor, status
):
    visit = _historical_visit(db_session, test_doctor, status=status)
    review_response = _review(client, auth_headers, visit.id, test_doctor.user_id)
    assert review_response.status_code == 200, review_response.text
    assert "no-store" in review_response.headers.get("cache-control", "").lower()
    review = review_response.json()
    assert review["visit_id"] == visit.id
    assert review["patient_id"] == visit.patient_id
    assert review["doctor_id"] == test_doctor.id
    assert review["current_doctor_user_id"] == test_doctor.user_id
    assert review["doctor_user_id"] == test_doctor.user_id
    assert review["evidence_generation"] == visit.repeat_evidence_generation
    assert db_session.query(PatientAccessAuditLog).filter_by(
        subject_patient_id=visit.patient_id, actor_staff_user_id=admin_user.id,
        resource_id=str(visit.id), outcome="success",
    ).count() == 1
    response = _attest(client, auth_headers, visit.id, test_doctor.user_id, review=review)
    assert response.status_code == 200, response.text
    assert response.json() == {"success": True, "visit_id": visit.id}
    assert "no-store" in response.headers.get("cache-control", "").lower()

    saved = _evidence(db_session, visit)
    assert saved.repeat_proof_consultation is True
    assert saved.repeat_proof_generation == saved.repeat_evidence_generation
    assert saved.repeat_proof_doctor_user_id == test_doctor.user_id
    audit = db_session.query(AuditLog).filter_by(
        action="repeat_consultation_attested",
        entity_type="visit",
        entity_id=visit.id,
        actor_user_id=admin_user.id,
    ).one()
    assert audit.payload["doctor_user_id"] == test_doctor.user_id
    assert audit.payload["evidence_generation"] == saved.repeat_evidence_generation
    assert "SYNTHETIC" not in json.dumps(audit.payload)


def test_doctor_cannot_attest_own_or_other_visit(
    client, db_session, auth_headers, cardio_auth_headers, test_doctor
):
    visit = _historical_visit(db_session, test_doctor)
    denied_review = _review(client, cardio_auth_headers, visit.id, test_doctor.user_id)
    assert denied_review.status_code == 403
    assert "no-store" in denied_review.headers.get("cache-control", "").lower()
    review = _review(client, auth_headers, visit.id, test_doctor.user_id).json()
    response = _attest(client, cardio_auth_headers, visit.id, test_doctor.user_id, review=review)
    assert response.status_code == 403
    assert "no-store" in response.headers.get("cache-control", "").lower()
    assert review["token"] not in response.text
    assert _evidence(db_session, visit).repeat_proof_generation is None


@pytest.mark.parametrize("review", [False, "true", 1, None])
def test_attestation_requires_explicit_boolean_confirmation(
    client, db_session, auth_headers, test_doctor, review
):
    visit = _historical_visit(db_session, test_doctor)
    response = _attest(client, auth_headers, visit.id, test_doctor.user_id, review)
    assert response.status_code == 422, response.text
    assert _evidence(db_session, visit).repeat_proof_generation is None


def test_attestation_requires_review_field(client, db_session, auth_headers, test_doctor, caplog):
    visit = _historical_visit(db_session, test_doctor)
    review = _review(client, auth_headers, visit.id, test_doctor.user_id).json()
    caplog.clear()
    response = client.post(
        f"/api/v1/visits/{visit.id}/repeat-evidence/attest",
        headers=auth_headers,
        json={"doctor_user_id": test_doctor.user_id,
              "expected_generation": review["evidence_generation"],
              "review_expires_at": review["review_expires_at"],
              "token": review["token"]},
    )
    assert response.status_code == 422, response.text
    assert "no-store" in response.headers.get("cache-control", "").lower()
    assert review["token"] not in response.text
    assert review["token"] not in caplog.text
    assert _evidence(db_session, visit).repeat_proof_generation is None


@pytest.mark.parametrize("doctor_id", [0, -1, True, "1"])
def test_attestation_rejects_invalid_doctor_user_id(
    client, db_session, auth_headers, test_doctor, doctor_id
):
    visit = _historical_visit(db_session, test_doctor)
    response = _attest(client, auth_headers, visit.id, doctor_id)
    assert response.status_code == 422, response.text
    assert _evidence(db_session, visit).repeat_proof_generation is None


def test_attestation_requires_doctor_user_id(client, db_session, auth_headers, test_doctor):
    visit = _historical_visit(db_session, test_doctor)
    review = _review(client, auth_headers, visit.id, test_doctor.user_id).json()
    response = client.post(
        f"/api/v1/visits/{visit.id}/repeat-evidence/attest",
        headers=auth_headers,
        json={"reviewed_record": True,
              "expected_generation": review["evidence_generation"],
              "review_expires_at": review["review_expires_at"],
              "token": review["token"]},
    )
    assert response.status_code == 422, response.text
    assert _evidence(db_session, visit).repeat_proof_generation is None


@pytest.mark.parametrize("status", ["open", "pending_confirmation", "confirmed", "in_progress", "canceled", "expired"])
def test_admin_cannot_attest_unfinished_or_cancelled_visit(
    client, db_session, auth_headers, test_doctor, status
):
    visit = _historical_visit(db_session, test_doctor)
    review = _review(client, auth_headers, visit.id, test_doctor.user_id).json()
    visit.status = status
    db_session.commit()
    response = _attest(client, auth_headers, visit.id, test_doctor.user_id, review=review)
    assert response.status_code == 409, response.text
    assert _evidence(db_session, visit).repeat_proof_generation is None


def test_unknown_visit_or_clinician_is_not_attested(client, db_session, auth_headers, test_doctor):
    visit = _historical_visit(db_session, test_doctor)
    assert _attest(client, auth_headers, 2147483647, test_doctor.user_id).status_code == 404
    assert _attest(client, auth_headers, visit.id, 2147483647).status_code == 404
    assert _evidence(db_session, visit).repeat_proof_generation is None


def test_existing_current_proof_cannot_be_replaced(client, db_session, auth_headers, test_doctor):
    visit = _historical_visit(db_session, test_doctor)
    review = _review(client, auth_headers, visit.id, test_doctor.user_id).json()
    visit.repeat_proof_generation = visit.repeat_evidence_generation
    visit.repeat_proof_consultation = True
    visit.repeat_proof_doctor_user_id = test_doctor.user_id
    db_session.commit()
    response = _attest(client, auth_headers, visit.id, test_doctor.user_id, review=review)
    assert response.status_code == 409, response.text
    saved = _evidence(db_session, visit)
    assert saved.repeat_proof_generation == saved.repeat_evidence_generation
    assert saved.repeat_proof_doctor_user_id == test_doctor.user_id
    assert db_session.query(AuditLog).filter_by(
        action="repeat_consultation_attested", entity_id=visit.id
    ).count() == 0


def test_stale_proof_requires_new_review_and_can_be_attested(
    client, db_session, auth_headers, test_doctor
):
    visit = _historical_visit(db_session, test_doctor)
    visit.repeat_proof_generation = 100
    visit.repeat_proof_consultation = True
    visit.repeat_proof_doctor_user_id = test_doctor.user_id
    db_session.commit()
    response = _attest(client, auth_headers, visit.id, test_doctor.user_id)
    assert response.status_code == 200, response.text
    saved = _evidence(db_session, visit)
    assert saved.repeat_proof_generation == saved.repeat_evidence_generation == 101


def test_audit_write_failure_rolls_back_attestation(
    client, db_session, auth_headers, test_doctor
):
    visit = _historical_visit(db_session, test_doctor)
    visit_id = visit.id
    bind = db_session.get_bind()

    def fail_audit_insert(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().lower().startswith("insert into audit_logs"):
            raise RuntimeError("SYNTHETIC audit storage unavailable")

    event.listen(bind, "before_cursor_execute", fail_audit_insert)
    try:
        response = _attest(client, auth_headers, visit_id, test_doctor.user_id)
    finally:
        event.remove(bind, "before_cursor_execute", fail_audit_insert)
    assert response.status_code == 500, response.text
    assert "no-store" in response.headers.get("cache-control", "").lower()
    db_session.rollback()
    saved = db_session.get(Visit, visit_id)
    assert saved.repeat_proof_generation is None
    assert saved.repeat_proof_consultation is None
    assert saved.repeat_proof_doctor_user_id is None


def test_review_fails_closed_when_patient_access_audit_cannot_be_written(
    client, db_session, auth_headers, test_doctor
):
    visit = _historical_visit(db_session, test_doctor)
    visit_id = visit.id
    bind = db_session.get_bind()

    def fail_patient_access_insert(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().lower().startswith("insert into patient_access_audit_logs"):
            raise RuntimeError("SYNTHETIC access audit unavailable")

    event.listen(bind, "before_cursor_execute", fail_patient_access_insert)
    try:
        response = _review(client, auth_headers, visit_id, test_doctor.user_id)
    finally:
        event.remove(bind, "before_cursor_execute", fail_patient_access_insert)
    assert response.status_code == 500, response.text
    assert "no-store" in response.headers.get("cache-control", "").lower()
    assert '"token"' not in response.text
    db_session.rollback()
    assert db_session.get(Visit, visit_id).repeat_proof_generation is None


def test_stale_review_generation_is_not_redeemable(
    client, db_session, auth_headers, test_doctor
):
    visit = _historical_visit(db_session, test_doctor)
    review = _review(client, auth_headers, visit.id, test_doctor.user_id).json()
    # The ORM-only test DB has no migrations; real ABA trigger behaviour is
    # covered separately by the migrated SQLite/PostgreSQL tests.
    visit.repeat_evidence_generation += 1
    db_session.commit()
    response = _attest(client, auth_headers, visit.id, test_doctor.user_id, review=review)
    assert response.status_code == 409, response.text
    assert "no-store" in response.headers.get("cache-control", "").lower()
    assert _evidence(db_session, visit).repeat_proof_generation is None
    assert db_session.query(AuditLog).filter_by(
        action="repeat_consultation_attested", entity_id=visit.id
    ).count() == 0


def test_review_token_is_bound_to_admin_actor(
    client, db_session, auth_headers, test_doctor
):
    visit = _historical_visit(db_session, test_doctor)
    review = _review(client, auth_headers, visit.id, test_doctor.user_id).json()
    other_admin = User(
        username=f"SYNTHETIC-admin-{uuid4().hex[:8]}",
        email=f"synthetic-{uuid4().hex[:8]}@example.com",
        hashed_password="SYNTHETIC-unused", role="Admin", is_active=True,
        is_superuser=True,
    )
    db_session.add(other_admin)
    db_session.commit()
    other_headers = {"Authorization": f"Bearer {mint_access_token(other_admin)}"}
    response = _attest(client, other_headers, visit.id, test_doctor.user_id, review=review)
    assert response.status_code in (403, 409), response.text
    assert _evidence(db_session, visit).repeat_proof_generation is None
    assert db_session.query(AuditLog).filter_by(
        action="repeat_consultation_attested", entity_id=visit.id
    ).count() == 0


def test_review_token_is_bound_to_the_reviewed_doctor(
    client, db_session, auth_headers, admin_user, test_doctor
):
    visit = _historical_visit(db_session, test_doctor)
    review = _review(client, auth_headers, visit.id, test_doctor.user_id).json()
    response = _attest(client, auth_headers, visit.id, admin_user.id, review=review)
    assert response.status_code == 409, response.text
    assert _evidence(db_session, visit).repeat_proof_generation is None
    assert db_session.query(AuditLog).filter_by(
        action="repeat_consultation_attested", entity_id=visit.id
    ).count() == 0


@pytest.mark.parametrize("seconds_after_expiry", [0, 1])
def test_review_token_expiry_fails_closed(
    client, db_session, auth_headers, test_doctor, monkeypatch, seconds_after_expiry
):
    from app.api.v1.endpoints import visits as visits_module

    visit = _historical_visit(db_session, test_doctor)
    review = _review(client, auth_headers, visit.id, test_doctor.user_id).json()
    monkeypatch.setattr(
        visits_module, "time",
        SimpleNamespace(time=lambda: review["review_expires_at"] + seconds_after_expiry),
    )
    response = _attest(client, auth_headers, visit.id, test_doctor.user_id, review=review)
    assert response.status_code == 409, response.text
    assert _evidence(db_session, visit).repeat_proof_generation is None


def test_review_token_is_masked_in_scrubbers_and_validation_errors(
    client, db_session, auth_headers, test_doctor, caplog
):
    from app.core.pii_masker import mask_pii

    visit = _historical_visit(db_session, test_doctor)
    response = _review(client, auth_headers, visit.id, test_doctor.user_id)
    assert response.status_code == 200, response.text
    review = response.json()
    assert mask_pii(review)["token"] == "[REDACTED]"
    assert review["token"] not in json.dumps(mask_pii(json.dumps(review)))

    secret = "SYNTHETIC-REVIEW-TOKEN-MUST-NOT-BE-LOGGED"
    caplog.clear()
    malformed = client.post(
        f"/api/v1/visits/{visit.id}/repeat-evidence/attest",
        headers=auth_headers,
        json={"doctor_user_id": test_doctor.user_id, "reviewed_record": True,
              "expected_generation": review["evidence_generation"],
              "review_expires_at": review["review_expires_at"], "token": {"value": secret}},
    )
    assert malformed.status_code == 422, malformed.text
    assert "no-store" in malformed.headers.get("cache-control", "").lower()
    assert secret not in malformed.text
    assert secret not in caplog.text


def test_unauthenticated_review_and_attestation_are_not_cacheable(
    client, db_session, auth_headers, test_doctor, caplog
):
    visit = _historical_visit(db_session, test_doctor)
    review = _review(client, auth_headers, visit.id, test_doctor.user_id).json()
    caplog.clear()
    unauthenticated_review = _review(client, {}, visit.id, test_doctor.user_id)
    unauthenticated_post = _attest(client, {}, visit.id, test_doctor.user_id, review=review)
    for response in (unauthenticated_review, unauthenticated_post):
        assert response.status_code in (401, 403), response.text
        assert "no-store" in response.headers.get("cache-control", "").lower()
        assert review["token"] not in response.text
    assert review["token"] not in caplog.text


def test_invalid_review_request_is_not_cacheable(client, db_session, auth_headers, test_doctor):
    visit = _historical_visit(db_session, test_doctor)
    response = _review(client, auth_headers, visit.id, True)
    assert response.status_code == 422, response.text
    assert "no-store" in response.headers.get("cache-control", "").lower()


@pytest.mark.parametrize("change", ["auth_epoch", "inactive"])
def test_admin_revocation_after_review_prevents_attestation(
    client, db_session, auth_headers, admin_user, test_doctor, change
):
    visit = _historical_visit(db_session, test_doctor)
    review = _review(client, auth_headers, visit.id, test_doctor.user_id).json()
    if change == "auth_epoch":
        admin_user.auth_epoch += 1
    else:
        admin_user.is_active = False
    db_session.commit()
    response = _attest(client, auth_headers, visit.id, test_doctor.user_id, review=review)
    assert response.status_code in (401, 403, 409), response.text
    assert _evidence(db_session, visit).repeat_proof_generation is None
    assert db_session.query(AuditLog).filter_by(
        action="repeat_consultation_attested", entity_id=visit.id
    ).count() == 0


@pytest.mark.parametrize("endpoint", ["review", "attest"])
def test_individual_logout_after_dependency_prevents_repeat_write(
    client, db_session, auth_headers, admin_user, test_doctor, monkeypatch, endpoint
):
    """A real JTI logout between dependency and lock must be seen under lock."""
    from app.api.v1.endpoints import visits as visits_endpoint
    from app.services.token_blacklist_service import token_blacklist_service

    visit = _historical_visit(db_session, test_doctor)
    review = _review(client, auth_headers, visit.id, test_doctor.user_id).json()
    capture = visits_endpoint.capture_profile_bearer

    def capture_then_logout(request, actor):
        context = capture(request, actor)
        assert context.jti is not None and context.expires_at is not None
        assert token_blacklist_service.blacklist_token(
            db_session, context.jti, datetime.fromtimestamp(context.expires_at, UTC),
            user_id=admin_user.id,
        )
        return context

    monkeypatch.setattr(visits_endpoint, "capture_profile_bearer", capture_then_logout)
    if endpoint == "review":
        response = _review(client, auth_headers, visit.id, test_doctor.user_id)
    else:
        response = _attest(client, auth_headers, visit.id, test_doctor.user_id, review=review)
    assert response.status_code == 401, response.text
    assert "no-store" in response.headers.get("cache-control", "").lower()
    assert _evidence(db_session, visit).repeat_proof_generation is None
    assert db_session.query(AuditLog).filter_by(
        action="repeat_consultation_attested", entity_id=visit.id
    ).count() == 0


def test_attestation_review_is_single_use_for_current_proof(
    client, db_session, auth_headers, test_doctor
):
    visit = _historical_visit(db_session, test_doctor)
    review = _review(client, auth_headers, visit.id, test_doctor.user_id).json()
    first = _attest(client, auth_headers, visit.id, test_doctor.user_id, review=review)
    assert first.status_code == 200, first.text
    replay = _attest(client, auth_headers, visit.id, test_doctor.user_id, review=review)
    assert replay.status_code == 409, replay.text
    assert db_session.query(AuditLog).filter_by(
        action="repeat_consultation_attested", entity_id=visit.id
    ).count() == 1


@pytest.fixture
def migrated_attestation_client(tmp_path):
    """Install the actual 0102/0103 SQLite triggers on an isolated schema.

    Metadata already has the columns, so the operation adapter skips only
    ADD COLUMN; trigger SQL itself is executed unchanged from both revisions.
    The separate migration suite tests the real upgrades and downgrades.
    """
    engine = create_engine(
        f"sqlite:///{tmp_path / 'SYNTHETIC_attest.sqlite'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    versions = Path(__file__).resolve().parents[2] / "alembic" / "versions"

    with engine.begin() as connection:
        context = MigrationContext.configure(connection)

        class ExistingColumnsOperations:
            def get_bind(self):
                return connection

            def get_context(self):
                return context

            def add_column(self, *args, **kwargs):
                return None

            def execute(self, sql):
                if str(sql).lstrip().upper().startswith("ALTER TABLE VISITS ADD COLUMN"):
                    return None
                return connection.execute(text(str(sql)))

        for filename in ("0102_visit_confirmation_context.py", "0103_visit_consultation_completion.py"):
            spec = importlib.util.spec_from_file_location("SYNTHETIC_" + filename, versions / filename)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.op = ExistingColumnsOperations()
            module.upgrade()

    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        admin = User(
            username="SYNTHETIC-review-admin", email="synthetic-review@example.com",
            hashed_password="SYNTHETIC-unused", role="Admin", is_active=True,
            is_superuser=True,
        )
        first_user = User(
            username="SYNTHETIC-doctor-a", email="synthetic-doctor-a@example.com",
            hashed_password="SYNTHETIC-unused", role="Doctor", is_active=True,
        )
        second_user = User(
            username="SYNTHETIC-doctor-b", email="synthetic-doctor-b@example.com",
            hashed_password="SYNTHETIC-unused", role="Doctor", is_active=True,
        )
        unbound_user = User(
            username="SYNTHETIC-doctor-c", email="synthetic-doctor-c@example.com",
            hashed_password="SYNTHETIC-unused", role="Doctor", is_active=True,
        )
        first_patient = Patient(first_name="SYNTHETIC", last_name="SYNTHETIC-A")
        second_patient = Patient(first_name="SYNTHETIC", last_name="SYNTHETIC-B")
        db.add_all([admin, first_user, second_user, unbound_user, first_patient, second_patient])
        db.flush()
        doctor_a = Doctor(user_id=first_user.id, specialty="cardiology", active=True)
        doctor_b = Doctor(user_id=second_user.id, specialty="cardiology", active=True)
        service = Service(code="SYNTHETIC", name="SYNTHETIC consultation", active=True, is_consultation=True)
        db.add_all([doctor_a, doctor_b, service])
        db.flush()
        visit = Visit(
            patient_id=first_patient.id, doctor_id=doctor_a.id,
            visit_date=date(2025, 1, 15), status="completed", discount_mode="none", source="desk",
        )
        db.add(visit)
        db.flush()
        line = VisitService(visit_id=visit.id, service_id=service.id, name="SYNTHETIC", qty=1, price=100)
        db.add(line)
        db.commit()
        ids = {
            "visit": visit.id, "line": line.id, "patient_a": first_patient.id,
            "patient_b": second_patient.id, "doctor_a": doctor_a.id,
            "doctor_b": doctor_b.id, "doctor_user": first_user.id,
            "unbound_user": unbound_user.id, "admin": admin.id, "service": service.id,
        }
        headers = {"Authorization": f"Bearer {mint_access_token(admin)}"}

    def own_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = own_db
    try:
        with TestClient(app) as client:
            yield client, factory, headers, ids
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


@pytest.mark.parametrize("change", ["patient", "doctor", "date", "service", "status"])
def test_real_trigger_aba_rejects_old_review_and_requires_fresh_attestation(
    migrated_attestation_client, change
):
    client, factory, headers, ids = migrated_attestation_client
    review = _review(client, headers, ids["visit"], ids["doctor_user"]).json()
    first = _attest(client, headers, ids["visit"], ids["doctor_user"], review=review)
    assert first.status_code == 200, first.text

    with factory() as db:
        if change == "service":
            row = db.get(VisitService, ids["line"])
            attribute, first_value, original = "qty", 2, 1
        else:
            row = db.get(Visit, ids["visit"])
            attribute, first_value, original = {
                "patient": ("patient_id", ids["patient_b"], ids["patient_a"]),
                "doctor": ("doctor_id", ids["doctor_b"], ids["doctor_a"]),
                "date": ("visit_date", date(2025, 1, 16), date(2025, 1, 15)),
                "status": ("status", "in_progress", "completed"),
            }[change]
        setattr(row, attribute, first_value)
        db.commit()
        setattr(row, attribute, original)
        db.commit()
        db.expire_all()
        changed = db.get(Visit, ids["visit"])
        assert changed.repeat_evidence_generation != review["evidence_generation"]
        assert changed.repeat_proof_generation is None

    replay = _attest(client, headers, ids["visit"], ids["doctor_user"], review=review)
    assert replay.status_code == 409, replay.text
    assert "no-store" in replay.headers.get("cache-control", "").lower()
    with factory() as db:
        assert db.query(AuditLog).filter_by(action="repeat_consultation_attested", entity_id=ids["visit"]).count() == 1

    refreshed_review = _review(client, headers, ids["visit"], ids["doctor_user"]).json()
    renewed = _attest(client, headers, ids["visit"], ids["doctor_user"], review=refreshed_review)
    assert renewed.status_code == 200, renewed.text
    with factory() as db:
        assert db.query(AuditLog).filter_by(action="repeat_consultation_attested", entity_id=ids["visit"]).count() == 2


def test_doctor_profile_owner_aba_invalidates_existing_review(migrated_attestation_client):
    client, factory, headers, ids = migrated_attestation_client
    review = _review(client, headers, ids["visit"], ids["doctor_user"]).json()
    with factory() as db:
        doctor = db.get(Doctor, ids["doctor_a"])
        doctor.user_id = ids["unbound_user"]
        db.commit()
        doctor.user_id = ids["doctor_user"]
        db.commit()
    response = _attest(client, headers, ids["visit"], ids["doctor_user"], review=review)
    assert response.status_code == 409, response.text
    with factory() as db:
        assert db.get(Visit, ids["visit"]).repeat_proof_generation is None
        assert db.query(AuditLog).filter_by(action="repeat_consultation_attested", entity_id=ids["visit"]).count() == 0


@pytest.mark.parametrize("via", ["lifecycle", "status_route"])
def test_migrated_new_visit_records_completion_evidence(
    migrated_attestation_client, via
):
    client, factory, headers, ids = migrated_attestation_client
    with factory() as db:
        visit = Visit(
            patient_id=ids["patient_a"], doctor_id=ids["doctor_a"],
            visit_date=date(2025, 1, 17), status="open", discount_mode="none", source="desk",
        )
        db.add(visit)
        db.flush()
        visit_id = visit.id
        db.add(VisitService(
            visit_id=visit_id, service_id=ids["service"], name="SYNTHETIC", qty=1, price=100,
        ))
        db.add(EMRRecord(
            visit_id=visit_id, patient_id=ids["patient_a"], data={},
            status="in_progress", created_by=ids["doctor_user"],
        ))
        visit.status = "in_progress"
        db.commit()
        db.refresh(visit)
        assert visit.repeat_assigned_doctor_user_id == ids["doctor_user"]
        if via == "lifecycle":
            VisitLifecycleService(db).complete_visit(visit_id, db.get(User, ids["admin"]))

    if via == "status_route":
        response = client.post(
            f"/api/v1/visits/visits/{visit_id}/status",
            params={"status_new": "completed"}, headers=headers,
        )
        assert response.status_code == 200, response.text

    with factory() as db:
        visit = db.get(Visit, visit_id)
        assert visit.status == "completed"
        assert visit.repeat_proof_consultation is True
        assert visit.repeat_proof_generation == visit.repeat_evidence_generation
        assert visit.repeat_proof_doctor_user_id == ids["doctor_user"]


def test_migrated_doctor_owner_aba_during_care_does_not_manufacture_proof(
    migrated_attestation_client,
):
    _, factory, _, ids = migrated_attestation_client
    with factory() as db:
        visit = Visit(
            patient_id=ids["patient_a"], doctor_id=ids["doctor_a"],
            visit_date=date(2025, 1, 17), status="open", discount_mode="none", source="desk",
        )
        db.add(visit)
        db.flush()
        visit_id = visit.id
        db.add(VisitService(visit_id=visit_id, service_id=ids["service"], name="SYNTHETIC", qty=1, price=100))
        db.add(EMRRecord(visit_id=visit_id, patient_id=ids["patient_a"], data={},
                         status="in_progress", created_by=ids["doctor_user"]))
        visit.status = "in_progress"
        db.commit()
        doctor = db.get(Doctor, ids["doctor_a"])
        doctor.user_id = ids["unbound_user"]
        db.commit()
        doctor.user_id = ids["doctor_user"]
        db.commit()
        db.refresh(visit)
        assert visit.repeat_assigned_doctor_user_id is None
        VisitLifecycleService(db).complete_visit(visit_id, db.get(User, ids["admin"]))
        db.refresh(visit)
        assert visit.status == "completed"  # Clinical care is not blocked.
        assert visit.repeat_proof_generation is None


def test_migrated_reconstructed_in_progress_visit_requires_manual_review(
    migrated_attestation_client,
):
    _, factory, _, ids = migrated_attestation_client
    with factory() as db:
        visit = Visit(
            patient_id=ids["patient_a"], doctor_id=ids["doctor_a"],
            visit_date=date(2025, 1, 17), status="in_progress", discount_mode="none", source="desk",
        )
        db.add(visit)
        db.flush()
        visit_id = visit.id
        db.add(VisitService(visit_id=visit_id, service_id=ids["service"], name="SYNTHETIC", qty=1, price=100))
        db.add(EMRRecord(visit_id=visit_id, patient_id=ids["patient_a"], data={},
                         status="in_progress", created_by=ids["doctor_user"]))
        db.commit()
        db.refresh(visit)
        assert visit.repeat_assigned_doctor_user_id is None
        VisitLifecycleService(db).complete_visit(visit_id, db.get(User, ids["admin"]))
        db.refresh(visit)
        assert visit.status == "completed"
        assert visit.repeat_proof_generation is None
