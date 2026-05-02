from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.services.ai_tracking_api_service import AITrackingApiService


@pytest.mark.unit
class TestAITrackingApiService:
    def test_get_recent_requests_formats_rows(self):
        log = SimpleNamespace(
            id=1,
            task_type="chat",
            specialty="cardio",
            success=True,
            response_time_ms=120,
            tokens_used=50,
            cached_response=False,
            error_message=None,
            created_at="2026-01-01T10:00:00",
        )
        provider = SimpleNamespace(
            name="openai",
            model="gpt-4o-mini",
            display_name="OpenAI",
        )
        repository = SimpleNamespace(list_recent_requests=lambda limit: [(log, provider)])
        service = AITrackingApiService(db=None, repository=repository)

        result = service.get_recent_requests(limit=10)

        assert result["total"] == 1
        assert result["requests"][0]["provider_name"] == "openai"

    def test_get_usage_trends_groups_by_date(self):
        rows = [
            SimpleNamespace(
                date=date(2026, 1, 2),
                provider_name="openai",
                model_name="gpt-4o-mini",
                requests_count=3,
                avg_response_time=100.0,
                total_tokens=150,
            ),
            SimpleNamespace(
                date=date(2026, 1, 2),
                provider_name="deepseek",
                model_name="deepseek-chat",
                requests_count=2,
                avg_response_time=90.0,
                total_tokens=80,
            ),
        ]
        repository = SimpleNamespace(list_daily_usage=lambda cutoff_date: rows)
        service = AITrackingApiService(db=None, repository=repository)

        result = service.get_usage_trends(days_back=7)

        assert result["period_days"] == 7
        assert result["total_days"] == 1
        assert result["trends"][0]["total_requests"] == 5

