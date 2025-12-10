"""
Grok (xAI) провайдер для AI функций
Использует OpenAI-совместимый API
"""

import logging
from typing import Optional

from openai import AsyncOpenAI

from .openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)


class GrokProvider(OpenAIProvider):
    """
    Провайдер Grok (xAI)
    
    Grok использует OpenAI-совместимый API, поэтому наследуемся от OpenAIProvider.
    Поддерживает модели: grok-2, grok-2-mini, grok-beta
    
    Документация: https://docs.x.ai/api
    """

    # xAI API endpoint
    XAI_BASE_URL = "https://api.x.ai/v1"
    
    def __init__(self, api_key: str, model: Optional[str] = None):
        """
        Инициализация Grok провайдера
        
        Args:
            api_key: API ключ от xAI (https://console.x.ai)
            model: Модель (grok-2, grok-2-mini, grok-beta)
        """
        # Не вызываем super().__init__() напрямую, чтобы настроить base_url
        self.api_key = api_key
        self.model = model or self.get_default_model()
        self.provider_name = "Grok"
        
        # Создаём клиент с xAI base_url
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=self.XAI_BASE_URL,
        )
        
        logger.info(f"Grok provider initialized with model: {self.model}")

    def get_default_model(self) -> str:
        """
        Модель по умолчанию - grok-2
        
        Доступные модели:
        - grok-2: Основная модель (best performance)
        - grok-2-mini: Быстрая модель для простых задач
        - grok-beta: Бета-версия новых возможностей
        """
        return "grok-2"
    
    @classmethod
    def get_available_models(cls) -> list:
        """Список доступных моделей Grok"""
        return [
            {
                "id": "grok-2",
                "name": "Grok 2",
                "description": "Основная модель с лучшей производительностью",
                "context_length": 131072,
            },
            {
                "id": "grok-2-mini",
                "name": "Grok 2 Mini",
                "description": "Быстрая модель для простых задач",
                "context_length": 131072,
            },
            {
                "id": "grok-beta",
                "name": "Grok Beta",
                "description": "Бета-версия с новыми возможностями",
                "context_length": 131072,
            },
        ]
    
    def _build_system_prompt(self, role: str) -> str:
        """
        Переопределяем системный промпт для Grok
        Добавляем специфику медицинского контекста
        """
        base_prompts = {
            "doctor": """Вы опытный врач-терапевт с 20-летним стажем в клинической практике.
Даете профессиональные медицинские рекомендации, основанные на доказательной медицине.
При необходимости указываете на ограничения AI-диагностики и важность очной консультации.""",
            
            "cardiologist": """Вы врач-кардиолог высшей категории с экспертизой в интерпретации ЭКГ и ЭхоКГ.
Предоставляете детальный анализ кардиологических данных с учетом клинического контекста.
Всегда указываете на необходимость подтверждения диагноза специалистом.""",
            
            "dermatologist": """Вы врач-дерматолог и косметолог с опытом в дерматоскопии.
Анализируете состояние кожи по описанию и даете рекомендации по уходу и лечению.
Подчеркиваете важность очного осмотра для точной диагностики.""",
            
            "lab": """Вы врач клинической лабораторной диагностики.
Интерпретируете результаты анализов в контексте возможных заболеваний.
Указываете на необходимость учета индивидуальных особенностей пациента.""",
            
            "icd": """Вы медицинский кодировщик с экспертизой в МКБ-10.
Помогаете подобрать правильные диагностические коды.
Учитываете взаимосвязь между симптомами и диагнозами.""",
            
            "emergency": """Вы врач скорой медицинской помощи.
Оцениваете экстренность состояния и определяете приоритет медицинской помощи.
Фокусируетесь на выявлении жизнеугрожающих состояний.""",
        }
        
        return base_prompts.get(role, base_prompts["doctor"])
