"""Repository helpers for admin AI endpoints."""

from __future__ import annotations

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.ai_config import AIUsageLog


class AdminAIRepository:
    """Encapsulates AI usage log ORM queries for admin API."""

    def __init__(self, db: Session):
        self.db = db

    def list_usage_logs(
        self,
        *,
        skip: int,
        limit: int,
        provider_id: int | None,
        task_type: str | None,
        success_only: bool | None,
    ) -> list[AIUsageLog]:
        query = self.db.query(AIUsageLog)
        if provider_id:
            query = query.filter(AIUsageLog.provider_id == provider_id)
        if task_type:
            query = query.filter(AIUsageLog.task_type == task_type)
        if success_only is not None:
            query = query.filter(AIUsageLog.success == success_only)
        return query.order_by(desc(AIUsageLog.created_at)).offset(skip).limit(limit).all()

