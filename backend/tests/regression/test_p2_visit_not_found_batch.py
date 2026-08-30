"""Regression tests for P2 #5: VisitNotFoundError → batch failure.

P2 #5: When a missing visit ID is submitted in a batch cancel request,
VisitLifecycleService.cancel_visit() raises VisitNotFoundError (NOT
HTTPException). The batch handler _run_single_registrar_record_action
only catches HTTPException and OnlineQueueNewDomainError — VisitNotFoundError
propagates, aborting the batch list comprehension and returning HTTP 500.

This was a REGRESSION from PR #2719: the old VisitsApiService.set_status
raised HTTPException(404) which WAS caught as a per-record failure.

Fix (PR 2725): add `except VisitNotFoundError` to _run_single.

Tests:
  1. Missing visit → per-record failure (NOT HTTP 500)
  2. Batch [valid, missing, valid] → 2 success + 1 failure
  3. Invalid transition → per-record failure (existing behavior unchanged)
  4. Missing record doesn't block other records in the batch

Run:
    pytest backend/tests/regression/test_p2_visit_not_found_batch.py -v
"""
from __future__ import annotations

from datetime import date

import pytest

from app.models.appointment import Appointment
from app.models.online_queue import OnlineQueueEntry
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.visit import Visit


def _create_visit_with_status(db_session, test_patient, test_doctor, status: str) -> Visit:
    """Create a visit with the given status."""
    visit = Visit(
        patient_id=test_patient.id,
        doctor_id=test_doctor.id,
        visit_date=date.today(),
        visit_time="10:00",
        status=status,
        discount_mode="none",
        department="cardiology",
        confirmation_token=f"test-token-{status}-{id(test_patient)}",
        confirmation_channel="telegram",
        confirmed_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
        confirmation_expires_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
        created_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
    )
    db_session.add(visit)
    db_session.commit()
    db_session.refresh(visit)
    return visit


@pytest.mark.integration
class TestP2VisitNotFoundBatchIsolation:
    """P2 #5: missing visit must be per-record failure, not batch abort."""

    def test_missing_visit_returns_per_record_failure_not_500(
        self, client, db_session, registrar_auth_headers
    ):
        """Cancel a non-existent visit ID → per-record failure, NOT HTTP 500."""
        response = client.post(
            "/api/v1/registrar/records/actions",
            headers=registrar_auth_headers,
            json={
                "action": "cancel",
                "records": [{"record_kind": "visit", "record_id": 999999}],
                "reason": "Test missing visit",
            },
        )

        # Must NOT be 500 — must be 200 with per-record failure.
        assert response.status_code == 200, (
            f"Expected HTTP 200 (batch response with per-record failure), "
            f"got HTTP {response.status_code}. This means VisitNotFoundError "
            f"was NOT caught — batch abort regression."
        )

        payload = response.json()
        assert payload["success"] is False  # batch-level: at least one failure
        assert payload["failed_count"] == 1
        assert payload["success_count"] == 0

        item = payload["results"][0]
        assert item["success"] is False
        assert "not found" in item.get("error", "").lower() or "не найден" in item.get("error", "").lower(), (
            f"Error should mention 'not found'. Got: {item.get('error')}"
        )

    def test_batch_valid_missing_valid_isolates_failure(
        self, client, db_session, registrar_auth_headers, test_patient, test_doctor
    ):
        """Batch [valid, missing, valid] → 2 success + 1 failure.

        The missing visit must NOT prevent processing of the third record.
        """
        # Create two valid visits
        visit_a = _create_visit_with_status(db_session, test_patient, test_doctor, "open")
        visit_c = _create_visit_with_status(db_session, test_patient, test_doctor, "open")

        response = client.post(
            "/api/v1/registrar/records/actions",
            headers=registrar_auth_headers,
            json={
                "action": "cancel",
                "records": [
                    {"record_kind": "visit", "record_id": visit_a.id},
                    {"record_kind": "visit", "record_id": 999999},  # missing
                    {"record_kind": "visit", "record_id": visit_c.id},
                ],
                "reason": "Batch cancel test",
            },
        )

        assert response.status_code == 200, (
            f"Expected HTTP 200, got {response.status_code}. "
            f"Batch should not abort on missing visit."
        )

        payload = response.json()
        assert payload["success_count"] == 2, (
            f"Expected 2 successes, got {payload['success_count']}. "
            f"Missing visit should not prevent processing of other records."
        )
        assert payload["failed_count"] == 1
        assert len(payload["results"]) == 3

        # Verify visit A and C were actually canceled
        db_session.refresh(visit_a)
        db_session.refresh(visit_c)
        assert visit_a.status == "canceled", "Visit A should be canceled"
        assert visit_c.status == "canceled", "Visit C should be canceled"

    def test_invalid_transition_still_returns_per_record_failure(
        self, client, db_session, registrar_auth_headers, test_patient, test_doctor
    ):
        """Invalid transition (completed → canceled) → per-record failure.

        This test verifies the fix doesn't break existing behavior for
        state machine rejections.
        """
        visit = _create_visit_with_status(db_session, test_patient, test_doctor, "completed")

        response = client.post(
            "/api/v1/registrar/records/actions",
            headers=registrar_auth_headers,
            json={
                "action": "cancel",
                "records": [{"record_kind": "visit", "record_id": visit.id}],
                "reason": "Test invalid transition",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["results"][0]["success"] is False, (
            "Canceling a completed visit must NOT succeed."
        )

        # Visit status must NOT change
        db_session.refresh(visit)
        assert visit.status == "completed"

    def test_missing_visit_does_not_create_side_effects(
        self, client, db_session, registrar_auth_headers, test_patient, test_doctor
    ):
        """Missing visit must not create/modify any records."""
        visit = _create_visit_with_status(db_session, test_patient, test_doctor, "open")

        # Count queue entries before
        from app.models.online_queue import OnlineQueueEntry
        queue_count_before = db_session.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.visit_id == 999999
        ).count()

        response = client.post(
            "/api/v1/registrar/records/actions",
            headers=registrar_auth_headers,
            json={
                "action": "cancel",
                "records": [{"record_kind": "visit", "record_id": 999999}],
                "reason": "Test no side effects",
            },
        )

        assert response.status_code == 200

        # No new queue entries should exist for the missing visit
        queue_count_after = db_session.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.visit_id == 999999
        ).count()
        assert queue_count_after == queue_count_before, (
            "Missing visit should not create any side effects."
        )
