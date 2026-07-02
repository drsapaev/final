"""Repository helpers for ai_tracking endpoints."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.ai_config import AIProvider, AIUsageLog


class AITrackingApiRepository:
    """Encapsulates ORM queries used by AI tracking API."""

    def __init__(self, db: Session):
        self.db = db

    def list_recent_requests(self, *, limit: int):
        return (
            self.db.query(AIUsageLog, AIProvider)
            .join(AIProvider, AIUsageLog.provider_id == AIProvider.id)
            .order_by(AIUsageLog.created_at.desc())
            .limit(limit)
            .all()
        )

    def list_daily_usage(self, *, cutoff_date: datetime):
        return (
            self.db.query(
                func.date(AIUsageLog.created_at).label("date"),
                AIProvider.name.label("provider_name"),
                AIProvider.model.label("model_name"),
                func.count(AIUsageLog.id).label("requests_count"),
                func.avg(AIUsageLog.response_time_ms).label("avg_response_time"),
                func.sum(AIUsageLog.tokens_used).label("total_tokens"),
            )
            .join(AIProvider, AIUsageLog.provider_id == AIProvider.id)
            .filter(AIUsageLog.created_at >= cutoff_date)
            .group_by(
                func.date(AIUsageLog.created_at),
                AIProvider.id,
                AIProvider.name,
                AIProvider.model,
            )
            .order_by(func.date(AIUsageLog.created_at).desc())
            .all()
        )

