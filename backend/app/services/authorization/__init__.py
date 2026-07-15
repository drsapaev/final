"""
Authorization Service — M4-P1-1 (Epic M4 — Backend Security & Compliance).

Centralized ABAC (Attribute-Based Access Control) policy layer for PHI access.

Replaces scattered authorization checks (require_telegram_mini_app_patient_scope,
inline patient_id == scope.patient_id checks) with a single policy engine.

Policy rules:
- self: patient accesses own PHI → allow
- guardian: patient accesses child/ward PHI → allow (future M4-P1-3)
- heir: patient accesses deceased relative's PHI → allow with restrictions (future)
- staff: doctor/admin/cashier accesses patient PHI → allow if role permitted

Usage:
    from app.services.authorization import AuthorizationService, require_phi_access

    # As FastAPI dependency:
    @router.post("/mini-app/reports/download")
    def download_report(
        scope: TelegramMiniAppSessionScope = Depends(require_phi_access(
            resource_type="lab_report",
            action="download",
        )),
    ):
        ...

    # Direct call:
    authz = AuthorizationService()
    authz.can_access_phi(scope, patient_id=42, resource_type="lab_report", action="download")
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.telegram_mini_app_init_data import TelegramMiniAppSessionScope

logger = logging.getLogger(__name__)


class ResourceType(str, Enum):
    """PHI resource types that can be accessed."""

    LAB_REPORT = "lab_report"
    CABINET_SUMMARY = "cabinet_summary"
    FORM_SUBMISSION = "form_submission"
    APPOINTMENT = "appointment"
    MANIFEST = "manifest"
    FORMS_PREVIEW = "forms_preview"
    SESSION_MANAGEMENT = "session_management"


class Action(str, Enum):
    """Actions that can be performed on PHI resources."""

    VIEW = "view"
    DOWNLOAD = "download"
    SUBMIT = "submit"
    CREATE = "create"
    PREVIEW = "preview"


class ActorType(str, Enum):
    """Who is accessing the PHI."""

    SELF = "self"
    GUARDIAN = "guardian"  # Future: M4-P1-3
    HEIR = "heir"  # Future: M4-P1-3
    STAFF = "staff"


class AuthorizationDecision(str, Enum):
    """Decision returned by policy engine."""

    ALLOW = "allow"
    DENY = "deny"


@dataclass(frozen=True)
class AuthorizationRequest:
    """Input to the authorization policy engine."""

    scope: "TelegramMiniAppSessionScope"
    subject_patient_id: int
    resource_type: str
    action: str
    resource_id: str | None = None


@dataclass(frozen=True)
class AuthorizationResult:
    """Output from the authorization policy engine."""

    decision: AuthorizationDecision
    reason: str
    actor_type: str

    @property
    def allowed(self) -> bool:
        return self.decision == AuthorizationDecision.ALLOW


class AuthorizationError(Exception):
    """Raised when PHI access is denied."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


# ─── Staff role permissions ────────────────────────────────────────────────
#
# Defines which staff roles can perform which actions on which resources.
# Patient self-access is always allowed (no role check needed).

STAFF_PERMISSIONS: dict[str, set[str]] = {
    # Admin: full access to all PHI
    "admin": {
        "lab_report:view", "lab_report:download",
        "cabinet_summary:view",
        "form_submission:view", "form_submission:submit",
        "appointment:view", "appointment:create", "appointment:preview",
        "manifest:view",
        "forms_preview:view",
        "session_management:view", "session_management:revoke_all",
    },
    # Doctor: view/download lab reports, view cabinet, view forms
    "doctor": {
        "lab_report:view", "lab_report:download",
        "cabinet_summary:view",
        "form_submission:view",
        "appointment:view", "appointment:preview",
        "forms_preview:view",
    },
    # Registrar: view cabinet, create appointments
    "registrar": {
        "cabinet_summary:view",
        "appointment:view", "appointment:create", "appointment:preview",
    },
    # Cashier: view cabinet (for payment info)
    "cashier": {
        "cabinet_summary:view",
    },
    # Lab: view/download lab reports
    "lab": {
        "lab_report:view", "lab_report:download",
    },
}

# Actions that only the patient (self) can perform — staff cannot.
PATIENT_ONLY_ACTIONS: set[str] = {
    "form_submission:submit",  # Patient submits their own forms
    "session_management:revoke_all",  # Patient revokes their own sessions
}


class AuthorizationService:
    """Centralized ABAC policy engine for PHI access (M4-P1-1)."""

    def can_access_phi(
        self,
        scope: "TelegramMiniAppSessionScope",
        *,
        subject_patient_id: int,
        resource_type: str,
        action: str,
        resource_id: str | None = None,
    ) -> AuthorizationResult:
        """Check if a scope can access PHI for a given patient.

        Args:
            scope: TelegramMiniAppSessionScope (patient or staff)
            subject_patient_id: Patient whose PHI is being accessed
            resource_type: One of ResourceType values
            action: One of Action values
            resource_id: Optional specific resource ID

        Returns:
            AuthorizationResult with decision + reason + actor_type
        """
        # Determine actor type
        if scope.scope_type == "patient":
            actor_type = ActorType.SELF
        elif scope.scope_type == "staff":
            actor_type = ActorType.STAFF
        else:
            return AuthorizationResult(
                decision=AuthorizationDecision.DENY,
                reason="unknown_scope_type",
                actor_type="unknown",
            )

        # Build permission key
        permission_key = f"{resource_type}:{action}"

        # ─── SELF access (patient accessing own PHI) ──────────────────────
        if actor_type == ActorType.SELF:
            if scope.patient_id is None:
                return AuthorizationResult(
                    decision=AuthorizationDecision.DENY,
                    reason="patient_scope_required",
                    actor_type=actor_type.value,
                )

            if int(scope.patient_id) != int(subject_patient_id):
                # Patient trying to access another patient's PHI
                # Future: check guardian/heir relationships (M4-P1-3)
                return AuthorizationResult(
                    decision=AuthorizationDecision.DENY,
                    reason="patient_scope_mismatch",
                    actor_type=actor_type.value,
                )

            # Self-access is always allowed
            return AuthorizationResult(
                decision=AuthorizationDecision.ALLOW,
                reason="self_access",
                actor_type=actor_type.value,
            )

        # ─── STAFF access (doctor/admin/etc accessing patient PHI) ────────
        if actor_type == ActorType.STAFF:
            if scope.staff_user_id is None:
                return AuthorizationResult(
                    decision=AuthorizationDecision.DENY,
                    reason="staff_scope_required",
                    actor_type=actor_type.value,
                )

            # Check if this is a patient-only action
            if permission_key in PATIENT_ONLY_ACTIONS:
                return AuthorizationResult(
                    decision=AuthorizationDecision.DENY,
                    reason="patient_only_action",
                    actor_type=actor_type.value,
                )

            # Check staff role permissions
            staff_role = scope.staff_role or ""
            allowed_permissions = STAFF_PERMISSIONS.get(staff_role, set())

            if permission_key not in allowed_permissions:
                return AuthorizationResult(
                    decision=AuthorizationDecision.DENY,
                    reason="staff_role_denied",
                    actor_type=actor_type.value,
                )

            return AuthorizationResult(
                decision=AuthorizationDecision.ALLOW,
                reason="staff_authorized",
                actor_type=actor_type.value,
            )

        # Should not reach here
        return AuthorizationResult(
            decision=AuthorizationDecision.DENY,
            reason="unknown_actor_type",
            actor_type="unknown",
        )

    def require_phi_access(
        self,
        scope: "TelegramMiniAppSessionScope",
        *,
        subject_patient_id: int,
        resource_type: str,
        action: str,
        resource_id: str | None = None,
    ) -> "TelegramMiniAppSessionScope":
        """Check authorization and raise if denied.

        Raises AuthorizationError if access is denied.
        Returns scope if allowed.
        """
        result = self.can_access_phi(
            scope,
            subject_patient_id=subject_patient_id,
            resource_type=resource_type,
            action=action,
            resource_id=resource_id,
        )

        if not result.allowed:
            logger.warning(
                "PHI access denied (resource_type=%s, action=%s, reason=%s, actor_type=%s)",
                resource_type,
                action,
                result.reason,
                result.actor_type,
            )
            raise AuthorizationError(result.reason)

        return scope


# Singleton instance
authorization_service = AuthorizationService()
