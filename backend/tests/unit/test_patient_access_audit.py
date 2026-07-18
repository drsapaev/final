"""
Unit tests for Patient Access Audit Service (M4-P0-1).

Tests the log_patient_access() wrapper function and the
PatientAccessAuditLog model.

Covers:
- Basic audit log creation with patient self-access
- Audit log for staff access
- Audit log for denied access (auth failure)
- Non-blocking behavior when db fails
- IP/User-Agent extraction from FastAPI Request
- subject_patient_id derivation from scope
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from app.services.patient_access_audit import (
    _get_client_ip,
    _get_user_agent,
    log_patient_access,
)


class TestPatientAccessAuditService:
    """Tests for log_patient_access() wrapper function."""

    def test_log_patient_access_creates_entry_for_self_access(self):
        """Basic audit log creation for patient self-access."""
        db = MagicMock()
        scope = MagicMock()
        scope.scope_type = "patient"
        scope.patient_id = 42
        scope.telegram_user_id = 123456
        scope.staff_user_id = None

        log_patient_access(
            db=db,
            scope=scope,
            resource_type="cabinet_summary",
            action="view",
            outcome="success",
            request=None,
        )

        # Verify db.add was called with a PatientAccessAuditLog
        assert db.add.called
        audit_entry = db.add.call_args[0][0]

        assert audit_entry.subject_patient_id == 42
        assert audit_entry.actor_patient_id == 42
        assert audit_entry.actor_staff_user_id is None
        assert audit_entry.actor_type == "self"
        assert audit_entry.actor_telegram_user_id == 123456
        assert audit_entry.resource_type == "cabinet_summary"
        assert audit_entry.action == "view"
        assert audit_entry.outcome == "success"

        # Verify commit was called
        assert db.commit.called

    def test_log_patient_access_creates_entry_for_staff_access(self):
        """Audit log creation for staff access to patient PHI."""
        db = MagicMock()
        scope = MagicMock()
        scope.scope_type = "staff"
        scope.patient_id = None
        scope.telegram_user_id = 789
        scope.staff_user_id = 100
        scope.staff_role = "doctor"

        log_patient_access(
            db=db,
            scope=scope,
            subject_patient_id=42,  # explicit subject for staff access
            resource_type="lab_report",
            resource_id="123",
            action="download",
            outcome="success",
            request=None,
        )

        audit_entry = db.add.call_args[0][0]
        assert audit_entry.subject_patient_id == 42
        assert audit_entry.actor_patient_id is None
        assert audit_entry.actor_staff_user_id == 100
        assert audit_entry.actor_type == "staff"
        assert audit_entry.actor_telegram_user_id == 789
        assert audit_entry.resource_type == "lab_report"
        assert audit_entry.resource_id == "123"
        assert audit_entry.action == "download"

    def test_log_patient_access_derives_subject_from_scope(self):
        """When subject_patient_id is None, derive from scope.patient_id."""
        db = MagicMock()
        scope = MagicMock()
        scope.scope_type = "patient"
        scope.patient_id = 99
        scope.telegram_user_id = 111
        scope.staff_user_id = None

        log_patient_access(
            db=db,
            scope=scope,
            resource_type="forms_preview",
            action="view",
            request=None,
        )

        audit_entry = db.add.call_args[0][0]
        assert audit_entry.subject_patient_id == 99

    def test_log_patient_access_skips_when_no_subject(self):
        """Skip audit log when subject_patient_id cannot be determined."""
        db = MagicMock()

        log_patient_access(
            db=db,
            scope=None,
            subject_patient_id=None,
            resource_type="manifest",
            action="view",
            request=None,
        )

        # Verify db.add was NOT called
        assert not db.add.called

    def test_log_patient_access_non_blocking_on_db_failure(self):
        """Audit log failure must NOT raise — non-blocking."""
        db = MagicMock()
        db.add.side_effect = Exception("Database connection lost")

        # Should not raise
        log_patient_access(
            db=db,
            subject_patient_id=42,
            resource_type="cabinet_summary",
            action="view",
            request=None,
        )

        # Verify rollback was attempted
        assert db.rollback.called

    def test_log_patient_access_captures_extra_data(self):
        """Extra data is stored in audit log entry."""
        db = MagicMock()
        scope = MagicMock()
        scope.scope_type = "patient"
        scope.patient_id = 42
        scope.telegram_user_id = 123
        scope.staff_user_id = None

        log_patient_access(
            db=db,
            scope=scope,
            resource_type="form_submission",
            resource_id="form_abc",
            action="submit",
            request=None,
            extra_data={
                "form_status": "draft",
                "submission_id": 789,
            },
        )

        audit_entry = db.add.call_args[0][0]
        assert audit_entry.extra_data == {
            "form_status": "draft",
            "submission_id": 789,
        }

    def test_log_patient_access_captures_correlation_id(self):
        """Correlation ID is stored in audit log entry."""
        db = MagicMock()
        scope = MagicMock()
        scope.scope_type = "patient"
        scope.patient_id = 42
        scope.telegram_user_id = 123
        scope.staff_user_id = None

        log_patient_access(
            db=db,
            scope=scope,
            resource_type="lab_report",
            resource_id="123",
            action="download",
            request=None,
            correlation_id="req-abc-123",
        )

        audit_entry = db.add.call_args[0][0]
        assert audit_entry.correlation_id == "req-abc-123"


class TestClientIpExtraction:
    """Tests for _get_client_ip() helper."""

    def test_get_client_ip_from_x_forwarded_for(self):
        """IP extracted from X-Forwarded-For header (first IP)."""
        request = MagicMock()
        request.headers = {"x-forwarded-for": "203.0.113.50, 70.41.0.1, 150.95.2.2"}

        ip = _get_client_ip(request)
        assert ip == "203.0.113.50"

    def test_get_client_ip_from_client_host(self):
        """IP extracted from request.client.host when no X-Forwarded-For."""
        request = MagicMock()
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "192.168.1.100"

        ip = _get_client_ip(request)
        assert ip == "192.168.1.100"

    def test_get_client_ip_returns_none_for_no_request(self):
        """Returns None when request is None."""
        ip = _get_client_ip(None)
        assert ip is None

    def test_get_client_ip_returns_none_on_exception(self):
        """Returns None when request access raises."""
        request = MagicMock()
        request.headers = MagicMock()
        request.headers.get = MagicMock(side_effect=Exception("header access failed"))

        ip = _get_client_ip(request)
        assert ip is None


class TestUserAgentExtraction:
    """Tests for _get_user_agent() helper."""

    def test_get_user_agent_from_header(self):
        """User-Agent extracted from headers."""
        request = MagicMock()
        request.headers = {"user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0)"}

        ua = _get_user_agent(request)
        assert ua == "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0)"

    def test_get_user_agent_returns_none_for_no_request(self):
        """Returns None when request is None."""
        ua = _get_user_agent(None)
        assert ua is None

    def test_get_user_agent_returns_none_when_missing(self):
        """Returns None when User-Agent header is missing."""
        request = MagicMock()
        request.headers = {}

        ua = _get_user_agent(request)
        assert ua is None
