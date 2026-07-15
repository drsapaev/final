"""
Unit tests for Unified Audit Service (M5.1 + M5.5).
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.audit_service import log_audit_event, _get_client_ip, _get_user_agent


class TestLogAuditEvent:
    """Tests for log_audit_event()."""

    def test_creates_audit_log_entry(self):
        """Audit log entry is created on success."""
        db = MagicMock()
        log_audit_event(
            db=db,
            event_type="DOCTOR_OPEN_EMR",
            actor_user_id=1,
            actor_role="doctor",
            subject_patient_id=42,
            resource_type="emr",
            resource_id="123",
            action="view",
            outcome="success",
        )
        assert db.add.called
        entry = db.add.call_args[0][0]
        assert entry.event_type == "DOCTOR_OPEN_EMR"
        assert entry.actor_user_id == 1
        assert entry.subject_patient_id == 42
        assert entry.action == "view"
        assert db.commit.called

    def test_non_blocking_on_failure(self):
        """Audit failure does NOT raise."""
        db = MagicMock()
        db.add.side_effect = Exception("DB error")
        log_audit_event(
            db=db,
            event_type="TEST",
            action="view",
        )
        assert db.rollback.called

    def test_captures_reason_code(self):
        """Reason code is stored."""
        db = MagicMock()
        log_audit_event(
            db=db,
            event_type="DOCTOR_OPEN_EMR",
            action="view",
            reason_code={"context": "consultation", "id": 5832},
        )
        entry = db.add.call_args[0][0]
        assert entry.reason_code == {"context": "consultation", "id": 5832}

    def test_captures_extra_data(self):
        """Extra data is stored."""
        db = MagicMock()
        log_audit_event(
            db=db,
            event_type="ADMIN_EXPORT",
            action="export",
            extra_data={"format": "csv", "rows": 1500},
        )
        entry = db.add.call_args[0][0]
        assert entry.extra_data == {"format": "csv", "rows": 1500}

    def test_patient_actor(self):
        """Patient actor fields are set correctly."""
        db = MagicMock()
        log_audit_event(
            db=db,
            event_type="PATIENT_REPORT_DOWNLOAD",
            actor_patient_id=42,
            actor_type="patient",
            subject_patient_id=42,
            resource_type="lab_report",
            resource_id="99",
            action="download",
        )
        entry = db.add.call_args[0][0]
        assert entry.actor_patient_id == 42
        assert entry.actor_type == "patient"
        assert entry.actor_user_id is None


class TestClientIpExtraction:
    def test_from_x_forwarded_for(self):
        request = MagicMock()
        request.headers = {"x-forwarded-for": "203.0.113.50, 10.0.0.1"}
        assert _get_client_ip(request) == "203.0.113.50"

    def test_from_client_host(self):
        request = MagicMock()
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "192.168.1.1"
        assert _get_client_ip(request) == "192.168.1.1"

    def test_none_request(self):
        assert _get_client_ip(None) is None


class TestUserAgentExtraction:
    def test_from_header(self):
        request = MagicMock()
        request.headers = {"user-agent": "Mozilla/5.0"}
        assert _get_user_agent(request) == "Mozilla/5.0"

    def test_none_request(self):
        assert _get_user_agent(None) is None


class TestAuditLogModel:
    def test_model_has_expected_fields(self):
        from app.models.audit import AuditLog
        assert AuditLog.__tablename__ == "audit_logs"
        mapper = AuditLog.__mapper__
        cols = set(mapper.columns.keys())
        expected = {
            "id", "event_type", "actor_user_id", "actor_patient_id",
            "actor_role", "actor_type", "subject_patient_id",
            "resource_type", "resource_id", "action", "outcome",
            "reason_code", "ip_address", "user_agent", "session_id",
            "payload", "created_at",
        }
        assert expected.issubset(cols), f"Missing: {expected - cols}"
