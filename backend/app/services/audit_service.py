"""
Unified Audit Service — M5.1 (Epic M5 — Enterprise Security).

Single wrapper for logging ALL audit events to the unified audit_logs table.

Replaces:
- PatientAccessAuditLog (M4-P0-1) — patient PHI access
- EMRAuditLog — doctor/staff EMR access

Usage:
    from app.services.audit_service import log_audit_event

    log_audit_event(
        db=db,
        event_type="DOCTOR_OPEN_EMR",
        actor_user_id=current_user.id,
        actor_role="doctor",
        subject_patient_id=patient_id,
        resource_type="emr",
        resource_id=str(emr_id),
        action="view",
        outcome="success",
        reason_code={"context": "consultation", "id": consultation_id},
        request=request,
    )
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.models.audit import AuditLog

if TYPE_CHECKING:
    from fastapi import Request
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _get_client_ip(request: "Request | None") -> str | None:
    if request is None:
        return None
    try:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client:
            return request.client.host
    except Exception:
        pass
    return None


def _get_user_agent(request: "Request | None") -> str | None:
    if request is None:
        return None
    try:
        return request.headers.get("user-agent")
    except Exception:
        return None


def log_audit_event(
    db: "Session",
    *,
    event_type: str,
    actor_user_id: int | None = None,
    actor_patient_id: int | None = None,
    actor_role: str | None = None,
    actor_type: str = "staff",
    subject_patient_id: int | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    action: str,
    outcome: str = "success",
    reason_code: dict[str, Any] | None = None,
    request: "Request | None" = None,
    extra_data: dict[str, Any] | None = None,
    session_id: str | None = None,
) -> None:
    """Log an audit event to the unified audit_logs table (M5.1).

    Non-blocking: audit-log failure does NOT break the request.
    Immutable: DB trigger prevents UPDATE/DELETE (M5.5).

    Args:
        event_type: Event type (PATIENT_LOGIN, DOCTOR_OPEN_EMR, ADMIN_EXPORT, etc.)
        actor_user_id: Staff user who performed the action (null for patient)
        actor_patient_id: Patient who performed the action (null for staff)
        actor_role: Role at time of action
        actor_type: staff | patient | system
        subject_patient_id: Patient whose data was accessed (null for non-PHI)
        resource_type: lab_report | emr | appointment | user | payment | etc.
        resource_id: ID of specific resource
        action: view | download | create | edit | delete | export | login | logout
        outcome: success | denied | error
        reason_code: Why the action was performed (M5.4)
        request: FastAPI Request (for IP + user-agent)
        extra_data: Additional context (JSON)
        session_id: Session ID for correlation
    """
    try:
        entry = AuditLog(
            event_type=event_type,
            actor_user_id=actor_user_id,
            actor_patient_id=actor_patient_id,
            actor_role=actor_role,
            actor_type=actor_type,
            subject_patient_id=subject_patient_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            outcome=outcome,
            reason_code=reason_code,
            ip_address=_get_client_ip(request),
            user_agent=_get_user_agent(request),
            session_id=session_id,
            extra_data=extra_data,
        )
        db.add(entry)
        db.commit()
    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning(
            "Failed to write audit log (event_type=%s, action=%s): %s",
            event_type, action, exc,
        )
