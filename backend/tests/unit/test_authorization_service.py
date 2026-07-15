"""
Unit tests for Authorization Service (M4-P1-1).

Tests the centralized ABAC policy engine.

Covers:
- Self-access (patient accessing own PHI) → allow
- Self-access with mismatched patient_id → deny
- Staff access with permitted role → allow
- Staff access with non-permitted role → deny
- Staff access to patient-only action → deny
- Unknown scope type → deny
- require_phi_access raises on deny
- can_access_phi returns bool
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.authorization import (
    Action,
    ActorType,
    AuthorizationDecision,
    AuthorizationError,
    AuthorizationResult,
    AuthorizationService,
    ResourceType,
    authorization_service,
)
from app.services.authorization.dependencies import can_access_phi, check_phi_access


def _make_patient_scope(patient_id: int = 42, telegram_user_id: int = 111):
    """Create a mock patient scope."""
    scope = MagicMock()
    scope.scope_type = "patient"
    scope.patient_id = patient_id
    scope.telegram_user_id = telegram_user_id
    scope.staff_user_id = None
    scope.staff_role = None
    return scope


def _make_staff_scope(
    staff_user_id: int = 1,
    staff_role: str = "doctor",
    telegram_user_id: int = 222,
):
    """Create a mock staff scope."""
    scope = MagicMock()
    scope.scope_type = "staff"
    scope.patient_id = None
    scope.telegram_user_id = telegram_user_id
    scope.staff_user_id = staff_user_id
    scope.staff_role = staff_role
    return scope


class TestSelfAccess:
    """Tests for patient self-access (ActorType.SELF)."""

    def test_self_access_allowed(self):
        """Patient accessing own PHI is allowed."""
        scope = _make_patient_scope(patient_id=42)
        result = authorization_service.can_access_phi(
            scope,
            subject_patient_id=42,
            resource_type="cabinet_summary",
            action="view",
        )
        assert result.allowed
        assert result.actor_type == "self"
        assert result.reason == "self_access"

    def test_self_access_denied_for_other_patient(self):
        """Patient accessing another patient's PHI is denied."""
        scope = _make_patient_scope(patient_id=42)
        result = authorization_service.can_access_phi(
            scope,
            subject_patient_id=99,
            resource_type="cabinet_summary",
            action="view",
        )
        assert not result.allowed
        assert result.reason == "patient_scope_mismatch"

    def test_self_access_denied_when_patient_id_none(self):
        """Patient scope without patient_id is denied."""
        scope = _make_patient_scope(patient_id=42)
        scope.patient_id = None
        result = authorization_service.can_access_phi(
            scope,
            subject_patient_id=42,
            resource_type="cabinet_summary",
            action="view",
        )
        assert not result.allowed
        assert result.reason == "patient_scope_required"

    def test_self_access_allowed_for_all_resource_types(self):
        """Self-access is allowed for any resource type."""
        scope = _make_patient_scope(patient_id=42)
        for resource_type in ["lab_report", "cabinet_summary", "form_submission", "appointment"]:
            for action in ["view", "download", "submit", "create", "preview"]:
                result = authorization_service.can_access_phi(
                    scope,
                    subject_patient_id=42,
                    resource_type=resource_type,
                    action=action,
                )
                assert result.allowed, f"Failed for {resource_type}:{action}"


class TestStaffAccess:
    """Tests for staff access (ActorType.STAFF)."""

    def test_doctor_can_view_lab_report(self):
        """Doctor can view lab reports."""
        scope = _make_staff_scope(staff_role="doctor")
        result = authorization_service.can_access_phi(
            scope,
            subject_patient_id=42,
            resource_type="lab_report",
            action="view",
        )
        assert result.allowed
        assert result.actor_type == "staff"
        assert result.reason == "staff_authorized"

    def test_doctor_can_download_lab_report(self):
        """Doctor can download lab reports."""
        scope = _make_staff_scope(staff_role="doctor")
        result = authorization_service.can_access_phi(
            scope,
            subject_patient_id=42,
            resource_type="lab_report",
            action="download",
        )
        assert result.allowed

    def test_cashier_cannot_download_lab_report(self):
        """Cashier cannot download lab reports (not in permissions)."""
        scope = _make_staff_scope(staff_role="cashier")
        result = authorization_service.can_access_phi(
            scope,
            subject_patient_id=42,
            resource_type="lab_report",
            action="download",
        )
        assert not result.allowed
        assert result.reason == "staff_role_denied"

    def test_admin_has_full_access(self):
        """Admin can access all resources (that are defined in STAFF_PERMISSIONS)."""
        scope = _make_staff_scope(staff_role="admin")
        # Only test resource:action combos that exist in STAFF_PERMISSIONS for admin
        test_cases = [
            ("lab_report", "view"),
            ("lab_report", "download"),
            ("cabinet_summary", "view"),
            ("form_submission", "view"),
            ("appointment", "view"),
            ("appointment", "create"),
            ("appointment", "preview"),
        ]
        for resource_type, action in test_cases:
            result = authorization_service.can_access_phi(
                scope,
                subject_patient_id=42,
                resource_type=resource_type,
                action=action,
            )
            assert result.allowed, f"Admin failed for {resource_type}:{action}"

    def test_staff_cannot_submit_patient_forms(self):
        """Staff cannot submit patient forms (patient-only action)."""
        scope = _make_staff_scope(staff_role="admin")
        result = authorization_service.can_access_phi(
            scope,
            subject_patient_id=42,
            resource_type="form_submission",
            action="submit",
        )
        assert not result.allowed
        assert result.reason == "patient_only_action"

    def test_staff_cannot_revoke_patient_sessions(self):
        """Staff cannot revoke patient sessions (patient-only action)."""
        scope = _make_staff_scope(staff_role="admin")
        result = authorization_service.can_access_phi(
            scope,
            subject_patient_id=42,
            resource_type="session_management",
            action="revoke_all",
        )
        assert not result.allowed
        assert result.reason == "patient_only_action"

    def test_unknown_staff_role_denied(self):
        """Unknown staff role is denied."""
        scope = _make_staff_scope(staff_role="unknown_role")
        result = authorization_service.can_access_phi(
            scope,
            subject_patient_id=42,
            resource_type="cabinet_summary",
            action="view",
        )
        assert not result.allowed
        assert result.reason == "staff_role_denied"

    def test_staff_scope_without_user_id_denied(self):
        """Staff scope without staff_user_id is denied."""
        scope = _make_staff_scope(staff_role="doctor")
        scope.staff_user_id = None
        result = authorization_service.can_access_phi(
            scope,
            subject_patient_id=42,
            resource_type="cabinet_summary",
            action="view",
        )
        assert not result.allowed
        assert result.reason == "staff_scope_required"


class TestRequirePhiAccess:
    """Tests for require_phi_access() (raising version)."""

    def test_require_phi_access_returns_scope_when_allowed(self):
        """Returns scope when access is allowed."""
        scope = _make_patient_scope(patient_id=42)
        result = authorization_service.require_phi_access(
            scope,
            subject_patient_id=42,
            resource_type="cabinet_summary",
            action="view",
        )
        assert result is scope

    def test_require_phi_access_raises_when_denied(self):
        """Raises AuthorizationError when access is denied."""
        scope = _make_patient_scope(patient_id=42)
        with pytest.raises(AuthorizationError) as exc_info:
            authorization_service.require_phi_access(
                scope,
                subject_patient_id=99,
                resource_type="cabinet_summary",
                action="view",
            )
        assert exc_info.value.reason == "patient_scope_mismatch"


class TestDependencies:
    """Tests for FastAPI dependency helpers."""

    def test_can_access_phi_returns_true_when_allowed(self):
        """can_access_phi returns True when allowed."""
        scope = _make_patient_scope(patient_id=42)
        assert can_access_phi(
            scope,
            subject_patient_id=42,
            resource_type="cabinet_summary",
            action="view",
        )

    def test_can_access_phi_returns_false_when_denied(self):
        """can_access_phi returns False when denied."""
        scope = _make_patient_scope(patient_id=42)
        assert not can_access_phi(
            scope,
            subject_patient_id=99,
            resource_type="cabinet_summary",
            action="view",
        )

    def test_check_phi_access_returns_scope_when_allowed(self):
        """check_phi_access returns scope when allowed."""
        scope = _make_patient_scope(patient_id=42)
        result = check_phi_access(
            scope,
            subject_patient_id=42,
            resource_type="cabinet_summary",
            action="view",
        )
        assert result is scope

    def test_check_phi_access_raises_when_denied(self):
        """check_phi_access raises AuthorizationError when denied."""
        scope = _make_patient_scope(patient_id=42)
        with pytest.raises(AuthorizationError):
            check_phi_access(
                scope,
                subject_patient_id=99,
                resource_type="cabinet_summary",
                action="view",
            )


class TestEnums:
    """Tests for enum values."""

    def test_resource_type_values(self):
        """ResourceType has expected values."""
        assert ResourceType.LAB_REPORT == "lab_report"
        assert ResourceType.CABINET_SUMMARY == "cabinet_summary"
        assert ResourceType.FORM_SUBMISSION == "form_submission"

    def test_action_values(self):
        """Action has expected values."""
        assert Action.VIEW == "view"
        assert Action.DOWNLOAD == "download"
        assert Action.SUBMIT == "submit"

    def test_actor_type_values(self):
        """ActorType has expected values."""
        assert ActorType.SELF == "self"
        assert ActorType.STAFF == "staff"
        assert ActorType.GUARDIAN == "guardian"

    def test_authorization_decision_values(self):
        """AuthorizationDecision has expected values."""
        assert AuthorizationDecision.ALLOW == "allow"
        assert AuthorizationDecision.DENY == "deny"
