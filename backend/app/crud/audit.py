from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import AuditLog


def log(
    db: Session,
    *,
    action: str,
    entity_type: str | None = None,
    entity_id: int | None = None,
    actor_user_id: int | None = None,
    payload: dict[str, Any] | None = None,
) -> AuditLog:
    row = AuditLog(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_user_id=actor_user_id,
        payload=(payload or None),
    )
    db.add(row)
    db.flush()
    return row


def list_logs(
    db: Session,
    *,
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    actor_user_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditLog]:
    stmt = select(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    if actor_user_id is not None:
        stmt = stmt.where(AuditLog.actor_user_id == actor_user_id)
    stmt = stmt.order_by(AuditLog.id.desc()).limit(limit).offset(offset)
    return list(db.execute(stmt).scalars().all())
