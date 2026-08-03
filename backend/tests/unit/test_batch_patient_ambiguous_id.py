"""Tests for structured ambiguous-id error (Issue #6).

Validates that when an entry ID matches both an OnlineQueueEntry and a
Visit, the service returns a structured error with error_code
'ambiguous_entry_id' instead of a bare string.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.services.batch_patient_service import (
    BatchPatientService,
    BatchUpdateRequest,
    EntryAction,
)


@pytest.mark.unit
class TestStructuredAmbiguousIdError:
    """Verify structured error_code propagation for ambiguous entry IDs."""

    def _make_service(self, db_session, entry_exists=True, visit_exists=True):
        """Create a service where _resolve_existing_entry_target returns
        ambiguous error (both entry and visit found for same ID)."""
        entry = SimpleNamespace(
            id=123, patient_id=1, queue_id=1, status="waiting",
            service_id=None, service_code=None, cancel_reason=None,
        ) if entry_exists else None
        visit = SimpleNamespace(
            id=123, patient_id=1, visit_date=None, status="open",
            doctor_id=None, cost=0,
        ) if visit_exists else None

        service = BatchPatientService.__new__(BatchPatientService)
        service.db = db_session

        # Mock _find_online_queue_entry_for_action and _find_visit_for_action
        service._find_online_queue_entry_for_action = Mock(return_value=entry)
        service._find_visit_for_action = Mock(return_value=visit)

        return service

    def test_ambiguous_entry_returns_error_code(self, db_session):
        """When both online_queue entry and visit match the same ID,
        _resolve_existing_entry_target returns a dict with 'code' and
        'message' keys."""
        service = self._make_service(db_session)
        action = EntryAction(id=123, action="cancel")

        entry_type, target, error = service._resolve_existing_entry_target(
            patient_id=1,
            target_date=__import__("datetime").date(2026, 1, 1),
            action=action,
        )

        assert entry_type is None
        assert target is None
        assert isinstance(error, dict)
        assert error["code"] == "ambiguous_entry_id"
        assert "entry_type" in error["message"]

    def test_entry_not_found_returns_error_code(self, db_session):
        """When neither entry nor visit is found, error has 'entry_not_found' code."""
        service = self._make_service(db_session, entry_exists=False, visit_exists=False)
        action = EntryAction(id=999, action="cancel")

        entry_type, target, error = service._resolve_existing_entry_target(
            patient_id=1,
            target_date=__import__("datetime").date(2026, 1, 1),
            action=action,
        )

        assert isinstance(error, dict)
        assert error["code"] == "entry_not_found"

    def test_cancel_entry_propagates_error_code(self, db_session):
        """_cancel_entry propagates error_code from _resolve_existing_entry_target."""
        service = self._make_service(db_session)
        action = EntryAction(id=123, action="cancel")

        result = service._cancel_entry(
            patient_id=1,
            target_date=__import__("datetime").date(2026, 1, 1),
            action=action,
        )

        assert result.status == "error"
        assert result.error_code == "ambiguous_entry_id"
        assert "entry_type" in result.error

    def test_update_entry_propagates_error_code(self, db_session):
        """_update_entry propagates error_code from _resolve_existing_entry_target."""
        service = self._make_service(db_session)
        action = EntryAction(id=123, action="update", status="called")

        result = service._update_entry(
            patient_id=1,
            target_date=__import__("datetime").date(2026, 1, 1),
            action=action,
        )

        assert result.status == "error"
        assert result.error_code == "ambiguous_entry_id"

    def test_batch_update_propagates_error_code_to_response(self, db_session):
        """BatchUpdateResponse.error_code is set when an entry has error_code."""
        service = self._make_service(db_session)
        action = EntryAction(id=123, action="cancel")
        request = BatchUpdateRequest(entries=[action])

        result = service.batch_update(
            patient_id=1,
            target_date=__import__("datetime").date(2026, 1, 1),
            request=request,
        )

        assert result.success is False
        assert result.error_code == "ambiguous_entry_id"

    def test_entry_result_has_error_code_field(self):
        """EntryResult model has error_code field (optional)."""
        from app.services.batch_patient_service import EntryResult

        result = EntryResult(id=1, status="error", error="test", error_code="test_code")
        assert result.error_code == "test_code"

        # Also works without error_code (backward compat)
        result_no_code = EntryResult(id=1, status="updated")
        assert result_no_code.error_code is None

    def test_batch_update_response_has_error_code_field(self):
        """BatchUpdateResponse model has error_code field (optional)."""
        from app.services.batch_patient_service import BatchUpdateResponse

        resp = BatchUpdateResponse(
            success=False, patient_id=1, date="2026-01-01",
            updated_entries=[], error="failed", error_code="ambiguous_entry_id"
        )
        assert resp.error_code == "ambiguous_entry_id"

        # Also works without error_code (backward compat)
        resp_no_code = BatchUpdateResponse(
            success=True, patient_id=1, date="2026-01-01", updated_entries=[]
        )
        assert resp_no_code.error_code is None
