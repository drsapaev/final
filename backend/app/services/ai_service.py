"""
Сервис для работы с AI провайдерами
Основа: passport.md стр. 3325-3888, detail.md стр. 3889-4282
"""
import asyncio
import json
import aiohttp
from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

from app.models.ai_config import AIProvider, AIPromptTemplate, AIUsageLog
from app.crud import ai_config as crud_ai
from app.core.config import settings

class AIService:
    """Сервис для работы с AI провайдерами"""
    
    def __init__(self, db: Session):
        self.db = db
        self.session = None

    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()

    async def analyze_complaints(
        self,
        complaints_text: str,
        specialty: str = "general",
        language: str = "ru"
    ) -> Dict[str, Any]:
        """
        Анализ жалоб пациента с помощью AI
        Из passport.md стр. 3325: анализ жалоб → план обследования
        """
        try:
            # Получаем провайдер по умолчанию
            provider = crud_ai.get_default_provider(self.db)
            if not provider:
                raise Exception("AI провайдер не настроен")

            # Получаем шаблон для анализа жалоб
            template = crud_ai.get_prompt_template(
                self.db,
                task_type="complaints_analysis",
                specialty=specialty,
                language=language
            )
            
            if not template:
                # Используем базовый шаблон
                template = self._get_default_complaints_template()

            # Формируем промпт
            prompt = self._build_prompt(template, {
                "complaints": complaints_text,
                "specialty": specialty,
                "language": language
            })

            # Отправляем запрос к AI
            response = await self._call_ai_provider(provider, prompt)
            
            # Логируем использование
            self._log_ai_usage(
                provider.id,
                "complaints_analysis",
                prompt,
                response,
                len(complaints_text)
            )

            # Парсим ответ
            result = self._parse_complaints_response(response)
            
            return {
                "success": True,
                "analysis": result,
                "provider": provider.name,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    async def suggest_icd10(
        self,
        diagnosis: str,
        specialty: str = "general",
        language: str = "ru"
    ) -> Dict[str, Any]:
        """
        Подбор кодов МКБ-10 по диагнозу
        Из passport.md стр. 3456: автоподбор МКБ-10
        """
        try:
            provider = crud_ai.get_default_provider(self.db)
            if not provider:
                raise Exception("AI провайдер не настроен")

            # Получаем шаблон для МКБ-10
            template = crud_ai.get_prompt_template(
                self.db,
                task_type="icd10_lookup",
                specialty=specialty,
                language=language
            )
            
            if not template:
                template = self._get_default_icd10_template()

            prompt = self._build_prompt(template, {
                "diagnosis": diagnosis,
                "specialty": specialty,
                "language": language
            })

            response = await self._call_ai_provider(provider, prompt)
            
            self._log_ai_usage(
                provider.id,
                "icd10_lookup",
                prompt,
                response,
                len(diagnosis)
            )

            result = self._parse_icd10_response(response)
            
            return {
                "success": True,
                "suggestions": result,
                "provider": provider.name,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    async def analyze_document(
        self,
        document_text: str,
        document_type: str = "medical_report",
        specialty: str = "general"
    ) -> Dict[str, Any]:
        """
        Анализ медицинских документов
        Из passport.md стр. 3678: анализ документов и извлечение данных
        """
        try:
            provider = crud_ai.get_default_provider(self.db)
            if not provider:
                raise Exception("AI провайдер не настроен")

            template = crud_ai.get_prompt_template(
                self.db,
                task_type="document_analysis",
                specialty=specialty
            )
            
            if not template:
                template = self._get_default_document_template()

            prompt = self._build_prompt(template, {
                "document_text": document_text,
                "document_type": document_type,
                "specialty": specialty
            })

            response = await self._call_ai_provider(provider, prompt)
            
            self._log_ai_usage(
                provider.id,
                "document_analysis",
                prompt,
                response,
                len(document_text)
            )

            result = self._parse_document_response(response)
            
            return {
                "success": True,
                "analysis": result,
                "provider": provider.name,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    async def _call_ai_provider(self, provider: AIProvider, prompt: str) -> str:
        """Вызов AI провайдера"""
        try:
            if provider.name == "openai":
                return await self._call_openai(provider, prompt)
            elif provider.name == "anthropic":
                return await self._call_anthropic(provider, prompt)
            elif provider.name == "yandex_gpt":
                return await self._call_yandex_gpt(provider, prompt)
            else:
                raise Exception(f"Неподдерживаемый провайдер: {provider.name}")
                
        except Exception as e:
            raise Exception(f"Ошибка вызова AI провайдера: {str(e)}")

    async def _call_openai(self, provider: AIProvider, prompt: str) -> str:
        """Вызов OpenAI API"""
        url = provider.api_url or "https://api.openai.com/v1/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": provider.model or "gpt-4",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": provider.temperature,
            "max_tokens": provider.max_tokens
        }
        
        async with self.session.post(url, headers=headers, json=data) as response:
            if response.status == 200:
                result = await response.json()
                return result["choices"][0]["message"]["content"]
            else:
                error_text = await response.text()
                raise Exception(f"OpenAI API error: {response.status} - {error_text}")

    async def _call_anthropic(self, provider: AIProvider, prompt: str) -> str:
        """Вызов Anthropic Claude API"""
        url = provider.api_url or "https://api.anthropic.com/v1/messages"
        
        headers = {
            "x-api-key": provider.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        
        data = {
            "model": provider.model or "claude-3-sonnet-20240229",
            "max_tokens": provider.max_tokens,
            "temperature": provider.temperature,
            "messages": [{"role": "user", "content": prompt}]
        }
        
        async with self.session.post(url, headers=headers, json=data) as response:
            if response.status == 200:
                result = await response.json()
                return result["content"][0]["text"]
            else:
                error_text = await response.text()
                raise Exception(f"Anthropic API error: {response.status} - {error_text}")

    async def _call_yandex_gpt(self, provider: AIProvider, prompt: str) -> str:
        """Вызов Yandex GPT API"""
        url = provider.api_url or "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
        
        headers = {
            "Authorization": f"Api-Key {provider.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "modelUri": f"gpt://{provider.model or 'yandexgpt-lite'}",
            "completionOptions": {
                "stream": False,
                "temperature": provider.temperature,
                "maxTokens": str(provider.max_tokens)
            },
            "messages": [
                {"role": "user", "text": prompt}
            ]
        }
        
        async with self.session.post(url, headers=headers, json=data) as response:
            if response.status == 200:
                result = await response.json()
                return result["result"]["alternatives"][0]["message"]["text"]
            else:
                error_text = await response.text()
                raise Exception(f"Yandex GPT API error: {response.status} - {error_text}")

    def _build_prompt(self, template: AIPromptTemplate, data: Dict[str, Any]) -> str:
        """Построить промпт из шаблона"""
        try:
            from jinja2 import Environment
            env = Environment()
            
            # Формируем полный промпт
            full_prompt = template.system_prompt
            
            if template.context_template:
                context_template = env.from_string(template.context_template)
                context = context_template.render(**data)
                full_prompt += f"\n\nКонтекст:\n{context}"
            
            task_template = env.from_string(template.task_template)
            task = task_template.render(**data)
            full_prompt += f"\n\nЗадача:\n{task}"
            
            # Добавляем примеры если есть
            if template.examples:
                full_prompt += "\n\nПримеры:"
                for example in template.examples:
                    full_prompt += f"\n{example}"
            
            return full_prompt
            
        except Exception as e:
            raise Exception(f"Ошибка построения промпта: {str(e)}")

    def _get_default_complaints_template(self) -> AIPromptTemplate:
        """Базовый шаблон для анализа жалоб"""
        return type('Template', (), {
            'system_prompt': 'Ты опытный врач. Проанализируй жалобы пациента и предложи план обследования.',
            'context_template': 'Специальность: {{ specialty }}\\nЯзык: {{ language }}',
            'task_template': 'Жалобы пациента: {{ complaints }}\\n\\nПроанализируй и предложи:\\n1. Возможные диагнозы\\n2. План обследования\\n3. Рекомендации',
            'examples': []
        })()

    def _get_default_icd10_template(self) -> AIPromptTemplate:
        """Базовый шаблон для МКБ-10"""
        return type('Template', (), {
            'system_prompt': 'Ты эксперт по МКБ-10. Найди подходящие коды для диагноза.',
            'context_template': 'Специальность: {{ specialty }}\\nЯзык: {{ language }}',
            'task_template': 'Диагноз: {{ diagnosis }}\\n\\nНайди подходящие коды МКБ-10 с описанием.',
            'examples': []
        })()

    def _get_default_document_template(self) -> AIPromptTemplate:
        """Базовый шаблон для анализа документов"""
        return type('Template', (), {
            'system_prompt': 'Ты медицинский ассистент. Проанализируй медицинский документ и извлеки ключевую информацию.',
            'context_template': 'Тип документа: {{ document_type }}\\nСпециальность: {{ specialty }}',
            'task_template': 'Текст документа:\\n{{ document_text }}\\n\\nИзвлеки:\\n1. Диагнозы\\n2. Назначения\\n3. Рекомендации\\n4. Ключевые показатели',
            'examples': []
        })()

    def _parse_complaints_response(self, response: str) -> Dict[str, Any]:
        """Парсинг ответа анализа жалоб"""
        try:
            # Пробуем парсить как JSON
            return json.loads(response)
        except:
            # Если не JSON, возвращаем как текст
            return {
                "analysis_text": response,
                "possible_diagnoses": [],
                "examination_plan": [],
                "recommendations": []
            }

    def _parse_icd10_response(self, response: str) -> List[Dict[str, Any]]:
        """Парсинг ответа подбора МКБ-10"""
        try:
            # Пробуем парсить как JSON
            data = json.loads(response)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "codes" in data:
                return data["codes"]
            else:
                return [{"code": "Z00.0", "description": response}]
        except:
            # Если не JSON, возвращаем базовый результат
            return [
                {
                    "code": "Z00.0",
                    "description": "Общее медицинское обследование",
                    "ai_suggestion": response
                }
            ]

    def _parse_document_response(self, response: str) -> Dict[str, Any]:
        """Парсинг ответа анализа документов"""
        try:
            return json.loads(response)
        except:
            return {
                "summary": response,
                "diagnoses": [],
                "prescriptions": [],
                "recommendations": [],
                "key_findings": []
            }

    def _log_ai_usage(
        self,
        provider_id: int,
        task_type: str,
        prompt: str,
        response: str,
        input_tokens: int
    ):
        """Логирование использования AI"""
        try:
            log_data = {
                "provider_id": provider_id,
                "task_type": task_type,
                "input_text": prompt[:1000],  # Ограничиваем размер
                "output_text": response[:2000],
                "input_tokens": input_tokens,
                "output_tokens": len(response),
                "status": "completed",
                "response_time_ms": 1000  # Заглушка
            }
            
            crud_ai.create_usage_log(self.db, log_data)
            
        except Exception as e:
            print(f"Ошибка логирования AI: {e}")

# Глобальные функции для использования в API
async def get_ai_service(db: Session) -> AIService:
    """Получить экземпляр AI сервиса"""
    return AIService(db)
