"""
Sensitive Action Definitions — M5.3 (Epic M5 — Enterprise Security).

Defines which actions are "sensitive" and must be logged to AuditLog.
Each sensitive action has:
- event_type: unique identifier for audit log
- action: verb (view, edit, delete, export, issue, etc.)
- resource_type: what resource is affected
- description: human-readable description

Usage:
    from app.services.sensitive_actions import SENSITIVE_ACTIONS, is_sensitive_action

    if is_sensitive_action("emr", "edit"):
        log_audit_event(db, event_type="DOCTOR_EDIT_EMR", ...)
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SensitiveAction:
    """Definition of a sensitive action that must be audit-logged."""
    event_type: str
    action: str
    resource_type: str
    description: str


# ─── Sensitive actions registry ─────────────────────────────────────────────
# These actions MUST be logged to AuditLog when performed.

SENSITIVE_ACTIONS: list[SensitiveAction] = [
    # ─── EMR / Clinical ────────────────────────────────────────────────────
    SensitiveAction("DOCTOR_OPEN_EMR", "view", "emr", "Doctor opened patient EMR"),
    SensitiveAction("DOCTOR_EDIT_DIAGNOSIS", "edit", "emr", "Doctor changed diagnosis"),
    SensitiveAction("DOCTOR_EDIT_PRESCRIPTION", "edit", "prescription", "Doctor edited prescription"),
    SensitiveAction("DOCTOR_ISSUE_PRESCRIPTION", "issue", "prescription", "Doctor issued new prescription"),
    SensitiveAction("DOCTOR_CANCEL_PRESCRIPTION", "delete", "prescription", "Doctor cancelled prescription"),
    SensitiveAction("DOCTOR_DELETE_EMR", "delete", "emr", "Doctor deleted EMR record"),

    # ─── Lab ────────────────────────────────────────────────────────────────
    SensitiveAction("LAB_RESULT_VIEW", "view", "lab_report", "Lab result viewed"),
    SensitiveAction("LAB_RESULT_DELETE", "delete", "lab_report", "Lab result deleted"),
    SensitiveAction("LAB_REPORT_FINALIZE", "finalize", "lab_report", "Lab report finalized (immutable)"),

    # ─── Patient data ───────────────────────────────────────────────────────
    SensitiveAction("REGISTRAR_EDIT_PATIENT", "edit", "patient", "Registrar edited patient record"),
    SensitiveAction("REGISTRAR_CREATE_APPOINTMENT", "create", "appointment", "Registrar created appointment"),
    SensitiveAction("PATIENT_REPORT_DOWNLOAD", "download", "lab_report", "Patient downloaded report PDF"),

    # ─── Admin operations ───────────────────────────────────────────────────
    SensitiveAction("ADMIN_CREATE_USER", "create", "user", "Admin created new user"),
    SensitiveAction("ADMIN_DELETE_USER", "delete", "user", "Admin deleted user"),
    SensitiveAction("ADMIN_CHANGE_ROLE", "edit", "user", "Admin changed user role"),
    SensitiveAction("ADMIN_EXPORT_DATA", "export", "data", "Admin exported data"),
    SensitiveAction("ADMIN_BULK_OPERATION", "bulk", "data", "Admin performed bulk operation"),

    # ─── Payments ───────────────────────────────────────────────────────────
    SensitiveAction("PAYMENT_EDIT", "edit", "payment", "Payment amount/details edited"),
    SensitiveAction("REFUND_ISSUE", "issue", "refund", "Refund issued"),

    # ─── Session / Auth ────────────────────────────────────────────────────
    SensitiveAction("STAFF_LOGIN", "login", "session", "Staff user logged in"),
    SensitiveAction("STAFF_LOGOUT", "logout", "session", "Staff user logged out"),
    SensitiveAction("SESSION_REVOKE", "delete", "session", "Session revoked"),
    SensitiveAction("EMERGENCY_TOKEN_ISSUED", "issue", "emergency_token", "Emergency access token issued"),

    # ─── Security ───────────────────────────────────────────────────────────
    SensitiveAction("RATE_LIMITED", "rate_limit", "endpoint", "Request rate-limited"),
    SensitiveAction("SECRET_ROTATED", "rotate", "secret", "Secret key rotated"),
]


# Build lookup index for fast checking
_SENSITIVE_LOOKUP: dict[tuple[str, str], SensitiveAction] = {
    (a.resource_type, a.action): a for a in SENSITIVE_ACTIONS
}


def is_sensitive_action(resource_type: str, action: str) -> bool:
    """Check if a resource:action combination is sensitive (must be logged)."""
    return (resource_type, action) in _SENSITIVE_LOOKUP


def get_sensitive_action(resource_type: str, action: str) -> SensitiveAction | None:
    """Get the SensitiveAction definition for a resource:action, or None."""
    return _SENSITIVE_LOOKUP.get((resource_type, action))


def get_event_type(resource_type: str, action: str) -> str | None:
    """Get the event_type for a resource:action, or None if not sensitive."""
    sa = _SENSITIVE_LOOKUP.get((resource_type, action))
    return sa.event_type if sa else None
