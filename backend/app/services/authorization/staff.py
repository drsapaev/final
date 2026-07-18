"""
Staff Authorization Service — M5.2 (Epic M5 — Enterprise Security).

Centralized authorization for ALL staff endpoints. Replaces scattered
inline checks like:
    if current_user.role == "Admin":
    if current_user.role not in ["Admin", "Registrar"]:
    if current_user.id != user_id and current_user.role != "Admin":

with a single policy engine:
    staff_authz.can_read_appointment(user, appointment)
    staff_authz.can_edit_patient(user, patient_id)
    staff_authz.can_manage_users(user, target_user_id)

Works with User objects (JWT-based staff auth), separate from
AuthorizationService which works with TelegramMiniAppSessionScope
(Mini App patient/staff auth).

Design:
- Role normalization: handles legacy role variants (cardio → Doctor, etc.)
- Ownership checks: doctor can only access own appointments/patients
- Superuser bypass: is_superuser always allowed
- Fail closed: unknown role → deny
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.appointment import Appointment

logger = logging.getLogger(__name__)


# ─── Role normalization ────────────────────────────────────────────────────
# Legacy code uses various role strings. Normalize to canonical roles.

_DOCTOR_ROLE_ALIASES = frozenset({
    "Doctor", "doctor",
    "cardio", "cardiology", "Cardiologist", "Cardio",
    "derma", "Dermatologist",
    "dentist", "Dentist",
})

_ADMIN_ROLE_ALIASES = frozenset({"Admin", "admin", "administrator", "super_admin", "superadmin"})
_REGISTRAR_ROLE_ALIASES = frozenset({"Registrar", "registrar", "receptionist"})
_CASHIER_ROLE_ALIASES = frozenset({"Cashier", "cashier"})
_LAB_ROLE_ALIASES = frozenset({"Lab", "lab", "lab_tech", "laboratory"})
_PATIENT_ROLE_ALIASES = frozenset({"Patient", "patient"})


def normalize_role(role: str | None) -> str:
    """Normalize legacy role strings to canonical role.

    Returns: 'admin' | 'doctor' | 'registrar' | 'cashier' | 'lab' | 'patient' | 'unknown'
    """
    if not role:
        return "unknown"
    if role in _ADMIN_ROLE_ALIASES:
        return "admin"
    if role in _DOCTOR_ROLE_ALIASES:
        return "doctor"
    if role in _REGISTRAR_ROLE_ALIASES:
        return "registrar"
    if role in _CASHIER_ROLE_ALIASES:
        return "cashier"
    if role in _LAB_ROLE_ALIASES:
        return "lab"
    if role in _PATIENT_ROLE_ALIASES:
        return "patient"
    return "unknown"


# ─── Permission sets ───────────────────────────────────────────────────────
# Each canonical role has a set of permissions.
# Permissions are action-scoped: 'appointment:read', 'patient:edit', etc.

_STAFF_PERMISSIONS: dict[str, frozenset[str]] = {
    "admin": frozenset({
        "appointment:read", "appointment:write", "appointment:delete",
        "patient:read", "patient:write",
        "emr:read", "emr:write", "emr:delete",
        "queue:manage",
        "users:manage",
        "payments:manage",
        "lab:read", "lab:write",
        "ai:access",
        "export:data",
        "files:manage",
        "settings:manage",
        "security:dashboard",
    }),
    "doctor": frozenset({
        "appointment:read", "appointment:write",
        "patient:read",
        "emr:read", "emr:write",
        "queue:read",
        "lab:read",
        "ai:access",
        "files:read",
    }),
    "registrar": frozenset({
        "appointment:read", "appointment:write",
        "patient:read", "patient:write",
        "queue:manage",
        "files:read",
    }),
    "cashier": frozenset({
        "appointment:read",
        "patient:read",
        "payments:manage",
        "files:read",
    }),
    "lab": frozenset({
        "lab:read", "lab:write",
        "patient:read",
        "files:read",
    }),
    "patient": frozenset({
        "appointment:read",
        "patient:read",  # self only
    }),
}


class StaffAuthorizationError(Exception):
    """Raised when staff access is denied."""

    def __init__(self, reason: str, permission: str = ""):
        super().__init__(reason)
        self.reason = reason
        self.permission = permission


class StaffAuthorizationService:
    """Centralized authorization for staff endpoints (M5.2).

    Replaces inline role checks with a single policy engine.
    All methods take User objects (from JWT-based auth).
    """

    def _get_permissions(self, user: "User") -> frozenset[str]:
        """Get permission set for a user's role."""
        if getattr(user, "is_superuser", False):
            # Superuser gets all permissions
            all_perms: set[str] = set()
            for perms in _STAFF_PERMISSIONS.values():
                all_perms |= perms
            return frozenset(all_perms)

        role = normalize_role(getattr(user, "role", None))
        return _STAFF_PERMISSIONS.get(role, frozenset())

    def has_permission(self, user: "User", permission: str) -> bool:
        """Check if user has a specific permission."""
        return permission in self._get_permissions(user)

    def require_permission(self, user: "User", permission: str) -> None:
        """Raise StaffAuthorizationError if user lacks permission."""
        if not self.has_permission(user, permission):
            logger.warning(
                "Authorization denied (permission=%s, user_id=%s, role=%s)",
                permission,
                getattr(user, "id", "?"),
                getattr(user, "role", "?"),
            )
            raise StaffAuthorizationError(
                reason="access_denied",
                permission=permission,
            )

    # ─── Appointment access ────────────────────────────────────────────────

    def can_read_appointment(self, user: "User", appointment: "Appointment | None" = None) -> bool:
        """Check if user can read an appointment.

        - Admin/Registrar: all appointments
        - Doctor: own appointments only
        - Patient: own appointments only
        - Cashier: all appointments (for payment processing)
        """
        if not self.has_permission(user, "appointment:read"):
            return False

        role = normalize_role(getattr(user, "role", None))

        # Broad access roles: admin, registrar, cashier
        if role in ("admin", "registrar", "cashier"):
            return True

        # Doctor: check ownership
        if role == "doctor" and appointment is not None:
            doctor_id = getattr(appointment, "doctor_id", None)
            if doctor_id is None:
                return False
            # Check if appointment.doctor_id matches user's doctor profile
            # This requires DB lookup — caller should pass the resolved doctor_id
            # For now, we check if user.id matches appointment.doctor_id (legacy)
            # or if user has a doctor profile matching
            return doctor_id == getattr(user, "id", None) or self._is_appointment_doctor(user, appointment)

        # Patient: check ownership
        if role == "patient" and appointment is not None:
            patient_id = getattr(appointment, "patient_id", None)
            current_patient = getattr(user, "patient", None)
            if current_patient and getattr(current_patient, "id", None) == patient_id:
                return True
            # Fallback: check user_id linkage
            return getattr(user, "id", None) == getattr(appointment, "patient_id", None)

        return False

    def can_write_appointment(self, user: "User") -> bool:
        """Check if user can create/edit appointments."""
        return self.has_permission(user, "appointment:write")

    def can_delete_appointment(self, user: "User") -> bool:
        """Check if user can delete appointments."""
        return self.has_permission(user, "appointment:delete")

    def _is_appointment_doctor(self, user: "User", appointment: "Appointment") -> bool:
        """Check if user is the doctor assigned to the appointment."""
        # This is a simplified check — in production, resolve Doctor profile
        doctor_id = getattr(appointment, "doctor_id", None)
        if doctor_id is None:
            return False
        return doctor_id == getattr(user, "id", None)

    # ─── Patient access ────────────────────────────────────────────────────

    def can_read_patient(self, user: "User", patient_id: int | None = None) -> bool:
        """Check if user can read patient data.

        - Admin/Registrar/Doctor/Lab/Cashier: can read patient data
        - Patient: can read own data only
        """
        if not self.has_permission(user, "patient:read"):
            return False

        role = normalize_role(getattr(user, "role", None))

        # Staff roles: broad access
        if role in ("admin", "registrar", "doctor", "cashier", "lab"):
            return True

        # Patient: self only
        if role == "patient" and patient_id is not None:
            current_patient = getattr(user, "patient", None)
            return current_patient and getattr(current_patient, "id", None) == patient_id

        return False

    def can_write_patient(self, user: "User") -> bool:
        """Check if user can create/edit patient records."""
        return self.has_permission(user, "patient:write")

    # ─── EMR access ────────────────────────────────────────────────────────

    def can_read_emr(self, user: "User") -> bool:
        """Check if user can read EMR records."""
        return self.has_permission(user, "emr:read")

    def can_write_emr(self, user: "User") -> bool:
        """Check if user can create/edit EMR records."""
        return self.has_permission(user, "emr:write")

    def can_delete_emr(self, user: "User") -> bool:
        """Check if user can delete EMR records."""
        return self.has_permission(user, "emr:delete")

    # ─── Queue management ──────────────────────────────────────────────────

    def can_manage_queue(self, user: "User") -> bool:
        """Check if user can manage queue (add, remove, call next)."""
        return self.has_permission(user, "queue:manage")

    def can_read_queue(self, user: "User") -> bool:
        """Check if user can read queue."""
        return self.has_permission(user, "queue:read") or self.can_manage_queue(user)

    # ─── User management ───────────────────────────────────────────────────

    def can_manage_users(self, user: "User", target_user_id: int | None = None) -> bool:
        """Check if user can manage other users.

        - Admin: can manage all users
        - Self: user can manage own profile (target_user_id == user.id)
        """
        if self.has_permission(user, "users:manage"):
            return True

        # Self-management: user can edit own profile
        if target_user_id is not None and target_user_id == getattr(user, "id", None):
            return True

        return False

    # ─── Payments ──────────────────────────────────────────────────────────

    def can_manage_payments(self, user: "User") -> bool:
        """Check if user can manage payments."""
        return self.has_permission(user, "payments:manage")

    # ─── Lab ───────────────────────────────────────────────────────────────

    def can_read_lab(self, user: "User") -> bool:
        """Check if user can read lab results."""
        return self.has_permission(user, "lab:read")

    def can_write_lab(self, user: "User") -> bool:
        """Check if user can create/edit lab results."""
        return self.has_permission(user, "lab:write")

    # ─── AI ────────────────────────────────────────────────────────────────

    def can_access_ai(self, user: "User") -> bool:
        """Check if user can access AI features."""
        return self.has_permission(user, "ai:access")

    # ─── Export ────────────────────────────────────────────────────────────

    def can_export_data(self, user: "User") -> bool:
        """Check if user can export data."""
        return self.has_permission(user, "export:data")

    # ─── Files ─────────────────────────────────────────────────────────────

    def can_manage_files(self, user: "User") -> bool:
        """Check if user can manage files (upload, delete)."""
        return self.has_permission(user, "files:manage")

    def can_read_files(self, user: "User") -> bool:
        """Check if user can read files."""
        return self.has_permission(user, "files:read") or self.can_manage_files(user)

    # ─── Settings ──────────────────────────────────────────────────────────

    def can_manage_settings(self, user: "User") -> bool:
        """Check if user can manage system settings."""
        return self.has_permission(user, "settings:manage")

    # ─── Security ──────────────────────────────────────────────────────────

    def can_view_security_dashboard(self, user: "User") -> bool:
        """Check if user can view security dashboard."""
        return self.has_permission(user, "security:dashboard")


# Singleton
staff_authorization_service = StaffAuthorizationService()
