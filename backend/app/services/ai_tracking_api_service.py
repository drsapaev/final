"""Service layer for ai_tracking endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.repositories.ai_tracking_api_repository import AITrackingApiRepository


class AITrackingApiService:
    """Builds API payloads for AI tracking endpoints."""

    def __init__(
        self,
        db: Session,
        repository: AITrackingApiRepository | None = None,
    ):
        self.repository = repository or AITrackingApiRepository(db)

    def get_recent_requests(self, *, limit: int) -> dict:
        logs = self.repository.list_recent_requests(limit=limit)
        requests = []
        for log, provider in logs:
            requests.append(
                {
                    "id": log.id,
                    "task_type": log.task_type,
                    "specialty": log.specialty,
                    "provider_name": provider.name,
                    "model_name": provider.model,
                    "display_name": provider.display_name,
                    "success": log.success,
                    "response_time_ms": log.response_time_ms,
                    "tokens_used": log.tokens_used,
                    "cached_response": log.cached_response,
                    "error_message": log.error_message,
                    "created_at": log.created_at,
                }
            )
        return {
            "requests": requests,
            "total": len(requests),
            "timestamp": datetime.utcnow(),
        }

    def get_usage_trends(self, *, days_back: int) -> dict:
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)
        daily_usage = self.repository.list_daily_usage(cutoff_date=cutoff_date)

        trends: dict[str, dict] = {}
        for row in daily_usage:
            date_str = row.date.strftime("%Y-%m-%d")
            if date_str not in trends:
                trends[date_str] = {
                    "date": date_str,
                    "total_requests": 0,
                    "total_tokens": 0,
                    "models": [],
                }
            trends[date_str]["total_requests"] += row.requests_count
            trends[date_str]["total_tokens"] += row.total_tokens or 0
            trends[date_str]["models"].append(
                {
                    "provider": row.provider_name,
                    "model": row.model_name,
                    "requests": row.requests_count,
                    "avg_response_time": round(row.avg_response_time or 0, 2),
                    "tokens": row.total_tokens or 0,
                }
            )

        sorted_trends = sorted(trends.values(), key=lambda item: item["date"], reverse=True)
        return {
            "trends": sorted_trends,
            "period_days": days_back,
            "total_days": len(sorted_trends),
            "timestamp": datetime.utcnow(),
        }

