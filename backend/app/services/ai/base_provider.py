"""
Базовый класс для AI провайдеров
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)


class AIRequest(BaseModel):
    """Базовая модель запроса к AI"""
    prompt: str
    max_tokens: Optional[int] = 1000
    temperature: Optional[float] = 0.7
    system_prompt: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


class AIResponse(BaseModel):
    """Базовая модель ответа от AI"""
    content: str
    usage: Optional[Dict[str, int]] = None
    model: Optional[str] = None
    provider: str
    error: Optional[str] = None


class BaseAIProvider(ABC):
    """Базовый класс для всех AI провайдеров"""
    
    def __init__(self, api_key: str, model: Optional[str] = None):
        self.api_key = api_key
        self.model = model or self.get_default_model()
        self.provider_name = self.__class__.__name__.replace('Provider', '')
    
    @abstractmethod
    def get_default_model(self) -> str:
        """Получить модель по умолчанию"""
        pass
    
    @abstractmethod
    async def generate(self, request: AIRequest) -> AIResponse:
        """Генерация ответа"""
        pass
    
    @abstractmethod
    async def analyze_complaint(self, complaint: str, patient_info: Optional[Dict] = None) -> Dict[str, Any]:
        """Анализ жалоб пациента и создание плана обследования"""
        pass
    
    @abstractmethod
    async def suggest_icd10(self, symptoms: List[str], diagnosis: Optional[str] = None) -> List[Dict[str, str]]:
        """Подсказки кодов МКБ-10"""
        pass
    
    @abstractmethod
    async def interpret_lab_results(self, results: List[Dict[str, Any]], patient_info: Optional[Dict] = None) -> Dict[str, Any]:
        """Интерпретация результатов анализов"""
        pass
    
    @abstractmethod
    async def analyze_skin(self, image_data: bytes, metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """Анализ состояния кожи по фото"""
        pass
    
    @abstractmethod
    async def interpret_ecg(self, ecg_data: Dict[str, Any], patient_info: Optional[Dict] = None) -> Dict[str, Any]:
        """Интерпретация ЭКГ"""
        pass
    
    def _build_system_prompt(self, role: str) -> str:
        """Построение системного промпта в зависимости от роли"""
        prompts = {
            "doctor": "Вы опытный врач-терапевт с 20-летним стажем. Даете профессиональные медицинские рекомендации.",
            "cardiologist": "Вы врач-кардиолог высшей категории. Специализируетесь на интерпретации ЭКГ и ЭхоКГ.",
            "dermatologist": "Вы врач-дерматолог и косметолог. Анализируете состояние кожи и даете рекомендации.",
            "lab": "Вы врач клинической лабораторной диагностики. Интерпретируете результаты анализов.",
            "icd": "Вы медицинский кодировщик. Помогаете подобрать правильные коды МКБ-10."
        }
        return prompts.get(role, prompts["doctor"])
    
    def _format_error(self, error: Exception) -> str:
        """Форматирование ошибки"""
        logger.error(f"{self.provider_name} error: {str(error)}")
        return f"Ошибка {self.provider_name}: {str(error)}"
