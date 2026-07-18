"""
Audit logging helper for HIPAA §164.312(b) Audit Controls compliance.

Provides a utility function to log admin/staff actions to the AuditLog table.
Captures: who (actor_user_id), what (action, entity_type, entity_id),
when (created_at), where (ip, user_agent), details (payload).

Usage in endpoints:
    from app.core.audit_helper import log_action
    log_action(db, user=current_user, action="DEPARTMENT_CREATE",
               entity_type="department", entity_id=dept.id,
               payload={"name": dept.name})
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit import AuditLog

logger = logging.getLogger(__name__)


def log_action(
    db: Session,
    *,
    user,
    action: str,
    entity_type: str | None = None,
    entity_id: int | None = None,
    payload: dict[str, Any] | None = None,
    request=None,
) -> None:
    """Log an admin/staff action to the AuditLog table.

    Args:
        db: Database session.
        user: The User object performing the action.
        action: Short action code (e.g. "DEPARTMENT_CREATE", "USER_DELETE").
        entity_type: Type of entity affected (e.g. "department", "user").
        entity_id: ID of the entity affected.
        payload: Additional details (old/new values, reason, etc.).
        request: FastAPI Request object (for IP + User-Agent).

    Returns:
        None. On failure, logs a warning but does not raise.
    """
    try:
        ip_address = None
        user_agent = None
        if request:
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                ip_address = forwarded.split(",")[0].strip()
            elif request.client:
                ip_address = request.client.host
            user_agent = request.headers.get("user-agent", "")

        entry = AuditLog(
            action=action[:64],
            entity_type=entity_type,
            entity_id=entity_id,
            actor_user_id=getattr(user, "id", None),
            payload={
                **(payload or {}),
                "ip": ip_address,
                "user_agent": user_agent[:500] if user_agent else None,
                "role": getattr(user, "role", None),
            },
        )
        db.add(entry)
        db.flush()  # Don't commit — caller controls transaction
    except Exception as e:
        logger.warning("Failed to log audit action %s: %s", action, type(e).__name__)
