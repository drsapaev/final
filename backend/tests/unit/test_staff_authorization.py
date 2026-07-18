"""
Unit tests for Staff Authorization Service (M5.2).

Tests the centralized authorization engine for staff endpoints.
Covers all roles × all permissions + ownership checks.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.authorization.staff import (
    StaffAuthorizationError,
    StaffAuthorizationService,
    normalize_role,
    staff_authorization_service,
)


def _make_user(role: str = "doctor", user_id: int = 1, is_superuser: bool = False):
    """Create a mock User with the given role."""
    user = MagicMock()
    user.role = role
    user.id = user_id
    user.is_superuser = is_superuser
    user.is_active = True
    return user


def _make_appointment(doctor_id=None, patient_id=None):
    """Create a mock Appointment."""
    apt = MagicMock()
    apt.doctor_id = doctor_id
    apt.patient_id = patient_id
    return apt


class TestNormalizeRole:
    """Tests for role normalization."""

    @pytest.mark.parametrize("input_role,expected", [
        ("Admin", "admin"),
        ("admin", "admin"),
        ("administrator", "admin"),
        ("super_admin", "admin"),
        ("Doctor", "doctor"),
        ("doctor", "doctor"),
        ("cardio", "doctor"),
        ("cardiology", "doctor"),
        ("Cardiologist", "doctor"),
        ("derma", "doctor"),
        ("dentist", "doctor"),
        ("Registrar", "registrar"),
        ("registrar", "registrar"),
        ("receptionist", "registrar"),
        ("Cashier", "cashier"),
        ("cashier", "cashier"),
        ("Lab", "lab"),
        ("lab", "lab"),
        ("lab_tech", "lab"),
        ("laboratory", "lab"),
        ("Patient", "patient"),
        ("patient", "patient"),
        ("unknown_role", "unknown"),
        (None, "unknown"),
        ("", "unknown"),
    ])
    def test_normalize_role(self, input_role, expected):
        assert normalize_role(input_role) == expected


class TestPermissionMatrix:
    """Tests for the permission matrix across all roles."""

    def test_admin_has_all_permissions(self):
        """Admin has all permissions."""
        user = _make_user(role="Admin")
        perms = staff_authorization_service._get_permissions(user)
        assert "appointment:read" in perms
        assert "users:manage" in perms
        assert "export:data" in perms
        assert "security:dashboard" in perms

    def test_doctor_permissions(self):
        """Doctor has expected permissions."""
        user = _make_user(role="Doctor")
        perms = staff_authorization_service._get_permissions(user)
        assert "appointment:read" in perms
        assert "appointment:write" in perms
        assert "patient:read" in perms
        assert "emr:read" in perms
        assert "emr:write" in perms
        assert "ai:access" in perms
        # Doctor CANNOT:
        assert "users:manage" not in perms
        assert "payments:manage" not in perms
        assert "export:data" not in perms
        assert "security:dashboard" not in perms

    def test_registrar_permissions(self):
        """Registrar has expected permissions."""
        user = _make_user(role="Registrar")
        perms = staff_authorization_service._get_permissions(user)
        assert "appointment:read" in perms
        assert "appointment:write" in perms
        assert "patient:read" in perms
        assert "patient:write" in perms
        assert "queue:manage" in perms
        # Registrar CANNOT:
        assert "emr:write" not in perms
        assert "users:manage" not in perms
        assert "payments:manage" not in perms

    def test_cashier_permissions(self):
        """Cashier has expected permissions."""
        user = _make_user(role="Cashier")
        perms = staff_authorization_service._get_permissions(user)
        assert "appointment:read" in perms
        assert "patient:read" in perms
        assert "payments:manage" in perms
        # Cashier CANNOT:
        assert "appointment:write" not in perms
        assert "emr:read" not in perms
        assert "queue:manage" not in perms
        assert "users:manage" not in perms

    def test_lab_permissions(self):
        """Lab has expected permissions."""
        user = _make_user(role="Lab")
        perms = staff_authorization_service._get_permissions(user)
        assert "lab:read" in perms
        assert "lab:write" in perms
        assert "patient:read" in perms
        # Lab CANNOT:
        assert "emr:read" not in perms
        assert "queue:manage" not in perms
        assert "payments:manage" not in perms

    def test_patient_permissions(self):
        """Patient has minimal permissions."""
        user = _make_user(role="Patient")
        perms = staff_authorization_service._get_permissions(user)
        assert "appointment:read" in perms
        assert "patient:read" in perms
        # Patient CANNOT:
        assert "emr:read" not in perms
        assert "queue:manage" not in perms
        assert "users:manage" not in perms

    def test_superuser_has_all_permissions(self):
        """Superuser gets all permissions."""
        user = _make_user(role="unknown", is_superuser=True)
        perms = staff_authorization_service._get_permissions(user)
        assert "users:manage" in perms
        assert "export:data" in perms
        assert "security:dashboard" in perms

    def test_unknown_role_has_no_permissions(self):
        """Unknown role has no permissions (fail closed)."""
        user = _make_user(role="unknown_role")
        perms = staff_authorization_service._get_permissions(user)
        assert len(perms) == 0


class TestHasPermission:
    """Tests for has_permission()."""

    def test_admin_has_permission(self):
        user = _make_user(role="Admin")
        assert staff_authorization_service.has_permission(user, "users:manage")

    def test_doctor_lacks_users_manage(self):
        user = _make_user(role="Doctor")
        assert not staff_authorization_service.has_permission(user, "users:manage")

    def test_require_permission_raises_on_denied(self):
        user = _make_user(role="Doctor")
        with pytest.raises(StaffAuthorizationError) as exc_info:
            staff_authorization_service.require_permission(user, "users:manage")
        assert exc_info.value.reason == "access_denied"
        assert exc_info.value.permission == "users:manage"

    def test_require_permission_passes_when_allowed(self):
        user = _make_user(role="Admin")
        # Should not raise
        staff_authorization_service.require_permission(user, "users:manage")


class TestAppointmentAccess:
    """Tests for appointment access checks."""

    def test_admin_can_read_all_appointments(self):
        user = _make_user(role="Admin")
        assert staff_authorization_service.can_read_appointment(user)

    def test_registrar_can_read_all_appointments(self):
        user = _make_user(role="Registrar")
        assert staff_authorization_service.can_read_appointment(user)

    def test_cashier_can_read_all_appointments(self):
        user = _make_user(role="Cashier")
        assert staff_authorization_service.can_read_appointment(user)

    def test_doctor_can_read_own_appointment(self):
        user = _make_user(role="Doctor", user_id=5)
        apt = _make_appointment(doctor_id=5)
        assert staff_authorization_service.can_read_appointment(user, apt)

    def test_doctor_cannot_read_other_doctor_appointment(self):
        user = _make_user(role="Doctor", user_id=5)
        apt = _make_appointment(doctor_id=99)
        assert not staff_authorization_service.can_read_appointment(user, apt)

    def test_patient_can_read_own_appointment(self):
        user = _make_user(role="Patient", user_id=10)
        user.patient = MagicMock()
        user.patient.id = 42
        apt = _make_appointment(patient_id=42)
        assert staff_authorization_service.can_read_appointment(user, apt)

    def test_patient_cannot_read_other_appointment(self):
        user = _make_user(role="Patient", user_id=10)
        user.patient = MagicMock()
        user.patient.id = 42
        apt = _make_appointment(patient_id=99)
        assert not staff_authorization_service.can_read_appointment(user, apt)

    def test_doctor_can_write_appointments(self):
        user = _make_user(role="Doctor")
        assert staff_authorization_service.can_write_appointment(user)

    def test_cashier_cannot_write_appointments(self):
        user = _make_user(role="Cashier")
        assert not staff_authorization_service.can_write_appointment(user)


class TestPatientAccess:
    """Tests for patient data access checks."""

    def test_admin_can_read_all_patients(self):
        user = _make_user(role="Admin")
        assert staff_authorization_service.can_read_patient(user)

    def test_doctor_can_read_patients(self):
        user = _make_user(role="Doctor")
        assert staff_authorization_service.can_read_patient(user)

    def test_lab_can_read_patients(self):
        user = _make_user(role="Lab")
        assert staff_authorization_service.can_read_patient(user)

    def test_patient_can_read_self(self):
        user = _make_user(role="Patient", user_id=10)
        user.patient = MagicMock()
        user.patient.id = 42
        assert staff_authorization_service.can_read_patient(user, patient_id=42)

    def test_patient_cannot_read_other_patient(self):
        user = _make_user(role="Patient", user_id=10)
        user.patient = MagicMock()
        user.patient.id = 42
        assert not staff_authorization_service.can_read_patient(user, patient_id=99)

    def test_registrar_can_write_patients(self):
        user = _make_user(role="Registrar")
        assert staff_authorization_service.can_write_patient(user)

    def test_doctor_cannot_write_patients(self):
        """Doctor can read patients but cannot create/edit patient records."""
        user = _make_user(role="Doctor")
        assert not staff_authorization_service.can_write_patient(user)


class TestEMRAccess:
    """Tests for EMR access checks."""

    def test_admin_can_read_emr(self):
        user = _make_user(role="Admin")
        assert staff_authorization_service.can_read_emr(user)

    def test_doctor_can_read_emr(self):
        user = _make_user(role="Doctor")
        assert staff_authorization_service.can_read_emr(user)

    def test_registrar_cannot_read_emr(self):
        user = _make_user(role="Registrar")
        assert not staff_authorization_service.can_read_emr(user)

    def test_cashier_cannot_read_emr(self):
        user = _make_user(role="Cashier")
        assert not staff_authorization_service.can_read_emr(user)

    def test_doctor_can_write_emr(self):
        user = _make_user(role="Doctor")
        assert staff_authorization_service.can_write_emr(user)

    def test_admin_can_delete_emr(self):
        user = _make_user(role="Admin")
        assert staff_authorization_service.can_delete_emr(user)

    def test_doctor_cannot_delete_emr(self):
        user = _make_user(role="Doctor")
        assert not staff_authorization_service.can_delete_emr(user)


class TestQueueManagement:
    """Tests for queue management checks."""

    def test_admin_can_manage_queue(self):
        user = _make_user(role="Admin")
        assert staff_authorization_service.can_manage_queue(user)

    def test_registrar_can_manage_queue(self):
        user = _make_user(role="Registrar")
        assert staff_authorization_service.can_manage_queue(user)

    def test_doctor_cannot_manage_queue(self):
        """Doctor can read queue but cannot manage (add/remove/call)."""
        user = _make_user(role="Doctor")
        assert not staff_authorization_service.can_manage_queue(user)
        assert staff_authorization_service.can_read_queue(user)

    def test_cashier_cannot_manage_queue(self):
        user = _make_user(role="Cashier")
        assert not staff_authorization_service.can_manage_queue(user)


class TestUserManagement:
    """Tests for user management checks."""

    def test_admin_can_manage_all_users(self):
        user = _make_user(role="Admin", user_id=1)
        assert staff_authorization_service.can_manage_users(user, target_user_id=99)

    def test_user_can_manage_self(self):
        user = _make_user(role="Doctor", user_id=5)
        assert staff_authorization_service.can_manage_users(user, target_user_id=5)

    def test_doctor_cannot_manage_other_users(self):
        user = _make_user(role="Doctor", user_id=5)
        assert not staff_authorization_service.can_manage_users(user, target_user_id=99)


class TestPaymentsAccess:
    """Tests for payment management checks."""

    def test_cashier_can_manage_payments(self):
        user = _make_user(role="Cashier")
        assert staff_authorization_service.can_manage_payments(user)

    def test_admin_can_manage_payments(self):
        user = _make_user(role="Admin")
        assert staff_authorization_service.can_manage_payments(user)

    def test_doctor_cannot_manage_payments(self):
        user = _make_user(role="Doctor")
        assert not staff_authorization_service.can_manage_payments(user)


class TestOtherPermissions:
    """Tests for other permission checks."""

    def test_doctor_can_access_ai(self):
        user = _make_user(role="Doctor")
        assert staff_authorization_service.can_access_ai(user)

    def test_cashier_cannot_access_ai(self):
        user = _make_user(role="Cashier")
        assert not staff_authorization_service.can_access_ai(user)

    def test_admin_can_export_data(self):
        user = _make_user(role="Admin")
        assert staff_authorization_service.can_export_data(user)

    def test_doctor_cannot_export_data(self):
        user = _make_user(role="Doctor")
        assert not staff_authorization_service.can_export_data(user)

    def test_admin_can_view_security_dashboard(self):
        user = _make_user(role="Admin")
        assert staff_authorization_service.can_view_security_dashboard(user)

    def test_doctor_cannot_view_security_dashboard(self):
        user = _make_user(role="Doctor")
        assert not staff_authorization_service.can_view_security_dashboard(user)

    def test_lab_can_read_lab_results(self):
        user = _make_user(role="Lab")
        assert staff_authorization_service.can_read_lab(user)

    def test_doctor_can_read_lab_results(self):
        user = _make_user(role="Doctor")
        assert staff_authorization_service.can_read_lab(user)

    def test_cashier_cannot_read_lab_results(self):
        user = _make_user(role="Cashier")
        assert not staff_authorization_service.can_read_lab(user)
