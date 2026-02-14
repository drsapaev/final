from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.admin_ai_service import AdminAIService


@pytest.mark.unit
class TestAdminAIService:
    def test_get_usage_logs_delegates_to_repository(self):
        expected = [SimpleNamespace(id=1), SimpleNamespace(id=2)]
        repository = SimpleNamespace(
            list_usage_logs=lambda **kwargs: expected,
        )
        service = AdminAIService(db=None, repository=repository)

        result = service.get_usage_logs(
            skip=0,
            limit=100,
            provider_id=None,
            task_type=None,
            success_only=None,
        )

        assert result == expected

