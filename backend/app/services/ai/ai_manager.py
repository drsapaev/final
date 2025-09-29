"""
AI Manager для управления различными AI провайдерами
"""
from typing import Dict, List, Optional, Any, Type
from enum import Enum
import os
from .base_provider import BaseAIProvider, AIRequest, AIResponse
from .openai_provider import OpenAIProvider
from .gemini_provider import GeminiProvider
from .deepseek_provider import DeepSeekProvider
from .mock_provider import MockProvider
from ...core.config import settings
import logging

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
        self.providers: Dict[AIProviderType, BaseAIProvider] = {}
        self.default_provider: Optional[AIProviderType] = None
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Инициализация доступных провайдеров"""
        provider_classes: Dict[AIProviderType, Type[BaseAIProvider]] = {
            AIProviderType.OPENAI: OpenAIProvider,
            AIProviderType.GEMINI: GeminiProvider,
            AIProviderType.DEEPSEEK: DeepSeekProvider,
            AIProviderType.MOCK: MockProvider
        }
        
        # Загружаем API ключи из переменных окружения или настроек
        api_keys = {
            AIProviderType.OPENAI: os.getenv("OPENAI_API_KEY", getattr(settings, "OPENAI_API_KEY", None)),
            AIProviderType.GEMINI: os.getenv("GEMINI_API_KEY", getattr(settings, "GEMINI_API_KEY", None)),
            AIProviderType.DEEPSEEK: os.getenv("DEEPSEEK_API_KEY", getattr(settings, "DEEPSEEK_API_KEY", None)),
            AIProviderType.MOCK: "mock-api-key"  # Mock провайдер всегда доступен
        }
        
        # Инициализируем провайдеры с доступными ключами
        for provider_type, api_key in api_keys.items():
            if api_key:
                try:
                    provider_class = provider_classes[provider_type]
                    self.providers[provider_type] = provider_class(api_key)
                    logger.info(f"Initialized {provider_type.value} provider")
                    
                    # Устанавливаем первый доступный провайдер как default
                    if not self.default_provider:
                        self.default_provider = provider_type
                except Exception as e:
                    logger.error(f"Failed to initialize {provider_type.value} provider: {str(e)}")
        
        if not self.providers:
            logger.warning("No AI providers initialized. Please set API keys.")
    
    def get_provider(self, provider_type: Optional[AIProviderType] = None) -> Optional[BaseAIProvider]:
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
    
    def get_available_providers(self) -> List[str]:
        """Получить список доступных провайдеров"""
        return [p.value for p in self.providers.keys()]
    
    async def generate(self, prompt: str, provider_type: Optional[AIProviderType] = None, **kwargs) -> AIResponse:
        """Универсальная генерация текста"""
        provider = self.get_provider(provider_type)
        if not provider:
            return AIResponse(
                content="",
                provider="none",
                error="No AI provider available"
            )
        
        request = AIRequest(prompt=prompt, **kwargs)
        return await provider.generate(request)
    
    async def analyze_complaint(
        self, 
        complaint: str, 
        patient_info: Optional[Dict] = None,
        provider_type: Optional[AIProviderType] = None
    ) -> Dict[str, Any]:
        """Анализ жалоб пациента"""
        provider = self.get_provider(provider_type)
        if not provider:
            return {"error": "No AI provider available"}
        
        return await provider.analyze_complaint(complaint, patient_info)
    
    async def suggest_icd10(
        self,
        symptoms: List[str],
        diagnosis: Optional[str] = None,
        provider_type: Optional[AIProviderType] = None
    ) -> List[Dict[str, str]]:
        """Подсказки кодов МКБ-10"""
        provider = self.get_provider(provider_type)
        if not provider:
            return []
        
        return await provider.suggest_icd10(symptoms, diagnosis)
    
    async def interpret_lab_results(
        self,
        results: List[Dict[str, Any]],
        patient_info: Optional[Dict] = None,
        provider_type: Optional[AIProviderType] = None
    ) -> Dict[str, Any]:
        """Интерпретация лабораторных результатов"""
        provider = self.get_provider(provider_type)
        if not provider:
            return {"error": "No AI provider available"}
        
        return await provider.interpret_lab_results(results, patient_info)
    
    async def analyze_skin(
        self,
        image_data: bytes,
        metadata: Optional[Dict] = None,
        provider_type: Optional[AIProviderType] = None
    ) -> Dict[str, Any]:
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
        ecg_data: Dict[str, Any],
        patient_info: Optional[Dict] = None,
        provider_type: Optional[AIProviderType] = None
    ) -> Dict[str, Any]:
        """Интерпретация ЭКГ"""
        provider = self.get_provider(provider_type)
        if not provider:
            return {"error": "No AI provider available"}
        
        return await provider.interpret_ecg(ecg_data, patient_info)


# Глобальный экземпляр менеджера
ai_manager = AIManager()


def get_ai_manager() -> AIManager:
    """Получить глобальный экземпляр AI менеджера"""
    return ai_manager
