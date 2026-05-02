"""
AI Manager для управления различными AI провайдерами
"""

import logging
import os
from enum import Enum
from typing import Any

from ...core.config import settings
from .base_provider import AIRequest, AIResponse, BaseAIProvider
from .deepseek_provider import DeepSeekProvider
from .gemini_provider import GeminiProvider
from .mock_provider import MockProvider
from .openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)


class AIProviderType(str, Enum):
    """Типы AI провайдеров"""

    OPENAI = "openai"
    GEMINI = "gemini"
    DEEPSEEK = "deepseek"
    MOCK = "mock"


class AIManager:
    """Менеджер для работы с AI провайдерами"""

    def __init__(self):
        self.providers: dict[AIProviderType, BaseAIProvider] = {}
        self.default_provider: AIProviderType | None = None
        self._initialize_providers()

    def _initialize_providers(self):
        """Инициализация доступных провайдеров"""

        provider_classes: dict[AIProviderType, type[BaseAIProvider]] = {
            AIProviderType.OPENAI: OpenAIProvider,
            AIProviderType.GEMINI: GeminiProvider,
            AIProviderType.DEEPSEEK: DeepSeekProvider,
            AIProviderType.MOCK: MockProvider,
        }

        # Загружаем API ключи из переменных окружения или настроек
        api_keys = {
            AIProviderType.OPENAI: os.getenv(
                "OPENAI_API_KEY", getattr(settings, "OPENAI_API_KEY", None)
            ),
            AIProviderType.GEMINI: os.getenv(
                "GEMINI_API_KEY", getattr(settings, "GEMINI_API_KEY", None)
            ),
            AIProviderType.DEEPSEEK: os.getenv(
                "DEEPSEEK_API_KEY", getattr(settings, "DEEPSEEK_API_KEY", None)
            ),
            AIProviderType.MOCK: "mock-api-key",  # Mock провайдер всегда доступен
        }

        # Инициализируем Mock провайдер сначала как fallback
        try:
            self.providers[AIProviderType.MOCK] = MockProvider()
            logger.info(
                "Initialized Enhanced Mock provider (realistic medical responses)"
            )
        except Exception as e:
            logger.error(f"Failed to initialize mock provider: {str(e)}")

        # Инициализируем провайдеры с доступными ключами
        # Приоритет: DeepSeek > Gemini > OpenAI (DeepSeek - ОСНОВНОЙ!)
        priority_order = [
            AIProviderType.DEEPSEEK,
            AIProviderType.GEMINI,
            AIProviderType.OPENAI,
        ]

        for provider_type in priority_order:
            api_key = api_keys.get(provider_type)
            if api_key and provider_type != AIProviderType.MOCK:
                try:
                    provider_class = provider_classes[provider_type]
                    self.providers[provider_type] = provider_class(api_key)
                    logger.info(f"Initialized {provider_type.value} provider")

                    # Устанавливаем первый доступный провайдер как default
                    if not self.default_provider:
                        self.default_provider = provider_type
                        logger.info(f"Set {provider_type.value} as DEFAULT provider")
                except Exception as e:
                    logger.error(
                        f"Failed to initialize {provider_type.value} provider: {str(e)}"
                    )

        # Если нет других провайдеров, используем Mock
        if not self.default_provider:
            self.default_provider = AIProviderType.MOCK
            logger.warning("Using Enhanced Mock provider (no external API configured)")

        if not self.providers:
            logger.warning("No AI providers initialized. Please set API keys.")

    def get_provider(
        self, provider_type: AIProviderType | None = None
    ) -> BaseAIProvider | None:
        """Получить провайдер по типу или default"""
        if provider_type:
            return self.providers.get(provider_type)
        elif self.default_provider:
            return self.providers.get(self.default_provider)
        return None

    def set_default_provider(self, provider_type: AIProviderType) -> bool:
        """Установить провайдер по умолчанию"""
        if provider_type in self.providers:
            self.default_provider = provider_type
            return True
        return False

    def get_available_providers(self) -> list[str]:
        """Получить список доступных провайдеров"""
        return [p.value for p in self.providers.keys()]

    async def generate(
        self, prompt: str, provider_type: AIProviderType | None = None, **kwargs
    ) -> AIResponse:
        """Универсальная генерация текста"""
        provider = self.get_provider(provider_type)
        if not provider:
            return AIResponse(
                content="", provider="none", error="No AI provider available"
            )

        request = AIRequest(prompt=prompt, **kwargs)
        return await provider.generate(request)

    async def analyze_complaint(
        self,
        complaint: str,
        patient_info: dict | None = None,
        provider_type: AIProviderType | None = None,
    ) -> dict[str, Any]:
        """Анализ жалоб пациента"""
        provider = self.get_provider(provider_type)
        if not provider:
            return {"error": "No AI provider available"}

        return await provider.analyze_complaint(complaint, patient_info)

    async def suggest_icd10(
        self,
        symptoms: list[str],
        diagnosis: str | None = None,
        provider_type: AIProviderType | None = None,
    ) -> list[dict[str, str]]:
        """Подсказки кодов МКБ-10"""
        provider = self.get_provider(provider_type)
        if not provider:
            return []

        return await provider.suggest_icd10(symptoms, diagnosis)

    async def interpret_lab_results(
        self,
        results: list[dict[str, Any]],
        patient_info: dict | None = None,
        provider_type: AIProviderType | None = None,
    ) -> dict[str, Any]:
        """Интерпретация лабораторных результатов"""
        provider = self.get_provider(provider_type)
        if not provider:
            return {"error": "No AI provider available"}

        return await provider.interpret_lab_results(results, patient_info)

    async def analyze_skin(
        self,
        image_data: bytes,
        metadata: dict | None = None,
        provider_type: AIProviderType | None = None,
    ) -> dict[str, Any]:
        """Анализ состояния кожи"""
        # Для анализа изображений предпочитаем OpenAI или Gemini
        if not provider_type:
            if AIProviderType.OPENAI in self.providers:
                provider_type = AIProviderType.OPENAI
            elif AIProviderType.GEMINI in self.providers:
                provider_type = AIProviderType.GEMINI

        provider = self.get_provider(provider_type)
        if not provider:
            return {"error": "No AI provider available for image analysis"}

        return await provider.analyze_skin(image_data, metadata)

    async def interpret_ecg(
        self,
        ecg_data: dict[str, Any],
        patient_info: dict | None = None,
        provider_type: AIProviderType | None = None,
    ) -> dict[str, Any]:
        """Интерпретация ЭКГ"""
        provider = self.get_provider(provider_type)
        if not provider:
            return {"error": "No AI provider available"}

        return await provider.interpret_ecg(ecg_data, patient_info)

    async def analyze_medical_trends(
        self,
        medical_data: list[dict],
        time_period: str,
        analysis_type: str,
        provider: AIProviderType | None = None,
    ) -> dict[str, Any]:
        """Анализ медицинских трендов и паттернов в данных"""
        provider_instance = self.get_provider(provider)
        if not provider_instance:
            raise ValueError("Нет доступного AI провайдера")

        return await provider_instance.analyze_medical_trends(
            medical_data=medical_data,
            time_period=time_period,
            analysis_type=analysis_type,
        )


# Глобальный экземпляр менеджера
ai_manager = AIManager()


def get_ai_manager() -> AIManager:
    """Получить глобальный экземпляр AI менеджера"""
    return ai_manager
