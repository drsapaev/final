"""
Расширенный AI сервис для EMR - умные подсказки и автозаполнение
"""
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)


class EMREnhancedAIService:
    """Расширенный AI сервис для работы с EMR"""

    def __init__(self):
        self.ai_providers = {
            "openai": "gpt-4",
            "anthropic": "claude-3-sonnet",
            "local": "llama-3"
        }
        self.specialty_templates = {
            "cardiology": self._get_cardiology_template(),
            "dermatology": self._get_dermatology_template(),
            "dentistry": self._get_dentistry_template(),
            "general": self._get_general_template()
        }

    async def generate_smart_template(
        self,
        specialty: str,
        patient_data: Dict[str, Any],
        doctor_preferences: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Генерация умного шаблона на основе данных пациента и предпочтений врача"""
        try:
            # Получаем базовый шаблон для специализации
            base_template = self.specialty_templates.get(specialty, self.specialty_templates["general"])
            
            # Анализируем данные пациента
            patient_analysis = await self._analyze_patient_data(patient_data)
            
            # Генерируем персонализированный шаблон
            personalized_template = await self._personalize_template(
                base_template, patient_analysis, doctor_preferences
            )
            
            return personalized_template
            
        except Exception as e:
            logger.error(f"Ошибка генерации умного шаблона: {e}")
            return self.specialty_templates.get(specialty, self.specialty_templates["general"])

    async def get_smart_suggestions(
        self,
        current_data: Dict[str, Any],
        field_name: str,
        specialty: str = "general"
    ) -> List[Dict[str, Any]]:
        """Получить умные подсказки для конкретного поля"""
        try:
            suggestions = []
            
            if field_name == "complaints":
                suggestions = await self._get_complaint_suggestions(current_data, specialty)
            elif field_name == "diagnosis":
                suggestions = await self._get_diagnosis_suggestions(current_data, specialty)
            elif field_name == "treatment":
                suggestions = await self._get_treatment_suggestions(current_data, specialty)
            elif field_name == "medications":
                suggestions = await self._get_medication_suggestions(current_data, specialty)
            elif field_name == "procedures":
                suggestions = await self._get_procedure_suggestions(current_data, specialty)
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Ошибка получения умных подсказок: {e}")
            return []

    async def auto_fill_emr_fields(
        self,
        template_structure: Dict[str, Any],
        patient_data: Dict[str, Any],
        specialty: str = "general"
    ) -> Dict[str, Any]:
        """Автоматическое заполнение полей EMR на основе данных пациента"""
        try:
            filled_data = {}
            
            # Анализируем данные пациента
            patient_analysis = await self._analyze_patient_data(patient_data)
            
            # Заполняем поля на основе анализа
            for field_name, field_config in template_structure.items():
                if field_config.get("auto_fill", False):
                    filled_data[field_name] = await self._fill_field(
                        field_name, field_config, patient_analysis, specialty
                    )
            
            return filled_data
            
        except Exception as e:
            logger.error(f"Ошибка автозаполнения полей: {e}")
            return {}

    async def validate_emr_data(
        self,
        emr_data: Dict[str, Any],
        specialty: str = "general"
    ) -> Dict[str, Any]:
        """Валидация данных EMR с AI подсказками"""
        try:
            validation_result = {
                "is_valid": True,
                "errors": [],
                "warnings": [],
                "suggestions": []
            }
            
            # Проверяем обязательные поля
            required_fields = self._get_required_fields(specialty)
            for field in required_fields:
                if not emr_data.get(field):
                    validation_result["errors"].append(f"Обязательное поле '{field}' не заполнено")
                    validation_result["is_valid"] = False
            
            # Проверяем логическую целостность
            logic_issues = await self._check_logic_consistency(emr_data, specialty)
            validation_result["warnings"].extend(logic_issues)
            
            # Генерируем предложения по улучшению
            suggestions = await self._generate_improvement_suggestions(emr_data, specialty)
            validation_result["suggestions"].extend(suggestions)
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Ошибка валидации EMR: {e}")
            return {"is_valid": False, "errors": [f"Ошибка валидации: {str(e)}"]}

    async def generate_icd10_suggestions(
        self,
        diagnosis_text: str,
        specialty: str = "general"
    ) -> List[Dict[str, Any]]:
        """Генерация предложений ICD-10 кодов"""
        try:
            # Здесь будет интеграция с реальным AI API
            # Пока возвращаем заглушку с умными предложениями
            suggestions = []
            
            if "сердце" in diagnosis_text.lower() or "cardiac" in diagnosis_text.lower():
                suggestions.extend([
                    {"code": "I25.9", "description": "Хроническая ишемическая болезнь сердца неуточненная", "confidence": 0.9},
                    {"code": "I21.9", "description": "Острый инфаркт миокарда неуточненный", "confidence": 0.8}
                ])
            elif "кожа" in diagnosis_text.lower() or "dermat" in diagnosis_text.lower():
                suggestions.extend([
                    {"code": "L30.9", "description": "Дерматит неуточненный", "confidence": 0.85},
                    {"code": "L70.9", "description": "Угри неуточненные", "confidence": 0.8}
                ])
            elif "зуб" in diagnosis_text.lower() or "dental" in diagnosis_text.lower():
                suggestions.extend([
                    {"code": "K02.9", "description": "Кариес зубов неуточненный", "confidence": 0.9},
                    {"code": "K05.0", "description": "Острый гингивит", "confidence": 0.8}
                ])
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Ошибка генерации ICD-10 предложений: {e}")
            return []

    async def _analyze_patient_data(self, patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """Анализ данных пациента для персонализации"""
        analysis = {
            "age_group": self._get_age_group(patient_data.get("age", 0)),
            "gender": patient_data.get("gender", "unknown"),
            "medical_history": patient_data.get("medical_history", []),
            "allergies": patient_data.get("allergies", []),
            "current_medications": patient_data.get("current_medications", []),
            "risk_factors": self._identify_risk_factors(patient_data)
        }
        return analysis

    async def _personalize_template(
        self,
        base_template: Dict[str, Any],
        patient_analysis: Dict[str, Any],
        doctor_preferences: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Персонализация шаблона на основе анализа пациента"""
        personalized = base_template.copy()
        
        # Адаптируем поля в зависимости от возраста
        if patient_analysis["age_group"] == "pediatric":
            personalized = self._adapt_for_pediatric(personalized)
        elif patient_analysis["age_group"] == "elderly":
            personalized = self._adapt_for_elderly(personalized)
        
        # Добавляем поля для аллергий если есть
        if patient_analysis["allergies"]:
            personalized["allergies"] = {
                "type": "textarea",
                "label": "Аллергии",
                "required": True,
                "auto_fill": True
            }
        
        return personalized

    async def _get_complaint_suggestions(
        self,
        current_data: Dict[str, Any],
        specialty: str
    ) -> List[Dict[str, Any]]:
        """Получить подсказки для жалоб"""
        suggestions = []
        
        if specialty == "cardiology":
            suggestions = [
                {"text": "Боль в груди", "confidence": 0.9, "category": "symptom"},
                {"text": "Одышка", "confidence": 0.8, "category": "symptom"},
                {"text": "Сердцебиение", "confidence": 0.7, "category": "symptom"}
            ]
        elif specialty == "dermatology":
            suggestions = [
                {"text": "Сыпь на коже", "confidence": 0.9, "category": "symptom"},
                {"text": "Зуд", "confidence": 0.8, "category": "symptom"},
                {"text": "Покраснение", "confidence": 0.7, "category": "symptom"}
            ]
        
        return suggestions

    async def _get_diagnosis_suggestions(
        self,
        current_data: Dict[str, Any],
        specialty: str
    ) -> List[Dict[str, Any]]:
        """Получить подсказки для диагнозов"""
        suggestions = []
        
        complaints = current_data.get("complaints", "").lower()
        
        if specialty == "cardiology":
            if "боль" in complaints and "груд" in complaints:
                suggestions.append({
                    "diagnosis": "Стенокардия напряжения",
                    "icd10": "I20.9",
                    "confidence": 0.8
                })
        elif specialty == "dermatology":
            if "сыпь" in complaints:
                suggestions.append({
                    "diagnosis": "Аллергический дерматит",
                    "icd10": "L23.9",
                    "confidence": 0.7
                })
        
        return suggestions

    async def _get_treatment_suggestions(
        self,
        current_data: Dict[str, Any],
        specialty: str
    ) -> List[Dict[str, Any]]:
        """Получить подсказки для лечения"""
        suggestions = []
        
        diagnosis = current_data.get("diagnosis", "").lower()
        
        if "стенокардия" in diagnosis:
            suggestions.append({
                "treatment": "Нитроглицерин 0.5 мг под язык",
                "type": "medication",
                "confidence": 0.9
            })
        elif "дерматит" in diagnosis:
            suggestions.append({
                "treatment": "Антигистаминные препараты",
                "type": "medication",
                "confidence": 0.8
            })
        
        return suggestions

    async def _get_medication_suggestions(
        self,
        current_data: Dict[str, Any],
        specialty: str
    ) -> List[Dict[str, Any]]:
        """Получить подсказки для лекарств"""
        suggestions = []
        
        if specialty == "cardiology":
            suggestions = [
                {"name": "Аспирин", "dosage": "75-100 мг", "frequency": "1 раз в день"},
                {"name": "Аторвастатин", "dosage": "20-40 мг", "frequency": "1 раз в день"}
            ]
        
        return suggestions

    async def _get_procedure_suggestions(
        self,
        current_data: Dict[str, Any],
        specialty: str
    ) -> List[Dict[str, Any]]:
        """Получить подсказки для процедур"""
        suggestions = []
        
        if specialty == "cardiology":
            suggestions = [
                {"name": "ЭКГ", "description": "Электрокардиография", "required": True},
                {"name": "ЭхоКГ", "description": "Эхокардиография", "required": False}
            ]
        
        return suggestions

    def _get_cardiology_template(self) -> Dict[str, Any]:
        """Шаблон для кардиологии"""
        return {
            "complaints": {
                "type": "textarea",
                "label": "Жалобы",
                "required": True,
                "auto_fill": True,
                "ai_suggestions": True
            },
            "anamnesis": {
                "type": "textarea",
                "label": "Анамнез",
                "required": True,
                "auto_fill": True
            },
            "examination": {
                "type": "textarea",
                "label": "Объективное обследование",
                "required": True
            },
            "diagnosis": {
                "type": "textarea",
                "label": "Диагноз",
                "required": True,
                "ai_suggestions": True
            },
            "icd10": {
                "type": "text",
                "label": "Код МКБ-10",
                "required": True,
                "ai_suggestions": True
            },
            "recommendations": {
                "type": "textarea",
                "label": "Рекомендации",
                "required": True
            },
            "procedures": {
                "type": "checkbox_group",
                "label": "Назначенные процедуры",
                "options": ["ЭКГ", "ЭхоКГ", "Холтер", "Стресс-тест"],
                "required": False
            }
        }

    def _get_dermatology_template(self) -> Dict[str, Any]:
        """Шаблон для дерматологии"""
        return {
            "complaints": {
                "type": "textarea",
                "label": "Жалобы",
                "required": True,
                "auto_fill": True
            },
            "examination": {
                "type": "textarea",
                "label": "Осмотр кожи",
                "required": True
            },
            "diagnosis": {
                "type": "textarea",
                "label": "Диагноз",
                "required": True,
                "ai_suggestions": True
            },
            "treatment": {
                "type": "textarea",
                "label": "Лечение",
                "required": True
            },
            "follow_up": {
                "type": "date",
                "label": "Дата повторного приема",
                "required": False
            }
        }

    def _get_dentistry_template(self) -> Dict[str, Any]:
        """Шаблон для стоматологии"""
        return {
            "complaints": {
                "type": "textarea",
                "label": "Жалобы",
                "required": True
            },
            "examination": {
                "type": "textarea",
                "label": "Осмотр полости рта",
                "required": True
            },
            "diagnosis": {
                "type": "textarea",
                "label": "Диагноз",
                "required": True
            },
            "treatment_plan": {
                "type": "textarea",
                "label": "План лечения",
                "required": True
            },
            "procedures": {
                "type": "checkbox_group",
                "label": "Выполненные процедуры",
                "options": ["Пломбирование", "Удаление", "Чистка", "Рентген"],
                "required": False
            }
        }

    def _get_general_template(self) -> Dict[str, Any]:
        """Общий шаблон"""
        return {
            "complaints": {
                "type": "textarea",
                "label": "Жалобы",
                "required": True
            },
            "anamnesis": {
                "type": "textarea",
                "label": "Анамнез",
                "required": True
            },
            "examination": {
                "type": "textarea",
                "label": "Объективное обследование",
                "required": True
            },
            "diagnosis": {
                "type": "textarea",
                "label": "Диагноз",
                "required": True
            },
            "recommendations": {
                "type": "textarea",
                "label": "Рекомендации",
                "required": True
            }
        }

    def _get_age_group(self, age: int) -> str:
        """Определить возрастную группу"""
        if age < 18:
            return "pediatric"
        elif age > 65:
            return "elderly"
        else:
            return "adult"

    def _identify_risk_factors(self, patient_data: Dict[str, Any]) -> List[str]:
        """Идентифицировать факторы риска"""
        risk_factors = []
        
        if patient_data.get("smoking"):
            risk_factors.append("smoking")
        if patient_data.get("diabetes"):
            risk_factors.append("diabetes")
        if patient_data.get("hypertension"):
            risk_factors.append("hypertension")
        
        return risk_factors

    def _adapt_for_pediatric(self, template: Dict[str, Any]) -> Dict[str, Any]:
        """Адаптировать шаблон для педиатрии"""
        adapted = template.copy()
        adapted["growth_development"] = {
            "type": "textarea",
            "label": "Физическое развитие",
            "required": True
        }
        return adapted

    def _adapt_for_elderly(self, template: Dict[str, Any]) -> Dict[str, Any]:
        """Адаптировать шаблон для пожилых"""
        adapted = template.copy()
        adapted["cognitive_status"] = {
            "type": "textarea",
            "label": "Когнитивный статус",
            "required": False
        }
        return adapted

    def _get_required_fields(self, specialty: str) -> List[str]:
        """Получить обязательные поля для специализации"""
        base_fields = ["complaints", "diagnosis"]
        
        if specialty == "cardiology":
            return base_fields + ["examination", "icd10"]
        elif specialty == "dermatology":
            return base_fields + ["examination", "treatment"]
        elif specialty == "dentistry":
            return base_fields + ["examination", "treatment_plan"]
        else:
            return base_fields + ["examination", "recommendations"]

    async def _check_logic_consistency(
        self,
        emr_data: Dict[str, Any],
        specialty: str
    ) -> List[str]:
        """Проверить логическую целостность данных"""
        warnings = []
        
        # Проверяем соответствие диагноза и симптомов
        diagnosis = emr_data.get("diagnosis", "").lower()
        complaints = emr_data.get("complaints", "").lower()
        
        if "стенокардия" in diagnosis and "боль" not in complaints:
            warnings.append("Диагноз 'стенокардия' обычно сопровождается болевыми ощущениями")
        
        return warnings

    async def _generate_improvement_suggestions(
        self,
        emr_data: Dict[str, Any],
        specialty: str
    ) -> List[str]:
        """Генерировать предложения по улучшению"""
        suggestions = []
        
        # Проверяем полноту данных
        if not emr_data.get("icd10") and specialty in ["cardiology", "dermatology"]:
            suggestions.append("Рекомендуется указать код МКБ-10 для лучшей классификации")
        
        if not emr_data.get("follow_up") and specialty == "dermatology":
            suggestions.append("Рекомендуется назначить дату повторного приема")
        
        return suggestions

    async def _fill_field(
        self,
        field_name: str,
        field_config: Dict[str, Any],
        patient_analysis: Dict[str, Any],
        specialty: str
    ) -> Any:
        """Заполнить конкретное поле на основе анализа пациента"""
        if field_name == "allergies" and patient_analysis.get("allergies"):
            return ", ".join(patient_analysis["allergies"])
        
        return None


# Создаем экземпляр сервиса
emr_ai_enhanced = EMREnhancedAIService()
