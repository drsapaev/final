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
# Main gateway (RECOMMENDED entry point)
from .ai_gateway import AIGateway, get_ai_gateway
from .ai_interfaces import (
    AIComplaintResponse,
    AIICD10Response,
    AIICD10Suggestion,
    AIImageResponse,
    AILabResponse,
    AIProviderType,
    AIResponse,
    AITaskType,
    IAIGateway,
    IAnonymizer,
)

# Legacy manager (still used internally)
from .ai_manager import ai_manager, get_ai_manager

# Base provider for custom implementations
from .base_provider import AIRequest

# Utilities
from .pii_anonymizer import PIIAnonymizer, get_anonymizer
from .rate_limiter import AIRateLimiter, enforce_rate_limit, get_rate_limiter

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
