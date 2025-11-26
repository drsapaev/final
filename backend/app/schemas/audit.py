from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field

from app.schemas.base import ORMModel


class AuditCreate(ORMModel):
    action: str = Field(max_length=64)
    entity_type: Optional[str] = Field(default=None, max_length=64)
    entity_id: Optional[int] = None
    payload: Optional[dict] = None
    actor_user_id: Optional[int] = None
    ip: Optional[str] = Field(default=None, max_length=64)
    user_agent: Optional[str] = Field(default=None, max_length=512)


class AuditOut(AuditCreate):
    id: int
    created_at: Optional[datetime] = None
