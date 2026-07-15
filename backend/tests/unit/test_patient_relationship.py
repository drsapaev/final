"""
Unit tests for Patient Relationship Model + Context Roles (M4-P1-3).

Tests:
- PatientRelationship model methods (is_valid_now, has_permission)
- AuthorizationService with guardian/heir/caregiver relationships
- Relationship with full permissions (null)
- Relationship with specific permissions (JSON dict)
- Expired relationship denied
- Inactive relationship denied
- No relationship → denied
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.services.authorization import (
    AuthorizationDecision,
    AuthorizationService,
    authorization_service,
)


class TestPatientRelationshipModel:
    """Tests for PatientRelationship model methods."""

    def test_is_valid_now_returns_true_for_active_unbounded(self):
        """Active relationship with no time bounds is valid."""
        from app.models.patient_relationship import PatientRelationship

        rel = PatientRelationship()
        rel.active = True
        rel.valid_from = None
        rel.valid_to = None

        assert rel.is_valid_now() is True

    def test_is_valid_now_returns_false_for_inactive(self):
        """Inactive relationship is not valid."""
        from app.models.patient_relationship import PatientRelationship

        rel = PatientRelationship()
        rel.active = False

        assert rel.is_valid_now() is False

    def test_is_valid_now_returns_false_for_future_start(self):
        """Relationship not yet valid (valid_from in future)."""
        from app.models.patient_relationship import PatientRelationship

        rel = PatientRelationship()
        rel.active = True
        rel.valid_from = datetime.now(UTC) + timedelta(days=1)
        rel.valid_to = None

        assert rel.is_valid_now() is False

    def test_is_valid_now_returns_false_for_past_end(self):
        """Relationship expired (valid_to in past)."""
        from app.models.patient_relationship import PatientRelationship

        rel = PatientRelationship()
        rel.active = True
        rel.valid_from = None
        rel.valid_to = datetime.now(UTC) - timedelta(days=1)

        assert rel.is_valid_now() is False

    def test_has_permission_returns_true_for_null_permissions(self):
        """Null permissions = full access."""
        from app.models.patient_relationship import PatientRelationship

        rel = PatientRelationship()
        rel.permissions = None  # Full access

        assert rel.has_permission("lab_report", "view") is True
        assert rel.has_permission("cabinet_summary", "view") is True
        assert rel.has_permission("anything", "anything") is True

    def test_has_permission_returns_false_for_empty_permissions(self):
        """Empty dict permissions = no access."""
        from app.models.patient_relationship import PatientRelationship

        rel = PatientRelationship()
        rel.permissions = {}  # No access

        assert rel.has_permission("lab_report", "view") is False

    def test_has_permission_returns_true_for_matching_list(self):
        """Specific permission in list is allowed."""
        from app.models.patient_relationship import PatientRelationship

        rel = PatientRelationship()
        rel.permissions = {
            "lab_report": ["view", "download"],
            "cabinet_summary": ["view"],
        }

        assert rel.has_permission("lab_report", "view") is True
        assert rel.has_permission("lab_report", "download") is True
        assert rel.has_permission("cabinet_summary", "view") is True

    def test_has_permission_returns_false_for_non_matching(self):
        """Permission not in list is denied."""
        from app.models.patient_relationship import PatientRelationship

        rel = PatientRelationship()
        rel.permissions = {
            "lab_report": ["view"],
        }

        assert rel.has_permission("lab_report", "download") is False
        assert rel.has_permission("cabinet_summary", "view") is False


class TestRelationshipType:
    """Tests for RelationshipType constants."""

    def test_relationship_type_values(self):
        """RelationshipType has expected values."""
        from app.models.patient_relationship import RelationshipType

        assert RelationshipType.GUARDIAN == "guardian"
        assert RelationshipType.HEIR == "heir"
        assert RelationshipType.CAREGIVER == "caregiver"


class TestAuthorizationServiceWithRelationships:
    """Tests for AuthorizationService._check_relationship_access()."""

    def test_guardian_access_allowed_with_full_permissions(self):
        """Guardian with null permissions (full access) is allowed."""
        scope = MagicMock()
        scope.scope_type = "patient"
        scope.patient_id = 42  # Guardian
        scope.telegram_user_id = 111
        scope.staff_user_id = None
        scope.staff_role = None

        mock_rel = MagicMock()
        mock_rel.is_valid_now.return_value = True
        mock_rel.has_permission.return_value = True
        mock_rel.relationship_type = "guardian"

        with patch(
            "app.services.authorization.authorization_service._check_relationship_access"
        ) as mock_check:
            mock_check.return_value = MagicMock(
                allowed=True,
                decision=AuthorizationDecision.ALLOW,
                reason="relationship_access:guardian",
                actor_type="guardian",
            )

            result = authorization_service.can_access_phi(
                scope,
                subject_patient_id=99,  # Child
                resource_type="cabinet_summary",
                action="view",
            )

        assert result.allowed
        assert result.actor_type == "guardian"

    def test_no_relationship_denied(self):
        """No relationship between actor and subject → denied."""
        scope = MagicMock()
        scope.scope_type = "patient"
        scope.patient_id = 42
        scope.telegram_user_id = 111
        scope.staff_user_id = None
        scope.staff_role = None

        with patch(
            "app.services.authorization.authorization_service._check_relationship_access"
        ) as mock_check:
            mock_check.return_value = MagicMock(
                allowed=False,
                decision=AuthorizationDecision.DENY,
                reason="patient_scope_mismatch",
                actor_type="self",
            )

            result = authorization_service.can_access_phi(
                scope,
                subject_patient_id=99,
                resource_type="cabinet_summary",
                action="view",
            )

        assert not result.allowed
        assert result.reason == "patient_scope_mismatch"

    def test_relationship_permission_denied(self):
        """Relationship exists but doesn't grant specific permission."""
        scope = MagicMock()
        scope.scope_type = "patient"
        scope.patient_id = 42
        scope.telegram_user_id = 111
        scope.staff_user_id = None
        scope.staff_role = None

        with patch(
            "app.services.authorization.authorization_service._check_relationship_access"
        ) as mock_check:
            mock_check.return_value = MagicMock(
                allowed=False,
                decision=AuthorizationDecision.DENY,
                reason="relationship_permission_denied",
                actor_type="self",
            )

            result = authorization_service.can_access_phi(
                scope,
                subject_patient_id=99,
                resource_type="lab_report",
                action="download",
            )

        assert not result.allowed
        assert result.reason == "relationship_permission_denied"

    def test_self_access_still_works_with_relationships(self):
        """Self-access is checked first — relationships only for non-self."""
        scope = MagicMock()
        scope.scope_type = "patient"
        scope.patient_id = 42
        scope.telegram_user_id = 111
        scope.staff_user_id = None
        scope.staff_role = None

        result = authorization_service.can_access_phi(
            scope,
            subject_patient_id=42,  # Same as scope.patient_id → self-access
            resource_type="cabinet_summary",
            action="view",
        )

        assert result.allowed
        assert result.reason == "self_access"
        assert result.actor_type == "self"
