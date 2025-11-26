"""
MCP сервер для анализа жалоб пациентов
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
import json
import logging
from .base_server import BaseMCPServer, MCPTool, MCPResource
from ..ai.ai_manager import get_ai_manager, AIProviderType

logger = logging.getLogger(__name__)


class MedicalComplaintMCPServer(BaseMCPServer):
    """MCP сервер для анализа медицинских жалоб"""
    
    def __init__(self):
        super().__init__(name="medical-complaint-server", version="1.0.0")
        self.ai_manager = None
        self.complaint_templates = self._load_complaint_templates()
        self.validation_rules = self._load_validation_rules()
    
    async def initialize(self):
        """Инициализация сервера"""
        self.ai_manager = get_ai_manager()
        logger.info("Medical Complaint MCP Server initialized")
    
    async def shutdown(self):
        """Завершение работы сервера"""
        logger.info("Medical Complaint MCP Server shutting down")
    
    def _load_complaint_templates(self) -> Dict[str, List[str]]:
        """Загрузка шаблонов жалоб"""
        return {
            "cardiology": [
                "Боль в области сердца при физической нагрузке",
                "Одышка при подъеме по лестнице",
                "Учащенное сердцебиение в покое",
                "Отеки нижних конечностей к вечеру",
                "Головокружение и слабость"
            ],
            "dermatology": [
                "Высыпания на коже лица",
                "Зуд и покраснение кожи",
                "Изменение цвета и формы родинок",
                "Шелушение кожи головы",
                "Акне и воспаления"
            ],
            "dentistry": [
                "Острая зубная боль",
                "Кровоточивость десен при чистке",
                "Чувствительность зубов к холодному",
                "Неприятный запах изо рта",
                "Подвижность зубов"
            ],
            "gastroenterology": [
                "Боль в эпигастральной области",
                "Изжога после приема пищи",
                "Тошнота и рвота",
                "Нарушение стула",
                "Вздутие живота"
            ],
            "neurology": [
                "Головная боль в височной области",
                "Мигрень с аурой",
                "Головокружение при смене положения",
                "Онемение конечностей",
                "Нарушение сна"
            ]
        }
    
    def _load_validation_rules(self) -> Dict[str, Any]:
        """Загрузка правил валидации"""
        return {
            "min_length": 10,
            "max_length": 2000,
            "required_context": ["когда", "как долго", "что беспокоит"],
            "forbidden_terms": [],
            "warning_terms": ["суицид", "самоповреждение", "наркотики"]
        }
    
    @MCPTool(name="analyze_complaint", description="Анализ жалоб пациента с созданием плана обследования")
    async def analyze_complaint(
        self,
        complaint: str,
        patient_info: Optional[Dict[str, Any]] = None,
        provider: Optional[str] = None,
        urgency_assessment: bool = True
    ) -> Dict[str, Any]:
        """
        Анализ жалоб пациента
        
        Args:
            complaint: Текст жалоб пациента
            patient_info: Информация о пациенте (возраст, пол, анамнез)
            provider: AI провайдер для анализа
            urgency_assessment: Оценивать срочность
        
        Returns:
            Результат анализа с планом обследования
        """
        try:
            # Валидация жалоб
            validation_result = await self.validate_complaint(complaint)
            if not validation_result.get("valid", False):
                return {
                    "status": "error",
                    "error": validation_result.get("reason", "Invalid complaint"),
                    "suggestions": validation_result.get("suggestions", [])
                }
            
            # Определяем провайдер
            provider_type = None
            if provider:
                try:
                    provider_type = AIProviderType(provider.lower())
                except ValueError:
                    logger.warning(f"Invalid provider: {provider}, using default")
            
            # Анализ через AI менеджер
            result = await self.ai_manager.analyze_complaint(
                complaint=complaint,
                patient_info=patient_info,
                provider_type=provider_type
            )
            
            # Проверяем на ошибки и используем fallback на другие провайдеры
            if result.get("error"):
                error_msg = result.get("error", "").lower()
                logger.warning(f"Primary AI provider failed: {result.get('error')}")
                
                # Пробуем альтернативные провайдеры
                from ..ai.ai_manager import AIProviderType
                alternative_providers = [
                    AIProviderType.DEEPSEEK,
                    AIProviderType.GEMINI,
                    AIProviderType.MOCK
                ]
                
                # Убираем текущий провайдер из альтернатив
                if provider_type in alternative_providers:
                    alternative_providers.remove(provider_type)
                
                for alt_provider in alternative_providers:
                    try:
                        logger.info(f"Trying fallback to {alt_provider.value} provider")
                        result = await self.ai_manager.analyze_complaint(
                            complaint=complaint,
                            patient_info=patient_info,
                            provider_type=alt_provider
                        )
                        if not result.get("error"):
                            provider = f"{alt_provider.value} (fallback)"
                            logger.info(f"✅ Fallback to {alt_provider.value} successful")
                            break
                    except Exception as e:
                        logger.error(f"Fallback to {alt_provider.value} failed: {str(e)}")
                        continue
            
            # Добавляем метаданные
            enhanced_result = {
                "status": "success",
                "data": result,
                "metadata": {
                    "provider_used": provider or "default",
                    "timestamp": datetime.utcnow().isoformat(),
                    "complaint_length": len(complaint),
                    "validation_score": validation_result.get("confidence", 0)
                }
            }
            
            # Оценка срочности
            if urgency_assessment and not result.get("error"):
                urgency = self._assess_urgency(complaint, result)
                enhanced_result["data"]["urgency_level"] = urgency
            
            return enhanced_result
            
        except Exception as e:
            logger.error(f"Error analyzing complaint: {str(e)}")
            return {
                "status": "error",
                "error": f"Analysis failed: {str(e)}"
            }
    
    @MCPTool(name="validate_complaint", description="Валидация жалоб на корректность и полноту")
    async def validate_complaint(self, complaint: str) -> Dict[str, Any]:
        """
        Валидация жалоб пациента
        
        Args:
            complaint: Текст жалоб
        
        Returns:
            Результат валидации
        """
        rules = self.validation_rules
        suggestions = []
        confidence = 1.0
        
        # Проверка длины
        if len(complaint) < rules["min_length"]:
            return {
                "valid": False,
                "reason": f"Слишком короткое описание (минимум {rules['min_length']} символов)",
                "suggestions": ["Опишите симптомы более подробно", "Укажите когда началось", "Опишите характер боли"]
            }
        
        if len(complaint) > rules["max_length"]:
            return {
                "valid": False,
                "reason": f"Слишком длинное описание (максимум {rules['max_length']} символов)",
                "suggestions": ["Сократите описание до основных симптомов"]
            }
        
        # Проверка на запрещенные термины
        complaint_lower = complaint.lower()
        for term in rules.get("warning_terms", []):
            if term in complaint_lower:
                confidence *= 0.7
                suggestions.append(f"Обнаружен тревожный симптом: {term}. Рекомендуется срочная консультация")
        
        # Проверка на наличие контекста
        has_time_context = any(word in complaint_lower for word in ["дня", "недели", "месяца", "вчера", "сегодня"])
        has_location_context = any(word in complaint_lower for word in ["области", "слева", "справа", "голова", "живот", "спина"])
        
        if not has_time_context:
            confidence *= 0.9
            suggestions.append("Укажите, как давно беспокоят симптомы")
        
        if not has_location_context:
            confidence *= 0.9
            suggestions.append("Уточните локализацию симптомов")
        
        return {
            "valid": True,
            "confidence": round(confidence, 2),
            "suggestions": suggestions,
            "has_context": {
                "time": has_time_context,
                "location": has_location_context
            }
        }
    
    @MCPTool(name="suggest_questions", description="Предложить уточняющие вопросы по жалобам")
    async def suggest_questions(
        self,
        complaint: str,
        specialty: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Генерация уточняющих вопросов
        
        Args:
            complaint: Текст жалоб
            specialty: Специальность врача
        
        Returns:
            Список уточняющих вопросов
        """
        base_questions = [
            "Как давно беспокоят эти симптомы?",
            "Что провоцирует или усиливает симптомы?",
            "Что облегчает состояние?",
            "Есть ли сопутствующие симптомы?",
            "Принимаете ли вы какие-либо лекарства?"
        ]
        
        specialty_questions = {
            "cardiology": [
                "Связана ли боль с физической нагрузкой?",
                "Есть ли одышка в покое?",
                "Измеряли ли артериальное давление?"
            ],
            "dermatology": [
                "Есть ли зуд?",
                "Менялись ли средства ухода за кожей?",
                "Есть ли аллергия на что-либо?"
            ],
            "gastroenterology": [
                "Связаны ли симптомы с приемом пищи?",
                "Есть ли изменения веса?",
                "Характер стула?"
            ]
        }
        
        questions = base_questions.copy()
        if specialty and specialty in specialty_questions:
            questions.extend(specialty_questions[specialty])
        
        return {
            "questions": questions,
            "specialty": specialty,
            "total_count": len(questions)
        }
    
    @MCPResource(name="complaint_templates", description="Шаблоны жалоб по специальностям")
    async def get_complaint_templates(
        self,
        specialty: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Получение шаблонов жалоб
        
        Args:
            specialty: Фильтр по специальности
        
        Returns:
            Шаблоны жалоб
        """
        if specialty:
            templates = self.complaint_templates.get(specialty, [])
            return {
                "specialty": specialty,
                "templates": templates,
                "count": len(templates)
            }
        
        return {
            "templates": self.complaint_templates,
            "total_count": sum(len(t) for t in self.complaint_templates.values()),
            "specialties": list(self.complaint_templates.keys())
        }
    
    @MCPResource(name="urgency_levels", description="Уровни срочности медицинской помощи")
    async def get_urgency_levels(self) -> Dict[str, Any]:
        """Получение описания уровней срочности"""
        return {
            "levels": {
                "emergency": {
                    "name": "Экстренная",
                    "description": "Требуется немедленная медицинская помощь",
                    "max_wait_time": "0 минут",
                    "color": "red"
                },
                "urgent": {
                    "name": "Неотложная",
                    "description": "Требуется помощь в течение 2 часов",
                    "max_wait_time": "2 часа",
                    "color": "orange"
                },
                "scheduled": {
                    "name": "Плановая",
                    "description": "Плановый прием в течение нескольких дней",
                    "max_wait_time": "7 дней",
                    "color": "yellow"
                },
                "routine": {
                    "name": "Профилактическая",
                    "description": "Профилактический осмотр",
                    "max_wait_time": "30 дней",
                    "color": "green"
                }
            }
        }
    
    def _assess_urgency(self, complaint: str, analysis_result: Dict[str, Any]) -> str:
        """Оценка срочности на основе жалоб и анализа"""
        complaint_lower = complaint.lower()
        
        # Экстренные симптомы
        emergency_keywords = [
            "острая боль", "потеря сознания", "кровотечение",
            "удушье", "судороги", "паралич"
        ]
        
        # Неотложные симптомы
        urgent_keywords = [
            "высокая температура", "сильная боль", "рвота",
            "головокружение", "одышка"
        ]
        
        for keyword in emergency_keywords:
            if keyword in complaint_lower:
                return "emergency"
        
        for keyword in urgent_keywords:
            if keyword in complaint_lower:
                return "urgent"
        
        # Проверяем результат анализа
        if analysis_result.get("urgency") == "экстренно":
            return "emergency"
        elif analysis_result.get("urgency") == "неотложно":
            return "urgent"
        
        # Проверяем red flags
        if analysis_result.get("red_flags") and len(analysis_result["red_flags"]) > 0:
            return "urgent"
        
        return "scheduled"
