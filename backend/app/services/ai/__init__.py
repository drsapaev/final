"""
AI сервисы для медицинской системы

Components:
- AIGateway: Единая точка входа для всех AI операций
- AIManager: Менеджер провайдеров (legacy, используется AIGateway)
- AIInterfaces: Контракты (AITaskType, AIResponse, IAIGateway)
- PIIAnonymizer: Анонимизация персональных данных
- RateLimiter: Контроль частоты запросов
"""

# Core interfaces and types
from .ai_interfaces import (
    AITaskType,
    AIProviderType,
    AIResponse,
    AIICD10Response,
    AIICD10Suggestion,
    AIComplaintResponse,
    AILabResponse,
    AIImageResponse,
    IAIGateway,
    IAnonymizer,
)

# Main gateway (RECOMMENDED entry point)
from .ai_gateway import AIGateway, get_ai_gateway

# Legacy manager (still used internally)
from .ai_manager import ai_manager, get_ai_manager

# Utilities
from .pii_anonymizer import PIIAnonymizer, get_anonymizer
from .rate_limiter import AIRateLimiter, get_rate_limiter, enforce_rate_limit

# Base provider for custom implementations
from .base_provider import AIRequest

__all__ = [
    # Interfaces
    "AITaskType",
    "AIProviderType",
    "AIResponse",
    "AIICD10Response",
    "AIICD10Suggestion",
    "AIComplaintResponse",
    "AILabResponse",
    "AIImageResponse",
    "IAIGateway",
    "IAnonymizer",
    # Gateway
    "AIGateway",
    "get_ai_gateway",
    # Manager (legacy)
    "ai_manager",
    "get_ai_manager",
    # Utilities
    "PIIAnonymizer",
    "get_anonymizer",
    "AIRateLimiter",
    "get_rate_limiter",
    "enforce_rate_limit",
    # Base
    "AIRequest",
]
