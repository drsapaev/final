"""
Backup Audit Service — M5.9 (Epic M5 — Enterprise Security).

Checks backup status and provides verification endpoints.
Does NOT perform actual backups (that requires infrastructure),
but checks when the last backup was performed and alerts if overdue.

Tracks backup events via AuditLog (event_type=BACKUP_VERIFIED/BACKUP_FAILED).
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit import AuditLog

BACKUP_INTERVAL_HOURS = 24  # Daily backup expected


def get_backup_status(db: Session) -> dict[str, Any]:
    """Check backup status (M5.9).

    Returns: last_backup_at, hours_since, overdue, last_status.
    """
    now = datetime.now(UTC)

    last_backup = (
        db.query(AuditLog)
        .filter(
            AuditLog.event_type.in_(["BACKUP_VERIFIED", "BACKUP_FAILED"]),
        )
        .order_by(AuditLog.timestamp.desc())
        .first()
    )

    if last_backup and last_backup.timestamp:
        last_at = last_backup.timestamp
        hours_since = int((now - last_at).total_seconds() / 3600)
        overdue = hours_since > BACKUP_INTERVAL_HOURS
        last_status = "verified" if last_backup.event_type == "BACKUP_VERIFIED" else "failed"
    else:
        last_at = None
        hours_since = None
        overdue = True
        last_status = "never"

    return {
        "last_backup_at": last_at.isoformat() if last_at else None,
        "hours_since_last_backup": hours_since,
        "overdue": overdue,
        "last_status": last_status,
        "expected_interval_hours": BACKUP_INTERVAL_HOURS,
    }


def record_backup_event(
    db: Session,
    *,
    status: str,  # "verified" or "failed"
    performed_by: int | None = None,
    notes: str | None = None,
) -> None:
    """Record a backup verification event (M5.9)."""
    from app.services.audit_service import log_audit_event

    event_type = "BACKUP_VERIFIED" if status == "verified" else "BACKUP_FAILED"
    log_audit_event(
        db=db,
        event_type=event_type,
        actor_user_id=performed_by,
        actor_type="system" if performed_by is None else "staff",
        action="verify" if status == "verified" else "error",
        resource_type="backup",
        outcome="success" if status == "verified" else "error",
        extra_data={"notes": notes},
    )
