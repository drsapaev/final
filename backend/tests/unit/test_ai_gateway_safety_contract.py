"""Medical safety envelope for the canonical AI v2 gateway."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.services.ai.ai_gateway import AIGateway
from app.services.ai.ai_interfaces import AIProviderType, AIResponse, AITaskType


def _assert_safety(response: AIResponse) -> None:
    assert response.requires_doctor_confirmation is True
    assert response.decision_boundary == "suggestion_only"
    assert response.ai_notice.strip()
    assert response.model_dump()["requires_doctor_confirmation"] is True


def _synthetic_gateway() -> AIGateway:
    gateway = AIGateway()
    gateway._cache_enabled = True
    gateway._rate_limiter = SimpleNamespace(
        check_user_limit=AsyncMock(return_value=(True, None)),
        check_provider_limit=AsyncMock(return_value=(True, None)),
    )
    gateway._anonymizer = SimpleNamespace(
        anonymize=lambda payload: payload,
        get_removed_fields=lambda: [],
    )
    gateway._circuit_breaker = SimpleNamespace(
        is_available=AsyncMock(return_value=True),
        record_success=AsyncMock(),
    )
    gateway._audit_request = AsyncMock()
    gateway._provider_priority = [AIProviderType.MOCK]
    gateway._get_provider_instance = lambda _: SimpleNamespace(model="synthetic")
    gateway._route_task = AsyncMock(return_value={"content": "synthetic suggestion"})
    return gateway


@pytest.mark.asyncio
async def test_ai_v2_success_and_cache_keep_safety_envelope() -> None:
    gateway = _synthetic_gateway()
    payload = {"complaint": "synthetic symptom"}

    fresh = await gateway.execute(AITaskType.COMPLAINT_ANALYSIS, payload, user_id=1)
    cached = await gateway.execute(AITaskType.COMPLAINT_ANALYSIS, payload, user_id=1)

    assert fresh.status == "success"
    assert fresh.cached is False
    assert cached.status == "success"
    assert cached.cached is True
    gateway._route_task.assert_awaited_once()
    _assert_safety(fresh)
    _assert_safety(cached)


@pytest.mark.asyncio
async def test_ai_v2_rate_limit_and_provider_failure_keep_safety_envelope() -> None:
    gateway = _synthetic_gateway()
    gateway._rate_limiter.check_user_limit = AsyncMock(return_value=(False, 60))
    limited = await gateway.execute(AITaskType.COMPLAINT_ANALYSIS, {}, user_id=1)

    gateway._rate_limiter.check_user_limit = AsyncMock(return_value=(True, None))
    gateway._provider_priority = []
    unavailable = await gateway.execute(AITaskType.COMPLAINT_ANALYSIS, {}, user_id=1)

    assert limited.status == unavailable.status == "error"
    _assert_safety(limited)
    _assert_safety(unavailable)


@pytest.mark.asyncio
async def test_ai_v2_unexpected_error_keeps_safety_envelope() -> None:
    gateway = _synthetic_gateway()
    gateway._rate_limiter.check_user_limit = AsyncMock(
        side_effect=RuntimeError("synthetic failure")
    )

    response = await gateway.execute(AITaskType.COMPLAINT_ANALYSIS, {}, user_id=1)

    assert response.status == "error"
    assert response.error == "AI service temporarily unavailable"
    _assert_safety(response)


@pytest.mark.parametrize(
    "bad_fields",
    [
        {"requires_doctor_confirmation": False},
        {"decision_boundary": "final_decision"},
        {"ai_notice": ""},
    ],
)
def test_ai_v2_response_rejects_unsafe_safety_values(bad_fields: dict) -> None:
    safe_fields = {
        "status": "success",
        "provider": "mock",
        "model": "synthetic",
        "latency_ms": 0,
        "requires_doctor_confirmation": True,
        "decision_boundary": "suggestion_only",
        "ai_notice": "A doctor must confirm this suggestion.",
    }

    with pytest.raises(ValidationError):
        AIResponse.model_validate({**safe_fields, **bad_fields})


def test_ai_v2_response_requires_safety_fields() -> None:
    with pytest.raises(ValidationError):
        AIResponse(status="success", provider="mock", model="synthetic", latency_ms=0)
