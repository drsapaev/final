"""Core mixin for MockProvider.

Split from mock_provider.py.
"""
from __future__ import annotations

from app.services.ai.mock_provider_pkg._base import (
    MockProviderMixinBase,
    AIRequest,
    AIResponse,
    asyncio,
    logging,
    random,
    Any,
)


class CoreMixin(MockProviderMixinBase):
    """Core methods for MockProvider."""

    def __init__(self, api_key: str = "mock", model: str | None = None):
        super().__init__(api_key, model)


    def get_default_model(self) -> str:
        return "mock-model-v1"


    async def generate(self, request: AIRequest) -> AIResponse:
        """Имитация генерации ответа"""
        await asyncio.sleep(0.5)  # Имитация задержки API

        return AIResponse(
            content=f"Mock ответ на запрос: {request.prompt[:50]}...",
            usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            model=self.model,
            provider=self.provider_name,
        )


    def _get_clinical_significance(self, parameter: str, is_high: bool) -> str:
        """Получить клиническое значение отклонения"""
        significance_map = {
            "Гемоглобин": {
                True: "Возможна полицитемия, обезвоживание",
                False: "Возможна анемия, кровопотеря",
            },
            "Лейкоциты": {
                True: "Возможна инфекция, воспаление",
                False: "Возможна иммуносупрессия",
            },
            "СОЭ": {
                True: "Неспецифический маркер воспаления",
                False: "Обычно не имеет клинического значения",
            },
        }

        return significance_map.get(parameter, {}).get(
            is_high, "Требует клинической корреляции"
        )


