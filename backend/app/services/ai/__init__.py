"""
AI сервисы для медицинской системы
"""
from .ai_manager import ai_manager, AIProviderType
from .base_provider import AIRequest, AIResponse

__all__ = [
    "ai_manager",
    "AIProviderType",
    "AIRequest", 
    "AIResponse"
]
