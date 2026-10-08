"""Compatibility contract for the OpenAI SDK 3.x transport migration."""

import json

import httpx2
import pytest
from openai import AsyncOpenAI, DefaultAsyncHttpx2Client

from app.services.ai.base_provider import AIRequest
from app.services.ai.grok_provider import GrokProvider
from app.services.ai.openai_provider import OpenAIProvider


class _TestProviderMethods:
    """Supply unrelated abstract operations so the provider clients can be exercised."""

    async def assess_emergency_level(self, *args, **kwargs):
        raise NotImplementedError

    async def predict_deterioration_risk(self, *args, **kwargs):
        raise NotImplementedError

    async def prioritize_patient_queue(self, *args, **kwargs):
        raise NotImplementedError

    async def recommend_care_pathway(self, *args, **kwargs):
        raise NotImplementedError

    async def triage_patient(self, *args, **kwargs):
        raise NotImplementedError


class _ConcreteOpenAIProvider(_TestProviderMethods, OpenAIProvider):
    pass


class _ConcreteGrokProvider(_TestProviderMethods, GrokProvider):
    pass


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider_type", "expected_base_url"),
    [
        pytest.param(_ConcreteOpenAIProvider, "https://api.openai.com/v1", id="openai"),
        pytest.param(_ConcreteGrokProvider, "https://api.x.ai/v1", id="grok"),
    ],
)
async def test_provider_request_works_with_openai_sdk_3_httpx2(
    provider_type, expected_base_url
):
    provider = provider_type(api_key="test-api-key", model="test-model")
    original_client = provider.client
    assert isinstance(original_client, AsyncOpenAI)
    assert str(original_client.base_url).rstrip("/") == expected_base_url

    requests = []

    def handle_request(request):
        requests.append(
            {
                "method": request.method,
                "url": str(request.url),
                "body": json.loads(request.content),
            }
        )
        return httpx2.Response(
            200,
            request=request,
            json={
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "created": 1_728_000_000,
                "model": "test-model",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "mocked response"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 12,
                    "completion_tokens": 3,
                    "total_tokens": 15,
                },
            },
        )

    mock_client = AsyncOpenAI(
        api_key="test-api-key",
        base_url=expected_base_url,
        timeout=10,
        http_client=DefaultAsyncHttpx2Client(
            transport=httpx2.MockTransport(handle_request)
        ),
    )
    provider.client = mock_client
    try:
        result = await provider.generate(
            AIRequest(
                system_prompt="synthetic system prompt",
                prompt="synthetic request",
                max_tokens=32,
                temperature=0,
            )
        )
    finally:
        await mock_client.close()
        await original_client.close()

    assert result.error is None
    assert result.content == "mocked response"
    assert result.usage == {
        "prompt_tokens": 12,
        "completion_tokens": 3,
        "total_tokens": 15,
    }
    assert len(requests) == 1
    assert requests[0]["method"] == "POST"
    assert requests[0]["url"] == f"{expected_base_url}/chat/completions"
    assert requests[0]["body"]["model"] == "test-model"
    assert requests[0]["body"]["messages"] == [
        {"role": "system", "content": "synthetic system prompt"},
        {"role": "user", "content": "synthetic request"},
    ]
