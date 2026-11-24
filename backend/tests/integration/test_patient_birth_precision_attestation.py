"""Synthetic administrator review of historical birth-date precision."""

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import event

from app.models.audit import AuditLog
from app.models.patient import Patient, PatientBirthDateEvidence
from app.models.user import User
from tests.conftest import mint_access_token


def _patient(db):
    patient = Patient(first_name="Synthetic", last_name="Patient", birth_date=date(2000, 1, 1),
                      birth_date_generation=7, birth_date_precision="unknown")
    db.add(patient)
    db.commit()
    return patient


def _review(client, headers, patient_id):
    return client.post(f"/api/v1/patients/{patient_id}/birth-date/review", headers=headers)


def _attest(client, headers, patient_id, review, **changes):
    body = {"confirmed_exact_date": True, "expected_generation": review["generation"],
            "review_expires_at": review["review_expires_at"], "token": review["token"]}
    body.update(changes)
    return client.post(f"/api/v1/patients/{patient_id}/birth-date/attest", headers=headers, json=body)


def test_admin_review_and_attestation_are_audited_and_single_use(client, db_session, auth_headers):
    patient = _patient(db_session)
    result = _review(client, auth_headers, patient.id)
    assert result.status_code == 200, result.text
    assert "no-store" in result.headers["cache-control"]
    review = result.json()
    assert review["birth_date"] == "2000-01-01" and review["precision"] == "unknown"
    response = _attest(client, auth_headers, patient.id, review)
    assert response.status_code == 200, response.text
    evidence = db_session.query(PatientBirthDateEvidence).filter_by(patient_id=patient.id).one()
    assert evidence.birth_date_generation == 7 and evidence.actor_role == "Admin"
    audit = db_session.query(AuditLog).filter_by(action="patient_birth_date_attested", entity_id=patient.id).one()
    assert "2000" not in str(audit.payload) and "2000" not in str(audit.reason_code)
    replay = _attest(client, auth_headers, patient.id, review)
    assert replay.status_code == 409 and "no-store" in replay.headers["cache-control"]


@pytest.mark.parametrize("change", ["date", "generation", "precision", "linked_user"])
def test_changed_patient_context_cannot_redeem_review(client, db_session, auth_headers, admin_user, change):
    patient = _patient(db_session)
    review = _review(client, auth_headers, patient.id).json()
    if change == "date":
        patient.birth_date = date(2000, 2, 1)
    elif change == "generation":
        patient.birth_date_generation += 1
    elif change == "precision":
        patient.birth_date_precision = "year_only"
    else:
        patient.user_id = admin_user.id
    db_session.commit()
    response = _attest(client, auth_headers, patient.id, review)
    assert response.status_code == 409, response.text
    assert db_session.query(PatientBirthDateEvidence).filter_by(patient_id=patient.id).count() == 0


def test_validation_and_unauthorized_responses_are_not_cacheable(client, db_session, auth_headers):
    patient = _patient(db_session)
    review = _review(client, auth_headers, patient.id).json()
    invalid = _attest(client, auth_headers, patient.id, review, confirmed_exact_date=False)
    anonymous = _attest(client, {}, patient.id, review)
    for response in (invalid, anonymous):
        assert response.status_code in (401, 403, 422)
        assert "no-store" in response.headers.get("cache-control", "").lower()
        assert review["token"] not in response.text


def test_review_capability_is_scrubbed_and_exact_confirmation_is_required(client, db_session, auth_headers):
    import json

    from app.core.pii_masker import mask_pii

    patient = _patient(db_session)
    review = _review(client, auth_headers, patient.id).json()
    assert mask_pii(review)["token"] == "[REDACTED]"
    assert review["token"] not in json.dumps(mask_pii(json.dumps(review)))
    response = client.post(f"/api/v1/patients/{patient.id}/birth-date/attest", headers=auth_headers, json={
        "reviewed_record": True, "expected_generation": review["generation"],
        "review_expires_at": review["review_expires_at"], "token": review["token"],
    })
    assert response.status_code == 422 and "no-store" in response.headers.get("cache-control", "").lower()
    assert review["token"] not in response.text


def test_missing_date_cannot_be_attested(client, db_session, auth_headers):
    patient = _patient(db_session)
    patient.birth_date = None
    db_session.commit()
    assert _review(client, auth_headers, patient.id).status_code == 409


def test_review_capability_cannot_be_redeemed_by_another_admin(client, db_session, auth_headers):
    patient = _patient(db_session)
    review = _review(client, auth_headers, patient.id).json()
    other = User(username="synthetic-other-admin", email="synthetic-other@invalid.example", full_name="Synthetic",
                 hashed_password="synthetic", role="Admin", is_active=True, is_superuser=True)
    db_session.add(other)
    db_session.commit()
    response = _attest(client, {"Authorization": f"Bearer {mint_access_token(other)}"}, patient.id, review)
    assert response.status_code == 409, response.text
    assert db_session.query(PatientBirthDateEvidence).filter_by(patient_id=patient.id).count() == 0


def test_review_failure_does_not_expose_token(client, db_session, auth_headers, monkeypatch):
    from app.api.v1.endpoints import patients as patients_endpoint

    patient = _patient(db_session)
    monkeypatch.setattr(patients_endpoint, "_build_patient_access_entry", lambda *args, **kwargs: None)
    response = _review(client, auth_headers, patient.id)
    assert response.status_code == 500 and "no-store" in response.headers.get("cache-control", "").lower()
    assert '"token"' not in response.text


def test_failed_audit_rolls_back_evidence(client, db_session, auth_headers):
    patient = _patient(db_session)
    patient_id = patient.id
    review = _review(client, auth_headers, patient_id).json()

    def refuse_audit(session, _context, _instances):
        if any(isinstance(obj, AuditLog) and obj.action == "patient_birth_date_attested" for obj in session.new):
            raise RuntimeError("synthetic audit failure")

    event.listen(db_session, "before_flush", refuse_audit)
    try:
        response = _attest(client, auth_headers, patient_id, review)
    finally:
        event.remove(db_session, "before_flush", refuse_audit)
    assert response.status_code == 500 and "no-store" in response.headers.get("cache-control", "").lower()
    assert db_session.query(PatientBirthDateEvidence).filter_by(patient_id=patient_id).count() == 0


@pytest.mark.parametrize("endpoint", ["review", "attest"])
def test_individual_logout_after_dependency_rejects_both_endpoints(
    client, db_session, auth_headers, admin_user, monkeypatch, endpoint
):
    from app.api.v1.endpoints import patients as patients_endpoint
    from app.services.token_blacklist_service import token_blacklist_service

    patient = _patient(db_session)
    patient_id = patient.id
    review = _review(client, auth_headers, patient_id).json()
    capture = patients_endpoint.capture_profile_bearer

    def capture_then_logout(request, actor):
        context = capture(request, actor)
        assert context.jti is not None and context.expires_at is not None
        assert token_blacklist_service.blacklist_token(
            db_session, context.jti, datetime.fromtimestamp(context.expires_at, UTC), user_id=admin_user.id
        )
        return context

    monkeypatch.setattr(patients_endpoint, "capture_profile_bearer", capture_then_logout)
    response = _review(client, auth_headers, patient_id) if endpoint == "review" else _attest(
        client, auth_headers, patient_id, review
    )
    assert response.status_code == 401, response.text
    assert db_session.query(PatientBirthDateEvidence).filter_by(patient_id=patient_id).count() == 0
