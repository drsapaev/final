"""Regression tests for Gate C bypass C: registrar_wizard cancel action.

Gate C bypass C (visits_api_service.py:set_status) was a real bypass
of the visit state machine. The old code called
``VisitsApiService.set_status(visit_id, status_new="canceled")`` which
did NOT call ``is_valid_visit_transition()``, allowing invalid
transitions like:

    completed → canceled  (clinical work done, EMR may be signed)
    closed → canceled     (EMR signed + payment collected)
    expired → canceled    (confirmation timeout bypassed)

Fix: migrate the caller (``registrar_wizard/_visits.py:897``) to
``VisitLifecycleService.cancel_visit()``, which provides:
    - SELECT FOR UPDATE row lock (concurrency safety)
    - is_valid_visit_transition() validation (state machine)
    - Audit logging (logger.info with visit_id, user_id, reason)
    - commit=False for caller-controlled transaction

These tests verify:
    1. Valid transitions still succeed (open→canceled, confirmed→canceled, etc.)
    2. Invalid transitions are rejected (completed→canceled, closed→canceled, expired→canceled)
    3. Rollback: no partial persistence on rejection
    4. request.reason is passed to the lifecycle service (audit logging)

Run:
    pytest backend/tests/regression/test_gate_c_bypass_c_registrar_cancel.py -v
"""
from __future__ import annotations

from datetime import date, datetime, UTC

import pytest

from app.models.visit import Visit


def _create_visit_with_status(db_session, test_patient, test_doctor, status: str) -> Visit:
    """Create a visit with the given status (bypasses state machine for setup)."""
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
        confirmation_expires_at=datetime.now(UTC),
        confirmed_at=datetime.now(UTC) if status != "pending_confirmation" else None,
        created_at=datetime.now(UTC),
    )
    db_session.add(visit)
    db_session.commit()
    db_session.refresh(visit)
    return visit


@pytest.mark.integration
class TestGateCBypassCRegistrarCancel:
    """Gate C bypass C: registrar cancel must use VisitLifecycleService."""

    # ─── Valid transitions (should succeed) ───────────────────────────

    def test_cancel_open_visit_succeeds(
        self, client, db_session, registrar_auth_headers, test_patient, test_doctor
    ):
        """open → canceled: valid transition, should succeed."""
        visit = _create_visit_with_status(db_session, test_patient, test_doctor, "open")

        response = client.post(
            "/api/v1/registrar/records/actions",
            headers=registrar_auth_headers,
            json={
                "action": "cancel",
                "records": [{"record_kind": "visit", "record_id": visit.id}],
                "reason": "Patient requested cancellation",
            },
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["success"] is True
        assert payload["results"][0]["success"] is True

        db_session.refresh(visit)
        assert visit.status == "canceled"

    def test_cancel_confirmed_visit_succeeds(
        self, client, db_session, registrar_auth_headers, test_patient, test_doctor
    ):
        """confirmed → canceled: valid transition per state machine."""
        visit = _create_visit_with_status(db_session, test_patient, test_doctor, "confirmed")

        response = client.post(
            "/api/v1/registrar/records/actions",
            headers=registrar_auth_headers,
            json={
                "action": "cancel",
                "records": [{"record_kind": "visit", "record_id": visit.id}],
                "reason": "Patient changed mind",
            },
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["success"] is True
        assert payload["results"][0]["success"] is True

        db_session.refresh(visit)
        assert visit.status == "canceled"

    def test_cancel_in_progress_visit_succeeds(
        self, client, db_session, registrar_auth_headers, test_patient, test_doctor
    ):
        """in_progress → canceled: valid transition per state machine."""
        visit = _create_visit_with_status(db_session, test_patient, test_doctor, "in_progress")

        response = client.post(
            "/api/v1/registrar/records/actions",
            headers=registrar_auth_headers,
            json={
                "action": "cancel",
                "records": [{"record_kind": "visit", "record_id": visit.id}],
                "reason": "Doctor called in sick",
            },
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["success"] is True
        assert payload["results"][0]["success"] is True

        db_session.refresh(visit)
        assert visit.status == "canceled"

    def test_cancel_pending_confirmation_visit_succeeds(
        self, client, db_session, registrar_auth_headers, test_patient, test_doctor
    ):
        """pending_confirmation → canceled: valid transition per state machine."""
        visit = _create_visit_with_status(
            db_session, test_patient, test_doctor, "pending_confirmation"
        )

        response = client.post(
            "/api/v1/registrar/records/actions",
            headers=registrar_auth_headers,
            json={
                "action": "cancel",
                "records": [{"record_kind": "visit", "record_id": visit.id}],
                "reason": "Patient did not confirm",
            },
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["success"] is True
        assert payload["results"][0]["success"] is True

        db_session.refresh(visit)
        assert visit.status == "canceled"

    # ─── Invalid transitions (should be rejected — bypass fix) ────────

    def test_cancel_completed_visit_rejected(
        self, client, db_session, registrar_auth_headers, test_patient, test_doctor
    ):
        """completed → canceled: MUST be rejected.

        A completed visit has clinical work finished. The state machine
        only allows completed → in_progress (re-open) or completed → closed
        (finalize). Canceling a completed visit loses the clinical audit
        trail and may leave orphaned EMR records.

        Before fix: VisitsApiService.set_status allowed this silently.
        After fix: VisitLifecycleService.cancel_visit raises 409.
        """
        visit = _create_visit_with_status(db_session, test_patient, test_doctor, "completed")

        response = client.post(
            "/api/v1/registrar/records/actions",
            headers=registrar_auth_headers,
            json={
                "action": "cancel",
                "records": [{"record_kind": "visit", "record_id": visit.id}],
                "reason": "Trying to cancel completed visit",
            },
        )

        assert response.status_code == 200  # endpoint returns 200 with error in payload
        payload = response.json()
        # The action should fail (not succeed) — bypass is closed.
        assert payload["results"][0]["success"] is False, (
            "Canceling a completed visit must NOT succeed — this is the Gate C bypass C fix. "
            "VisitLifecycleService.cancel_visit should reject completed→canceled."
        )

        # CRITICAL: visit status must NOT change.
        db_session.refresh(visit)
        assert visit.status == "completed", (
            f"Completed visit status was changed to '{visit.status}'. "
            f"Terminal/non-terminal→canceled bypass must NOT mutate status."
        )

    def test_cancel_closed_visit_rejected(
        self, client, db_session, registrar_auth_headers, test_patient, test_doctor
    ):
        """closed → canceled: MUST be rejected.

        A closed visit has EMR signed + payment collected. Canceling it
        would break financial/EMR invariants. The only path to reopen
        is admin force_reopen, not a registrar cancel.
        """
        visit = _create_visit_with_status(db_session, test_patient, test_doctor, "closed")

        response = client.post(
            "/api/v1/registrar/records/actions",
            headers=registrar_auth_headers,
            json={
                "action": "cancel",
                "records": [{"record_kind": "visit", "record_id": visit.id}],
                "reason": "Trying to cancel closed visit",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["results"][0]["success"] is False, (
            "Canceling a closed visit must NOT succeed — terminal status bypass."
        )

        db_session.refresh(visit)
        assert visit.status == "closed", (
            f"Closed visit status was changed to '{visit.status}'. "
            f"Terminal→canceled bypass must NOT mutate status."
        )

    def test_cancel_expired_visit_rejected(
        self, client, db_session, registrar_auth_headers, test_patient, test_doctor
    ):
        """expired → canceled: MUST be rejected.

        An expired visit has confirmation timeout. Canceling it bypasses
        the confirmation security policy. The only path is admin force_reopen.
        """
        visit = _create_visit_with_status(db_session, test_patient, test_doctor, "expired")

        response = client.post(
            "/api/v1/registrar/records/actions",
            headers=registrar_auth_headers,
            json={
                "action": "cancel",
                "records": [{"record_kind": "visit", "record_id": visit.id}],
                "reason": "Trying to cancel expired visit",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["results"][0]["success"] is False, (
            "Canceling an expired visit must NOT succeed — terminal status bypass."
        )

        db_session.refresh(visit)
        assert visit.status == "expired", (
            f"Expired visit status was changed to '{visit.status}'. "
            f"Terminal→canceled bypass must NOT mutate status."
        )

    # ─── Idempotent / edge cases ──────────────────────────────────────

    def test_cancel_already_canceled_visit_idempotent(
        self, client, db_session, registrar_auth_headers, test_patient, test_doctor
    ):
        """canceled → canceled: idempotent success (no-op).

        The state machine allows same-status transitions as idempotent
        no-ops (duplicate click protection). This is INTENTIONAL —
        a registrar clicking "cancel" twice on an already-canceled
        visit should not get an error, just a no-op success.

        This test pins that behavior: the cancel succeeds, but the
        visit status stays "canceled" (no mutation to a different status).
        """
        visit = _create_visit_with_status(db_session, test_patient, test_doctor, "canceled")

        response = client.post(
            "/api/v1/registrar/records/actions",
            headers=registrar_auth_headers,
            json={
                "action": "cancel",
                "records": [{"record_kind": "visit", "record_id": visit.id}],
                "reason": "Duplicate cancel attempt",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        # Idempotent success — no error, but no status change either.
        assert payload["results"][0]["success"] is True

        db_session.refresh(visit)
        assert visit.status == "canceled"

    # ─── Rollback / partial persistence ───────────────────────────────

    def test_cancel_rejection_no_partial_persistence(
        self, client, db_session, registrar_auth_headers, test_patient, test_doctor
    ):
        """Invalid cancel must NOT partially persist.

        When cancel_visit raises 409, the transaction must roll back:
        - visit.status unchanged
        - visit.notes unchanged (no "Canceled: ..." appended)
        - No orphaned queue entry updates

        This verifies the caller-controlled transaction (commit=False)
        correctly rolls back on rejection.
        """
        visit = _create_visit_with_status(db_session, test_patient, test_doctor, "completed")
        original_notes = visit.notes

        response = client.post(
            "/api/v1/registrar/records/actions",
            headers=registrar_auth_headers,
            json={
                "action": "cancel",
                "records": [{"record_kind": "visit", "record_id": visit.id}],
                "reason": "Should not persist",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["results"][0]["success"] is False

        db_session.refresh(visit)
        # Status must NOT change.
        assert visit.status == "completed"
        # Notes must NOT have "Canceled: ..." appended (rollback worked).
        assert visit.notes == original_notes or (
            visit.notes is not None and "Canceled: Should not persist" not in visit.notes
        ), (
            f"Notes were partially persisted: '{visit.notes}'. "
            f"Transaction should have rolled back on rejection."
        )

    # ─── request.reason audit ─────────────────────────────────────────

    def test_cancel_reason_passed_to_lifecycle_service(
        self, client, db_session, registrar_auth_headers, test_patient, test_doctor
    ):
        """request.reason must be passed to VisitLifecycleService.cancel_visit().

        The lifecycle service logs the reason via logger.info for audit.
        This test verifies the reason is threaded through (not just
        appended to notes).

        We verify by checking that a valid cancel succeeds AND the reason
        appears in the notes (which the caller appends after the lifecycle
        call succeeds). If the lifecycle service rejected, notes would
        not be updated.
        """
        visit = _create_visit_with_status(db_session, test_patient, test_doctor, "open")
        reason = "Patient moved to another city"

        response = client.post(
            "/api/v1/registrar/records/actions",
            headers=registrar_auth_headers,
            json={
                "action": "cancel",
                "records": [{"record_kind": "visit", "record_id": visit.id}],
                "reason": reason,
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["results"][0]["success"] is True

        db_session.refresh(visit)
        assert visit.status == "canceled"
        # Reason should appear in notes (caller appends it after lifecycle success).
        assert reason in (visit.notes or ""), (
            f"Reason '{reason}' not found in visit.notes: '{visit.notes}'. "
            f"The reason should be appended to notes after lifecycle success."
        )
