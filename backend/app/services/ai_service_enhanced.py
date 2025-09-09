"""
Улучшенный сервис для работы с AI провайдерами с трекингом моделей
"""
import asyncio
import json
import aiohttp
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

from app.models.ai_config import AIProvider, AIPromptTemplate, AIUsageLog
from app.crud import ai_config as crud_ai
from app.core.config import settings
from app.services.ai_tracking_service import AITrackingService, get_ai_tracking_service
from app.schemas.ai_tracking import AIResponseWithTracking, AIRequestTracking


class EnhancedAIService:
    """Улучшенный сервис для работы с AI провайдерами с полным трекингом"""
    
    def __init__(self, db: Session):
        self.db = db
        self.session = None
        self.tracking_service = get_ai_tracking_service(db)

    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()

    async def analyze_complaints_with_tracking(
        self,
        complaints_text: str,
        specialty: str = "general",
        language: str = "ru",
        user_id: Optional[int] = None
    ) -> AIResponseWithTracking:
        """
        Анализ жалоб пациента с полным трекингом AI модели
        """
        start_time = time.time()
        tracking = None
        
        try:
            # Получаем провайдер по умолчанию
            provider = crud_ai.get_default_provider(self.db)
            if not provider:
                raise Exception("AI провайдер не настроен")

            # Создаем трекинг запроса
            tracking = self.tracking_service.create_request_tracking(
                provider_id=provider.id,
                task_type="complaints_analysis",
                specialty=specialty,
                user_id=user_id,
                request_data={"complaints": complaints_text, "language": language}
            )

            # Получаем шаблон для анализа жалоб
            template = crud_ai.get_prompt_template(
                self.db,
                task_type="complaints_analysis",
                specialty=specialty,
                language=language
            )
            
            if not template:
                template = self._get_default_complaints_template()

            # Формируем промпт
            prompt = template.format(
                complaints=complaints_text,
                specialty=specialty,
                language=language
            )

            # Выполняем запрос к AI
            response_data = await self._call_ai_provider(
                provider=provider,
                prompt=prompt,
                task_type="complaints_analysis"
            )

            # Подсчитываем токены (упрощенная версия)
            tokens_used = len(prompt.split()) + len(str(response_data).split())

            # Завершаем трекинг
            result = self.tracking_service.complete_request_tracking(
                tracking=tracking,
                response_data=response_data,
                tokens_used=tokens_used,
                success=True
            )

            return result

        except Exception as e:
            # Завершаем трекинг с ошибкой
            if tracking:
                self.tracking_service.complete_request_tracking(
                    tracking=tracking,
                    response_data={},
                    tokens_used=0,
                    success=False,
                    error_message=str(e)
                )
            
            # Возвращаем ответ с ошибкой
            return AIResponseWithTracking(
                data={"error": str(e)},
                tracking=tracking or self._create_error_tracking(str(e))
            )

    async def generate_prescription_with_tracking(
        self,
        patient_data: Dict[str, Any],
        diagnosis: str,
        specialty: str = "general",
        user_id: Optional[int] = None
    ) -> AIResponseWithTracking:
        """
        Генерация рецепта с полным трекингом AI модели
        """
        start_time = time.time()
        tracking = None
        
        try:
            # Получаем провайдер по умолчанию
            provider = crud_ai.get_default_provider(self.db)
            if not provider:
                raise Exception("AI провайдер не настроен")

            # Создаем трекинг запроса
            tracking = self.tracking_service.create_request_tracking(
                provider_id=provider.id,
                task_type="prescription_generation",
                specialty=specialty,
                user_id=user_id,
                request_data={"patient_data": patient_data, "diagnosis": diagnosis}
            )

            # Получаем шаблон для генерации рецепта
            template = crud_ai.get_prompt_template(
                self.db,
                task_type="prescription_generation",
                specialty=specialty
            )
            
            if not template:
                template = self._get_default_prescription_template()

            # Формируем промпт
            prompt = template.format(
                patient_name=patient_data.get("name", "Пациент"),
                patient_age=patient_data.get("age", "не указан"),
                diagnosis=diagnosis,
                specialty=specialty
            )

            # Выполняем запрос к AI
            response_data = await self._call_ai_provider(
                provider=provider,
                prompt=prompt,
                task_type="prescription_generation"
            )

            # Подсчитываем токены
            tokens_used = len(prompt.split()) + len(str(response_data).split())

            # Завершаем трекинг
            result = self.tracking_service.complete_request_tracking(
                tracking=tracking,
                response_data=response_data,
                tokens_used=tokens_used,
                success=True
            )

            return result

        except Exception as e:
            # Завершаем трекинг с ошибкой
            if tracking:
                self.tracking_service.complete_request_tracking(
                    tracking=tracking,
                    response_data={},
                    tokens_used=0,
                    success=False,
                    error_message=str(e)
                )
            
            return AIResponseWithTracking(
                data={"error": str(e)},
                tracking=tracking or self._create_error_tracking(str(e))
            )

    async def _call_ai_provider(
        self,
        provider: AIProvider,
        prompt: str,
        task_type: str
    ) -> Dict[str, Any]:
        """Вызов AI провайдера"""
        
        if provider.name == "openai":
            return await self._call_openai(provider, prompt)
        elif provider.name == "gemini":
            return await self._call_gemini(provider, prompt)
        elif provider.name == "deepseek":
            return await self._call_deepseek(provider, prompt)
        else:
            raise Exception(f"Неподдерживаемый провайдер: {provider.name}")

    async def _call_openai(self, provider: AIProvider, prompt: str) -> Dict[str, Any]:
        """Вызов OpenAI API"""
        # Здесь должна быть реальная реализация OpenAI API
        # Пока возвращаем заглушку
        return {
            "summary": f"Анализ выполнен с помощью {provider.display_name}",
            "model_used": provider.model,
            "confidence": 0.85
        }

    async def _call_gemini(self, provider: AIProvider, prompt: str) -> Dict[str, Any]:
        """Вызов Gemini API"""
        # Здесь должна быть реальная реализация Gemini API
        return {
            "summary": f"Анализ выполнен с помощью {provider.display_name}",
            "model_used": provider.model,
            "confidence": 0.82
        }

    async def _call_deepseek(self, provider: AIProvider, prompt: str) -> Dict[str, Any]:
        """Вызов DeepSeek API"""
        # Здесь должна быть реальная реализация DeepSeek API
        return {
            "summary": f"Анализ выполнен с помощью {provider.display_name}",
            "model_used": provider.model,
            "confidence": 0.80
        }

    def _get_default_complaints_template(self) -> str:
        """Базовый шаблон для анализа жалоб"""
        return """
        Проанализируйте жалобы пациента:
        
        Жалобы: {complaints}
        Специализация: {specialty}
        Язык: {language}
        
        Предоставьте:
        1. Краткое резюме жалоб
        2. Возможные диагнозы
        3. Рекомендуемые обследования
        4. План лечения
        """

    def _get_default_prescription_template(self) -> str:
        """Базовый шаблон для генерации рецепта"""
        return """
        Создайте рецепт для пациента:
        
        Пациент: {patient_name}
        Возраст: {patient_age}
        Диагноз: {diagnosis}
        Специализация: {specialty}
        
        Предоставьте:
        1. Названия препаратов
        2. Дозировки
        3. Способ применения
        4. Длительность приема
        """

    def _create_error_tracking(self, error_message: str) -> AIRequestTracking:
        """Создать трекинг для ошибки"""
        # Создаем минимальный трекинг для ошибки
        from app.schemas.ai_tracking import AIModelInfo
        
        model_info = AIModelInfo(
            provider_id=0,
            provider_name="unknown",
            model_name="unknown",
            temperature=0.0,
            max_tokens=0
        )
        
        return AIRequestTracking(
            request_id="error",
            task_type="error",
            model_info=model_info,
            response_time_ms=0,
            tokens_used=0,
            success=False,
            error_message=error_message
        )

    def get_model_stats(self, days_back: int = 30) -> List[Dict[str, Any]]:
        """Получить статистику по AI моделям"""
        return self.tracking_service.get_model_stats(days_back)

    def get_provider_stats(self, days_back: int = 30) -> List[Dict[str, Any]]:
        """Получить статистику по провайдерам AI"""
        return self.tracking_service.get_provider_stats(days_back)


# Глобальные функции для использования в API
async def get_enhanced_ai_service(db: Session) -> EnhancedAIService:
    """Получить экземпляр улучшенного AI сервиса"""
    return EnhancedAIService(db)
