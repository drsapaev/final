"""
Unit tests for M5.3 (Sensitive Actions), M5.4 (Reason Codes), M5.7 (Rate Limiting).
"""
from __future__ import annotations

import pytest

from app.services.sensitive_actions import (
    SENSITIVE_ACTIONS,
    get_event_type,
    get_sensitive_action,
    is_sensitive_action,
)
from app.services.reason_codes import ReasonCode, REASON_CONTEXTS
from app.services.rate_limits import RATE_LIMITS, get_rate_limit, is_rate_limiting_active


class TestSensitiveActions:
    """M5.3: Sensitive Action definitions."""

    def test_is_sensitive_action_returns_true_for_known(self):
        assert is_sensitive_action("emr", "view") is True
        assert is_sensitive_action("lab_report", "delete") is True
        assert is_sensitive_action("user", "create") is True
        assert is_sensitive_action("payment", "edit") is True

    def test_is_sensitive_action_returns_false_for_unknown(self):
        assert is_sensitive_action("unknown", "view") is False
        assert is_sensitive_action("emr", "unknown") is False

    def test_get_event_type_returns_correct_type(self):
        assert get_event_type("emr", "view") == "DOCTOR_OPEN_EMR"
        assert get_event_type("lab_report", "finalize") == "LAB_REPORT_FINALIZE"
        assert get_event_type("user", "create") == "ADMIN_CREATE_USER"

    def test_get_event_type_returns_none_for_unknown(self):
        assert get_event_type("unknown", "view") is None

    def test_get_sensitive_action_returns_definition(self):
        sa = get_sensitive_action("emr", "view")
        assert sa is not None
        assert sa.event_type == "DOCTOR_OPEN_EMR"
        assert sa.resource_type == "emr"
        assert sa.action == "view"

    def test_all_sensitive_actions_have_unique_event_types(self):
        event_types = [a.event_type for a in SENSITIVE_ACTIONS]
        assert len(event_types) == len(set(event_types)), "Duplicate event_types found"

    def test_sensitive_actions_cover_all_critical_areas(self):
        """Verify all critical areas are covered."""
        resource_types = {a.resource_type for a in SENSITIVE_ACTIONS}
        expected = {"emr", "prescription", "lab_report", "patient", "appointment",
                     "user", "data", "payment", "refund", "session", "emergency_token",
                     "endpoint", "secret"}
        assert expected.issubset(resource_types), f"Missing: {expected - resource_types}"


class TestReasonCodes:
    """M5.4: Reason Codes."""

    def test_consultation_reason(self):
        rc = ReasonCode.consultation(5832)
        d = rc.to_dict()
        assert d["context"] == "consultation"
        assert d["id"] == 5832

    def test_appointment_reason(self):
        rc = ReasonCode.appointment(4471)
        d = rc.to_dict()
        assert d["context"] == "appointment"
        assert d["id"] == 4471

    def test_visit_reason(self):
        rc = ReasonCode.visit(99)
        d = rc.to_dict()
        assert d["context"] == "visit"
        assert d["id"] == 99

    def test_emergency_reason(self):
        rc = ReasonCode.emergency(note="Patient collapsed in waiting room")
        d = rc.to_dict()
        assert d["context"] == "emergency"
        assert d["note"] == "Patient collapsed in waiting room"
        assert "id" not in d

    def test_scheduled_report_reason(self):
        rc = ReasonCode.scheduled_report("monthly_report_july_2026")
        d = rc.to_dict()
        assert d["context"] == "scheduled_report"
        assert d["note"] == "monthly_report_july_2026"

    def test_user_request_reason(self):
        rc = ReasonCode.user_request(42)
        d = rc.to_dict()
        assert d["context"] == "user_request"
        assert d["id"] == 42

    def test_system_reason(self):
        rc = ReasonCode.system(note="automated cleanup")
        d = rc.to_dict()
        assert d["context"] == "system"

    def test_to_dict_excludes_none_fields(self):
        rc = ReasonCode(context="test")
        d = rc.to_dict()
        assert d == {"context": "test"}
        assert "id" not in d
        assert "note" not in d

    def test_reason_contexts_list_has_entries(self):
        assert len(REASON_CONTEXTS) >= 7
        assert any(c["value"] == "consultation" for c in REASON_CONTEXTS)


class TestRateLimits:
    """M5.7: Rate Limiting."""

    def test_get_rate_limit_returns_defined_limit(self):
        assert get_rate_limit("login") == "5/5minutes"
        assert get_rate_limit("report_download") == "10/minute"
        assert get_rate_limit("data_export") == "3/hour"

    def test_get_rate_limit_returns_default_for_unknown(self):
        assert get_rate_limit("unknown_endpoint") == "60/minute"

    def test_all_critical_endpoints_have_limits(self):
        critical = ["login", "report_download", "data_export", "password_reset", "emergency_token"]
        for endpoint in critical:
            assert endpoint in RATE_LIMITS, f"Missing rate limit for {endpoint}"

    def test_is_rate_limiting_active_returns_bool(self):
        assert isinstance(is_rate_limiting_active(), bool)

    def test_rate_limits_are_reasonable(self):
        """Rate limits should not be too restrictive or too permissive."""
        assert "5/5minutes" in RATE_LIMITS["login"]  # Not too strict
        assert "60/minute" in RATE_LIMITS["default"]  # Default exists
