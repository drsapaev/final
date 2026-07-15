"""
Secrets Rotation Service — M5.8 (Epic M5 — Enterprise Security).

Tracks secret rotation status and provides rotation schedule.
Does NOT perform actual rotation (that requires server restart /
env var change), but tracks when secrets were last rotated and
alerts when rotation is overdue.

Secrets tracked:
- SECRET_KEY (JWT signing)
- AUTH_SECRET (legacy JWT helper)
- Telegram bot token
- API keys (per-service)
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit import AuditLog

ROTATION_INTERVAL_DAYS = 90  # Quarterly rotation


def get_secrets_rotation_status(db: Session) -> dict[str, Any]:
    """Check when each secret was last rotated (M5.8).

    Returns status for each secret: last_rotated, days_since, overdue.
    """
    secrets = ["SECRET_KEY", "AUTH_SECRET", "TELEGRAM_BOT_TOKEN", "API_KEYS"]
    now = datetime.now(UTC)
    result = {}

    for secret_name in secrets:
        # Find last rotation event in audit log
        last_rotation = (
            db.query(AuditLog)
            .filter(
                AuditLog.event_type == "SECRET_ROTATED",
                AuditLog.resource_type == "secret",
                AuditLog.payload.op("->>")("secret_name") == secret_name
                if hasattr(AuditLog.payload, "op")
                else True,
            )
            .order_by(AuditLog.created_at.desc())
            .first()
        )

        if last_rotation and last_rotation.created_at:
            last_rotated = last_rotation.created_at
            days_since = (now - last_rotated).days
            overdue = days_since > ROTATION_INTERVAL_DAYS
        else:
            last_rotated = None
            days_since = None
            overdue = True  # Never rotated = overdue

        result[secret_name] = {
            "last_rotated": last_rotated.isoformat() if last_rotated else None,
            "days_since_rotation": days_since,
            "overdue": overdue,
            "rotation_interval_days": ROTATION_INTERVAL_DAYS,
        }

    return {
        "secrets": result,
        "rotation_interval_days": ROTATION_INTERVAL_DAYS,
        "all_current": all(not s["overdue"] for s in result.values()),
    }


def record_secret_rotation(
    db: Session,
    *,
    secret_name: str,
    rotated_by: int,
    notes: str | None = None,
) -> None:
    """Record that a secret was rotated (M5.8).

    Call this after manually rotating a secret to track the rotation.
    """
    from app.services.audit_service import log_audit_event

    log_audit_event(
        db=db,
        event_type="SECRET_ROTATED",
        actor_user_id=rotated_by,
        action="rotate",
        resource_type="secret",
        resource_id=secret_name,
        outcome="success",
        extra_data={"secret_name": secret_name, "notes": notes},
    )
