"""
Security Dashboard Service — M5.6 (Epic M5 — Enterprise Security).

Aggregates audit log data for admin security dashboard.
Returns recent events, failed logins, suspicious IPs, bulk operations.

Usage:
    from app.services.security_dashboard import get_security_dashboard

    data = get_security_dashboard(db)
    # data = { recent_logins, recent_downloads, failed_logins, suspicious_ips, ... }
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.audit import AuditLog


def get_security_dashboard(db: Session, *, hours: int = 24) -> dict[str, Any]:
    """Get aggregated security dashboard data (M5.6).

    Args:
        db: SQLAlchemy session
        hours: Time window in hours (default 24h)

    Returns:
        Dict with: recent_logins, recent_downloads, recent_exports,
        failed_logins, suspicious_ips, bulk_operations, summary
    """
    since = datetime.now(UTC) - timedelta(hours=hours)

    # Recent logins (staff + patient)
    recent_logins = (
        db.query(AuditLog)
        .filter(
            AuditLog.event_type.in_(["STAFF_LOGIN", "PATIENT_LOGIN"]),
            AuditLog.created_at >= since,
        )
        .order_by(AuditLog.created_at.desc())
        .limit(20)
        .all()
    )

    # Recent downloads
    recent_downloads = (
        db.query(AuditLog)
        .filter(
            AuditLog.action == "download",
            AuditLog.created_at >= since,
        )
        .order_by(AuditLog.created_at.desc())
        .limit(20)
        .all()
    )

    # Recent exports
    recent_exports = (
        db.query(AuditLog)
        .filter(
            AuditLog.action == "export",
            AuditLog.created_at >= since,
        )
        .order_by(AuditLog.created_at.desc())
        .limit(20)
        .all()
    )

    # Failed logins
    failed_logins = (
        db.query(AuditLog)
        .filter(
            AuditLog.event_type.in_(["STAFF_LOGIN", "PATIENT_LOGIN"]),
            AuditLog.outcome == "denied",
            AuditLog.created_at >= since,
        )
        .order_by(AuditLog.created_at.desc())
        .limit(20)
        .all()
    )

    # Suspicious IPs: IPs with 5+ failed logins
    suspicious_ips = (
        db.query(
            AuditLog.ip_address,
            func.count(AuditLog.id).label("fail_count"),
        )
        .filter(
            AuditLog.outcome == "denied",
            AuditLog.created_at >= since,
            AuditLog.ip_address.isnot(None),
        )
        .group_by(AuditLog.ip_address)
        .having(func.count(AuditLog.id) >= 5)
        .order_by(func.count(AuditLog.id).desc())
        .limit(10)
        .all()
    )

    # Bulk operations
    bulk_operations = (
        db.query(AuditLog)
        .filter(
            AuditLog.action == "bulk",
            AuditLog.created_at >= since,
        )
        .order_by(AuditLog.created_at.desc())
        .limit(10)
        .all()
    )

    # Summary counts
    total_events = (
        db.query(func.count(AuditLog.id))
        .filter(AuditLog.created_at >= since)
        .scalar() or 0
    )
    total_denied = (
        db.query(func.count(AuditLog.id))
        .filter(
            AuditLog.created_at >= since,
            AuditLog.outcome == "denied",
        )
        .scalar() or 0
    )

    def _serialize(entry: AuditLog) -> dict:
        return {
            "id": entry.id,
            "event_type": entry.event_type,
            "action": entry.action,
            "outcome": entry.outcome,
            "actor_user_id": entry.actor_user_id,
            "actor_patient_id": entry.actor_patient_id,
            "actor_role": entry.actor_role,
            "subject_patient_id": entry.subject_patient_id,
            "resource_type": entry.resource_type,
            "ip_address": entry.ip_address,
            "timestamp": entry.created_at.isoformat() if entry.created_at else None,
        }

    return {
        "time_window_hours": hours,
        "summary": {
            "total_events": total_events,
            "total_denied": total_denied,
            "suspicious_ip_count": len(suspicious_ips),
        },
        "recent_logins": [_serialize(e) for e in recent_logins],
        "recent_downloads": [_serialize(e) for e in recent_downloads],
        "recent_exports": [_serialize(e) for e in recent_exports],
        "failed_logins": [_serialize(e) for e in failed_logins],
        "suspicious_ips": [
            {"ip": ip, "fail_count": count}
            for ip, count in suspicious_ips
        ],
        "bulk_operations": [_serialize(e) for e in bulk_operations],
    }
