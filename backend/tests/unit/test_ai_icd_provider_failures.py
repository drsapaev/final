"""Failed ICD provider responses must not masquerade as an empty result."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.ai.ai_gateway import AIGateway
from app.services.ai.ai_interfaces import AIProviderType, AITaskType
from app.services.ai.ai_manager import AIManager
from app.services.ai.base_provider import AIResponse as ProviderResponse
from app.services.ai.deepseek_provider import DeepSeekProvider
from app.services.ai.gemini_provider import GeminiProvider
from app.services.ai.openai_provider import OpenAIProvider

# The deployed OpenAI provider currently has unrelated unimplemented abstract
# triage methods. Fill only those for this test; suggest_icd10 is the real
# inherited provider implementation, with only its network generate mocked.
TestableOpenAIProvider = type(
    "TestableOpenAIProvider", (OpenAIProvider,),
    {name: lambda *_args, **_kwargs: None for name in OpenAIProvider.__abstractmethods__},
)


def _provider(cls, response):
    provider = cls.__new__(cls)
    provider.model = "SYNTHETIC"
    provider._build_system_prompt = lambda _role: "SYNTHETIC"
    provider.generate = AsyncMock(return_value=response)
    return provider


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_class", [DeepSeekProvider, GeminiProvider, TestableOpenAIProvider])
async def test_real_provider_error_is_not_reported_as_empty_list(provider_class):
    provider = _provider(provider_class, ProviderResponse(
        provider="synthetic", content="UNSAFE_PARTIAL", error="PRIVATE_ERROR"
    ))
    with pytest.raises(RuntimeError, match="AI provider unavailable") as caught:
        await provider.suggest_icd10(["SYNTHETIC"])
    assert "PRIVATE_ERROR" not in str(caught.value)
    assert "UNSAFE_PARTIAL" not in str(caught.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_class", [DeepSeekProvider, GeminiProvider, TestableOpenAIProvider])
async def test_real_provider_valid_empty_result_is_preserved(provider_class):
    provider = _provider(provider_class, ProviderResponse(
        provider="synthetic", content="[]", error=None
    ))
    assert await provider.suggest_icd10(["SYNTHETIC"]) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_class", [DeepSeekProvider, GeminiProvider, TestableOpenAIProvider])
@pytest.mark.parametrize("fenced", [False, True])
async def test_real_provider_valid_suggestion_is_preserved(provider_class, fenced):
    content = '[{"code":"SYNTHETIC","name":"Synthetic name"}]'
    if fenced:
        content = f"```json\n{content}\n```"
    provider = _provider(provider_class, ProviderResponse(
        provider="synthetic", content=content, error=None
    ))
    result = await provider.suggest_icd10(["SYNTHETIC"])
    assert len(result) == 1
    assert result[0]["code"] == "SYNTHETIC"
    assert result[0].get("name", result[0].get("label")) == "Synthetic name"


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_class", [DeepSeekProvider, GeminiProvider, TestableOpenAIProvider])
async def test_numeric_string_confidence_remains_compatible(provider_class):
    provider = _provider(provider_class, ProviderResponse(
        provider="synthetic",
        content='[{"code":"SYNTHETIC","name":"Synthetic name","confidence":"0.8"}]',
        error=None,
    ))
    result = await provider.suggest_icd10(["SYNTHETIC"])
    expected = 0.8 if provider_class is DeepSeekProvider else "0.8"
    assert result[0]["confidence"] == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_class", [DeepSeekProvider, GeminiProvider, TestableOpenAIProvider])
@pytest.mark.parametrize("invalid", [
    "PRIVATE_INVALID_JSON", '{"code":"SYNTHETIC"}', '["SYNTHETIC"]',
    '[{"name":"Synthetic"}]', '[{"code":"SYNTHETIC"}]',
    '[{"code":"SYNTHETIC","name":"Synthetic","confidence":2}]',
    '[{"code":"SYNTHETIC","name":"Synthetic","confidence":NaN}]',
    '[{"code":"SYNTHETIC","name":"Synthetic","confidence":"inf"}]',
    '[{"code":"SYNTHETIC","name":"Synthetic","confidence":"nan"}]',
    '[{"code":"SYNTHETIC","name":"Synthetic","confidence":true}]',
    '[{"code":"SYNTHETIC","name":"Synthetic","confidence":"-0.1"}]',
])
async def test_invalid_output_is_provider_failure_not_empty_success(provider_class, invalid, caplog):
    provider = _provider(provider_class, ProviderResponse(provider="synthetic", content=invalid, error=None))
    with pytest.raises(RuntimeError, match="invalid ICD suggestions") as caught:
        await provider.suggest_icd10(["SYNTHETIC"])
    assert "PRIVATE_INVALID_JSON" not in str(caught.value)
    assert "PRIVATE_INVALID_JSON" not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_class", [DeepSeekProvider, GeminiProvider, TestableOpenAIProvider])
@pytest.mark.parametrize("has_fallback", [True, False])
@pytest.mark.parametrize("failure_mode", ["provider_error", "malformed"])
async def test_gateway_falls_back_after_real_provider_error(provider_class, has_fallback, failure_mode):
    failed = _provider(provider_class, ProviderResponse(
        provider="synthetic", content="UNSAFE_PARTIAL",
        error="PRIVATE_ERROR" if failure_mode == "provider_error" else None,
    ))
    healthy = _provider(provider_class, ProviderResponse(
        provider="synthetic", content="[]", error=None
    ))
    gateway = AIGateway()
    gateway._cache_enabled = True
    gateway._rate_limiter = SimpleNamespace(
        check_user_limit=AsyncMock(return_value=(True, None)),
        check_provider_limit=AsyncMock(return_value=(True, None)),
    )
    gateway._anonymizer = SimpleNamespace(anonymize=lambda payload: payload,
                                          get_removed_fields=lambda: [])
    gateway._circuit_breaker = SimpleNamespace(is_available=AsyncMock(return_value=True),
                                              record_failure=AsyncMock(),
                                              record_success=AsyncMock())
    gateway._audit_request = AsyncMock()
    gateway._provider_priority = [AIProviderType.DEEPSEEK]
    if has_fallback:
        gateway._provider_priority.append(AIProviderType.MOCK)
    gateway._get_provider_instance = lambda p: failed if p == AIProviderType.DEEPSEEK else healthy
    result = await gateway.execute(AITaskType.ICD10_SUGGESTION, {"symptoms": ["SYNTHETIC"]}, user_id=1)
    if has_fallback:
        assert result.status == "success"
        assert result.provider == "mock"
        # Keep the pre-existing v2 content shape while distinguishing errors.
        assert result.data == {"content": "[]"}
        assert len(gateway._cache) == 1
    else:
        assert result.status == "error"
        assert not result.data
        assert not gateway._cache
    assert result.ai_safety_meta.requires_doctor_confirmation is True
    assert "UNSAFE_PARTIAL" not in str(result.model_dump())
    gateway._circuit_breaker.record_failure.assert_awaited_once_with("deepseek")


@pytest.mark.asyncio
async def test_legacy_manager_missing_provider_is_not_empty_success():
    manager = AIManager.__new__(AIManager)
    manager.get_provider = lambda *_args: None
    with pytest.raises(RuntimeError, match="AI provider unavailable"):
        await manager.suggest_icd10(["SYNTHETIC"])
