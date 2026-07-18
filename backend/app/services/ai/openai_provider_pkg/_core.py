"""Core mixin for OpenAIProvider.

Split from openai_provider.py.
"""
from __future__ import annotations

from openai import AsyncOpenAI  # noqa: F401

from app.services.ai.openai_provider_pkg._base import (
    _PROVIDER_TIMEOUT,  # noqa: F401
    AIRequest,
    AIResponse,
    OpenAIProviderMixinBase,
)


class CoreMixin(OpenAIProviderMixinBase):
    """Core methods for OpenAIProvider."""

    def __init__(self, api_key: str, model: str | None = None):
        super().__init__(api_key, model)
        self.client = AsyncOpenAI(api_key=api_key, timeout=_PROVIDER_TIMEOUT)


    def get_default_model(self) -> str:
        return "gpt-4-turbo-preview"


    async def generate(self, request: AIRequest) -> AIResponse:
        """Генерация ответа через OpenAI API"""
        try:
            messages = []
            if request.system_prompt:
                messages.append({"role": "system", "content": request.system_prompt})
            messages.append({"role": "user", "content": request.prompt})

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
            )

            return AIResponse(
                content=response.choices[0].message.content,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
                model=response.model,
                provider=self.provider_name,
            )
        except Exception as e:
            return AIResponse(
                content="", provider=self.provider_name, error=self._format_error(e)
            )


