from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.base import ORMModel


class AuditCreate(ORMModel):
    action: str = Field(max_length=64)
    entity_type: str | None = Field(default=None, max_length=64)
    entity_id: int | None = None
    payload: dict | None = None
    actor_user_id: int | None = None
    ip: str | None = Field(default=None, max_length=64)
    user_agent: str | None = Field(default=None, max_length=512)


class AuditOut(AuditCreate):
    id: int
    created_at: datetime | None = None
