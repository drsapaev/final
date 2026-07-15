"""
Patient Access Audit Service — M4-P0-1 (Epic M4 — Backend Security & Compliance).

Wrapper function `log_patient_access()` for logging PHI access from
patient-facing endpoints. Called from every telegram mini-app endpoint
that accesses patient PHI.

Design decisions:
- Non-blocking: audit-log failure must NOT break the request.
  If db.add/commit fails, log warning but don't raise.
- Context-rich: captures subject_patient_id, actor info, resource details,
  request metadata (IP, user-agent), and optional correlation_id.
- Future-proofing: actor_type supports 'self' (current) and 'guardian'/'heir'
  (future M4-P1-3 context roles).
- Immutable: append-only. No UPDATE/DELETE methods exposed.

Usage:
    from app.services.patient_access_audit import log_patient_access

    log_patient_access(
        db=db,
        scope=scope,  # TelegramMiniAppSessionScope
        resource_type="lab_report",
        resource_id=str(report_id),
        action="download",
        outcome="success",
        request=request,  # FastAPI Request (for IP + user-agent)
    )
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.models.patient_access_audit import PatientAccessAuditLog

if TYPE_CHECKING:
    from fastapi import Request
    from sqlalchemy.orm import Session
    from app.services.telegram_mini_app_init_data import TelegramMiniAppSessionScope

logger = logging.getLogger(__name__)


def _get_client_ip(request: "Request | None") -> str | None:
    """Extract client IP from FastAPI Request, respecting X-Forwarded-For."""
    if request is None:
        return None
    try:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # X-Forwarded-For: client, proxy1, proxy2
            return forwarded.split(",")[0].strip()
        if request.client:
            return request.client.host
    except Exception:
        pass
    return None


def _get_user_agent(request: "Request | None") -> str | None:
    """Extract User-Agent from FastAPI Request."""
    if request is None:
        return None
    try:
        return request.headers.get("user-agent")
    except Exception:
        return None


def log_patient_access(
    db: "Session",
    *,
    scope: "TelegramMiniAppSessionScope | None" = None,
    subject_patient_id: int | None = None,
    resource_type: str,
    resource_id: str | None = None,
    action: str,
    outcome: str = "success",
    request: "Request | None" = None,
    extra_data: dict[str, Any] | None = None,
    correlation_id: str | None = None,
    session_id: str | None = None,
) -> None:
    """
    Log a PHI access event to patient_access_audit_logs.

    M4-P0-1: Every patient-facing endpoint that accesses PHI must call this.

    Args:
        db: SQLAlchemy session
        scope: TelegramMiniAppSessionScope (if access via Mini App)
        subject_patient_id: Patient whose PHI is being accessed.
            If None, derived from scope.patient_id.
        resource_type: lab_report | cabinet_summary | form_submission |
            appointment | manifest | forms_preview
        resource_id: Optional ID of specific resource
        action: view | download | submit | create | preview
        outcome: success | denied | error
        request: FastAPI Request (for IP + user-agent extraction)
        extra_data: Optional additional context (JSON)
        correlation_id: Optional request tracing ID
        session_id: Optional UserSession ID (future M4-P0-2 JWT jti)

    Note:
        Audit-log failure is non-blocking — logs warning but doesn't raise.
        The request must complete even if audit-logging fails.
    """
    try:
        # Derive subject_patient_id from scope if not explicitly provided
        if subject_patient_id is None and scope is not None:
            subject_patient_id = scope.patient_id

        if subject_patient_id is None:
            logger.warning(
                "log_patient_access called without subject_patient_id "
                "(resource_type=%s, action=%s) — skipping audit log",
                resource_type,
                action,
            )
            return

        # Determine actor fields from scope
        actor_patient_id: int | None = None
        actor_staff_user_id: int | None = None
        actor_telegram_user_id: int | None = None
        actor_type = "self"  # default for patient self-access

        if scope is not None:
            if scope.scope_type == "patient":
                actor_patient_id = scope.patient_id
                actor_telegram_user_id = scope.telegram_user_id
                actor_type = "self"  # M4-P1-3 will add guardian/heir
            elif scope.scope_type == "staff":
                actor_staff_user_id = scope.staff_user_id
                actor_telegram_user_id = scope.telegram_user_id
                actor_type = "staff"

        audit_entry = PatientAccessAuditLog(
            subject_patient_id=subject_patient_id,
            actor_patient_id=actor_patient_id,
            actor_staff_user_id=actor_staff_user_id,
            actor_type=actor_type,
            actor_telegram_user_id=actor_telegram_user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            outcome=outcome,
            ip_address=_get_client_ip(request),
            user_agent=_get_user_agent(request),
            session_id=session_id,
            correlation_id=correlation_id,
            extra_data=extra_data,
        )

        db.add(audit_entry)
        db.commit()

    except Exception as exc:
        # Non-blocking: audit-log failure must NOT break the request.
        # Rollback to avoid polluting the session, then log warning.
        # Note: do NOT log subject_patient_id or other PHI here —
        # CodeQL flags this as clear-text logging of sensitive information.
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning(
            "Failed to write patient access audit log "
            "(resource_type=%s, action=%s): %s",
            resource_type,
            action,
            exc,
        )
