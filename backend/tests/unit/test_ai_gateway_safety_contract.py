"""Medical safety envelope for the canonical AI v2 gateway."""

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.services.ai.ai_gateway import AIGateway
from app.services.ai.ai_interfaces import AIProviderType, AIResponse, AITaskType
from app.services.ai.base_provider import AIResponse as ProviderResponse
from app.services.ai.medical_safety import (
    MedicalAISafetyMeta,
    medical_ai_safety_meta,
    with_medical_ai_safety,
)


def _assert_safety(response: AIResponse) -> None:
    assert response.requires_doctor_confirmation is True
    assert response.ai_safety_meta.requires_doctor_confirmation is True
    assert response.decision_boundary == "suggestion_only"
    assert response.ai_notice.strip()
    assert response.model_dump()["requires_doctor_confirmation"] is True
    assert response.model_dump()["ai_safety_meta"] == {
        "requires_doctor_confirmation": True
    }


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


@pytest.mark.asyncio
async def test_ai_v2_unexpected_error_log_omits_exception_text(caplog) -> None:
    gateway = _synthetic_gateway()
    gateway._rate_limiter.check_user_limit = AsyncMock(
        side_effect=RuntimeError("AI_RESPONSE_CANARY")
    )

    with caplog.at_level(logging.ERROR, logger="app.services.ai.ai_gateway"):
        response = await gateway.execute(AITaskType.COMPLAINT_ANALYSIS, {}, user_id=1)

    assert response.status == "error"
    assert "AI_RESPONSE_CANARY" not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)
    error_record = next(
        record for record in caplog.records if record.levelno == logging.ERROR
    )
    assert error_record.diagnostic_code == "ai_gateway_unexpected_error"
    assert error_record.error_type == "RuntimeError"


@pytest.mark.asyncio
async def test_ai_v2_provider_failure_log_omits_exception_text(caplog) -> None:
    gateway = _synthetic_gateway()
    gateway._provider_priority = [AIProviderType.MOCK]
    gateway._circuit_breaker.record_failure = AsyncMock()
    gateway._route_task = AsyncMock(
        side_effect=RuntimeError("AI_TOOL_ARGUMENTS_CANARY")
    )

    with caplog.at_level(logging.WARNING, logger="app.services.ai.ai_gateway"):
        response = await gateway.execute(AITaskType.COMPLAINT_ANALYSIS, {}, user_id=1)

    assert response.status == "error"
    assert "AI_TOOL_ARGUMENTS_CANARY" not in caplog.text
    warning_record = next(
        record for record in caplog.records if record.levelno == logging.WARNING
    )
    assert warning_record.diagnostic_code == "ai_provider_failure"
    assert warning_record.provider == "mock"
    assert warning_record.error_type == "RuntimeError"


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
        "ai_safety_meta": medical_ai_safety_meta(),
        "decision_boundary": "suggestion_only",
        "ai_notice": "A doctor must confirm this suggestion.",
    }

    with pytest.raises(ValidationError):
        AIResponse.model_validate({**safe_fields, **bad_fields})


def test_ai_v2_response_requires_safety_fields() -> None:
    with pytest.raises(ValidationError):
        AIResponse(status="success", provider="mock", model="synthetic", latency_ms=0)


@pytest.mark.parametrize("bad", [None, False, 1, "true", [], {}])
def test_nested_safety_meta_rejects_coerced_or_missing_true(bad) -> None:
    with pytest.raises(ValidationError):
        MedicalAISafetyMeta.model_validate({"requires_doctor_confirmation": bad})
    with pytest.raises(ValidationError):
        MedicalAISafetyMeta.model_validate({})


def test_server_boundary_replaces_provider_safety_without_mutating_payload() -> None:
    payload = {"data": "synthetic", "ai_safety_meta": {"requires_doctor_confirmation": False}}
    wrapped = with_medical_ai_safety(payload)
    assert wrapped["ai_safety_meta"] == {"requires_doctor_confirmation": True}
    assert payload["ai_safety_meta"] == {"requires_doctor_confirmation": False}
    wrapped["ai_safety_meta"]["requires_doctor_confirmation"] = False
    assert medical_ai_safety_meta()["requires_doctor_confirmation"] is True


def test_nested_model_instance_is_revalidated_and_assignment_is_guarded() -> None:
    constructed = MedicalAISafetyMeta.model_construct(requires_doctor_confirmation=False)
    with pytest.raises(ValidationError):
        AIResponse(
            status="success", provider="mock", model="synthetic", latency_ms=0,
            requires_doctor_confirmation=True, decision_boundary="suggestion_only",
            ai_notice="A doctor must confirm", ai_safety_meta=constructed,
        )
    valid = MedicalAISafetyMeta(**medical_ai_safety_meta())
    with pytest.raises(ValidationError):
        valid.requires_doctor_confirmation = False


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [None, {}, {"requires_doctor_confirmation": False},
                                 {"requires_doctor_confirmation": 1},
                                 {"requires_doctor_confirmation": "true"}])
async def test_invalid_cached_safety_is_discarded_and_recomputed(bad) -> None:
    gateway = _synthetic_gateway()
    payload = {"complaint": "synthetic symptom"}
    first = await gateway.execute(AITaskType.COMPLAINT_ANALYSIS, payload, user_id=1)
    key = gateway._make_cache_key(AITaskType.COMPLAINT_ANALYSIS, payload, None, user_id=1)
    old, expiry = gateway._cache[key]
    # A cache value written by older code or corrupted via model_construct
    # must not be blessed by simply adding the marker at read time.
    gateway._cache[key] = (old.model_copy(update={"ai_safety_meta": bad}), expiry)
    second = await gateway.execute(AITaskType.COMPLAINT_ANALYSIS, payload, user_id=1)
    assert first.status == second.status == "success"
    assert second.cached is False
    assert gateway._route_task.await_count == 2
    _assert_safety(second)


@pytest.mark.asyncio
async def test_cached_data_is_not_mutated_through_returned_response() -> None:
    gateway = _synthetic_gateway()
    payload = {"complaint": "synthetic symptom"}
    await gateway.execute(AITaskType.COMPLAINT_ANALYSIS, payload, user_id=1)
    cached = await gateway.execute(AITaskType.COMPLAINT_ANALYSIS, payload, user_id=1)
    cached.data["content"] = "mutated by caller"
    again = await gateway.execute(AITaskType.COMPLAINT_ANALYSIS, payload, user_id=1)
    assert again.data["content"] == "synthetic suggestion"
    _assert_safety(again)


@pytest.mark.asyncio
async def test_cached_legacy_model_without_nested_marker_is_discarded() -> None:
    gateway = _synthetic_gateway()
    payload = {"complaint": "synthetic symptom"}
    await gateway.execute(AITaskType.COMPLAINT_ANALYSIS, payload, user_id=1)
    key = gateway._make_cache_key(AITaskType.COMPLAINT_ANALYSIS, payload, None, user_id=1)
    old, expiry = gateway._cache[key]
    legacy = old.model_copy(deep=True)
    del legacy.__dict__["ai_safety_meta"]
    gateway._cache[key] = (legacy, expiry)
    second = await gateway.execute(AITaskType.COMPLAINT_ANALYSIS, payload, user_id=1)
    assert second.status == "success"
    assert second.cached is False
    assert gateway._route_task.await_count == 2
    _assert_safety(second)


@pytest.mark.asyncio
async def test_malformed_internal_result_fails_closed() -> None:
    gateway = _synthetic_gateway()
    bad = AIResponse.model_construct(**{
        "status": "success", "data": {"content": "UNSAFE_SYNTHETIC"},
        "provider": "mock", "model": "synthetic", "latency_ms": 0,
        "requires_doctor_confirmation": True, "decision_boundary": "suggestion_only",
        "ai_notice": "Confirm with a doctor", "ai_safety_meta": None,
    })
    gateway._execute_with_fallback = AsyncMock(return_value=bad)
    response = await gateway.execute(AITaskType.COMPLAINT_ANALYSIS, {}, user_id=1)
    assert response.status == "error"
    assert "UNSAFE_SYNTHETIC" not in str(response.model_dump())
    _assert_safety(response)


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_result", [
    ProviderResponse(content="UNSAFE_PARTIAL", provider="synthetic", error="private error"),
    {"content": "UNSAFE_PARTIAL", "error": "private error"},
])
async def test_provider_errors_with_partial_content_are_not_success_or_cached(provider_result) -> None:
    gateway = _synthetic_gateway()
    # Exercise actual _route_task and _execute_with_fallback, not their mocks.
    gateway._route_task = AIGateway._route_task.__get__(gateway)
    gateway._circuit_breaker.record_failure = AsyncMock()
    provider = SimpleNamespace(model="synthetic", analyze_complaint=AsyncMock(return_value=provider_result))
    gateway._get_provider_instance = lambda _: provider
    result = await gateway.execute(AITaskType.COMPLAINT_ANALYSIS, {"complaint": "synthetic"}, user_id=1)
    assert result.status == "error"
    assert "UNSAFE_PARTIAL" not in str(result.model_dump())
    assert "private error" not in str(result.model_dump())
    assert not gateway._cache
    gateway._circuit_breaker.record_failure.assert_awaited_once()
    _assert_safety(result)


@pytest.mark.asyncio
async def test_provider_failure_uses_next_provider_without_exposing_partial_content() -> None:
    gateway = _synthetic_gateway()
    gateway._route_task = AIGateway._route_task.__get__(gateway)
    gateway._circuit_breaker.record_failure = AsyncMock()
    gateway._provider_priority = [AIProviderType.DEEPSEEK, AIProviderType.MOCK]
    failed = SimpleNamespace(model="first", analyze_complaint=AsyncMock(return_value={
        "error": "provider failed", "raw_response": "UNSAFE_PARTIAL"
    }))
    successful = SimpleNamespace(model="second", analyze_complaint=AsyncMock(return_value={
        "content": "SYNTHETIC suggestion"
    }))
    gateway._get_provider_instance = lambda p: failed if p == AIProviderType.DEEPSEEK else successful
    result = await gateway.execute(AITaskType.COMPLAINT_ANALYSIS, {"complaint": "synthetic"}, user_id=1)
    assert result.status == "success"
    assert result.provider == "mock"
    assert result.data == {"content": "SYNTHETIC suggestion"}
    assert "UNSAFE_PARTIAL" not in str(result.model_dump())
    gateway._circuit_breaker.record_failure.assert_awaited_once_with("deepseek")
    _assert_safety(result)
