"""
AI сервис для EMR - подсказки и автозаполнение
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class EMRService:
    """AI сервис для работы с EMR"""

    def __init__(self):
        self.ai_providers = {
            "openai": "gpt-3.5-turbo",
            "anthropic": "claude-3-sonnet",
            "local": "llama-3",
        }

    async def get_diagnosis_suggestions(
        self, symptoms: List[str], specialty: str = "general"
    ) -> List[Dict[str, Any]]:
        """Получить предложения диагнозов на основе симптомов"""
        try:
            # Формируем промпт для AI
            prompt = self._build_diagnosis_prompt(symptoms, specialty)

            # Здесь будет вызов AI API
            # Пока возвращаем заглушку
            suggestions = [
                {
                    "diagnosis": "Острый респираторный вирус",
                    "icd10": "J06.9",
                    "confidence": 0.85,
                    "description": "Острое респираторное заболевание вирусной этиологии",
                },
                {
                    "diagnosis": "Острый бронхит",
                    "icd10": "J20.9",
                    "confidence": 0.72,
                    "description": "Острое воспаление бронхов",
                },
            ]

            return suggestions

        except Exception as e:
            logger.error(f"Ошибка получения предложений диагнозов: {e}")
            return []

    async def get_treatment_suggestions(
        self, diagnosis: str, specialty: str = "general"
    ) -> List[Dict[str, Any]]:
        """Получить предложения лечения на основе диагноза"""
        try:
            prompt = self._build_treatment_prompt(diagnosis, specialty)

            # Заглушка для предложений лечения
            suggestions = [
                {
                    "medication": "Парацетамол 500мг",
                    "dosage": "1 таблетка 3 раза в день",
                    "duration": "5-7 дней",
                    "instructions": "Принимать после еды",
                },
                {
                    "medication": "Ибупрофен 400мг",
                    "dosage": "1 таблетка 2 раза в день",
                    "duration": "3-5 дней",
                    "instructions": "Принимать с едой",
                },
            ]

            return suggestions

        except Exception as e:
            logger.error(f"Ошибка получения предложений лечения: {e}")
            return []

    async def get_icd10_suggestions(self, diagnosis_text: str) -> List[Dict[str, Any]]:
        """Получить предложения кодов МКБ-10"""
        try:
            # Заглушка для кодов МКБ-10
            suggestions = [
                {
                    "code": "J06.9",
                    "description": "Острая инфекция верхних дыхательных путей неуточненная",
                    "category": "Болезни органов дыхания",
                },
                {
                    "code": "J20.9",
                    "description": "Острый бронхит неуточненный",
                    "category": "Болезни органов дыхания",
                },
            ]

            return suggestions

        except Exception as e:
            logger.error(f"Ошибка получения кодов МКБ-10: {e}")
            return []

    async def auto_fill_emr_fields(
        self,
        template_structure: Dict[str, Any],
        patient_data: Dict[str, Any],
        specialty: str = "general",
    ) -> Dict[str, Any]:
        """Автозаполнение полей EMR на основе данных пациента"""
        try:
            filled_data = {}

            # Анализируем структуру шаблона
            for section in template_structure.get("sections", []):
                section_name = section["section_name"]
                filled_data[section_name] = {}

                for field in section.get("fields", []):
                    field_name = field["field_name"]
                    field_type = field["field_type"]

                    # Автозаполнение на основе типа поля
                    if field_type == "checkbox":
                        filled_data[section_name][field_name] = False
                    elif field_type == "text":
                        filled_data[section_name][field_name] = ""
                    elif field_type == "textarea":
                        filled_data[section_name][field_name] = ""
                    elif field_type == "select":
                        filled_data[section_name][field_name] = field.get(
                            "options", [""]
                        )[0]
                    elif field_type == "date":
                        filled_data[section_name][field_name] = datetime.now().strftime(
                            "%Y-%m-%d"
                        )

            return filled_data

        except Exception as e:
            logger.error(f"Ошибка автозаполнения EMR: {e}")
            return {}

    async def validate_emr_data(
        self, emr_data: Dict[str, Any], template_structure: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Валидация данных EMR"""
        try:
            validation_result = {
                "is_valid": True,
                "errors": [],
                "warnings": [],
                "suggestions": [],
            }

            # Проверяем обязательные поля
            for section in template_structure.get("sections", []):
                if section.get("required", False):
                    section_name = section["section_name"]
                    if section_name not in emr_data:
                        validation_result["errors"].append(
                            f"Отсутствует обязательная секция: {section['section_title']}"
                        )
                        validation_result["is_valid"] = False
                    else:
                        for field in section.get("fields", []):
                            if field.get("required", False):
                                field_name = field["field_name"]
                                if field_name not in emr_data[section_name]:
                                    validation_result["errors"].append(
                                        f"Отсутствует обязательное поле: {field['label']}"
                                    )
                                    validation_result["is_valid"] = False

            # Проверяем коды МКБ-10
            if "diagnosis" in emr_data:
                diagnosis_section = emr_data.get("diagnosis", {})
                if "icd10_code" in diagnosis_section:
                    icd10_code = diagnosis_section["icd10_code"]
                    if icd10_code and not self._validate_icd10_code(icd10_code):
                        validation_result["warnings"].append(
                            "Код МКБ-10 может быть некорректным"
                        )

            return validation_result

        except Exception as e:
            logger.error(f"Ошибка валидации EMR: {e}")
            return {
                "is_valid": False,
                "errors": [f"Ошибка валидации: {str(e)}"],
                "warnings": [],
                "suggestions": [],
            }

    def _build_diagnosis_prompt(self, symptoms: List[str], specialty: str) -> str:
        """Построить промпт для получения диагнозов"""
        symptoms_text = ", ".join(symptoms)

        prompt = f"""
        На основе следующих симптомов предложите возможные диагнозы:
        
        Симптомы: {symptoms_text}
        Специализация: {specialty}
        
        Предоставьте:
        1. Наиболее вероятный диагноз
        2. Код МКБ-10
        3. Уровень уверенности (0-1)
        4. Краткое описание
        
        Ответ в формате JSON.
        """

        return prompt

    def _build_treatment_prompt(self, diagnosis: str, specialty: str) -> str:
        """Построить промпт для получения лечения"""
        prompt = f"""
        Предложите план лечения для следующего диагноза:
        
        Диагноз: {diagnosis}
        Специализация: {specialty}
        
        Предоставьте:
        1. Медикаментозное лечение
        2. Дозировки
        3. Продолжительность
        4. Инструкции по применению
        
        Ответ в формате JSON.
        """

        return prompt

    def _validate_icd10_code(self, code: str) -> bool:
        """Валидация кода МКБ-10"""
        # Простая валидация формата МКБ-10
        if not code:
            return False

        # МКБ-10 коды обычно имеют формат: буква + 2-3 цифры + точка + 1-2 цифры
        import re

        pattern = r'^[A-Z]\d{2,3}(\.\d{1,2})?$'
        return bool(re.match(pattern, code))

    async def get_ai_suggestions(
        self, emr_data: Dict[str, Any], specialty: str = "general"
    ) -> Dict[str, Any]:
        """Получить общие AI предложения для EMR"""
        try:
            suggestions = {
                "diagnosis": [],
                "treatment": [],
                "icd10": [],
                "warnings": [],
                "improvements": [],
            }

            # Анализируем жалобы для предложения диагнозов
            if "complaints" in emr_data:
                complaints_section = emr_data["complaints"]
                symptoms = []

                for field_name, value in complaints_section.items():
                    if isinstance(value, bool) and value:
                        symptoms.append(field_name)
                    elif isinstance(value, str) and value.strip():
                        symptoms.append(value.strip())

                if symptoms:
                    diagnosis_suggestions = await self.get_diagnosis_suggestions(
                        symptoms, specialty
                    )
                    suggestions["diagnosis"] = diagnosis_suggestions

            # Анализируем диагноз для предложения лечения
            if "diagnosis" in emr_data:
                diagnosis_section = emr_data["diagnosis"]
                main_diagnosis = diagnosis_section.get("main_diagnosis", "")

                if main_diagnosis:
                    treatment_suggestions = await self.get_treatment_suggestions(
                        main_diagnosis, specialty
                    )
                    suggestions["treatment"] = treatment_suggestions

                    icd10_suggestions = await self.get_icd10_suggestions(main_diagnosis)
                    suggestions["icd10"] = icd10_suggestions

            return suggestions

        except Exception as e:
            logger.error(f"Ошибка получения AI предложений: {e}")
            return {
                "diagnosis": [],
                "treatment": [],
                "icd10": [],
                "warnings": [],
                "improvements": [],
            }


# Глобальный экземпляр сервиса
emr_ai_service = EMRService()


async def get_emr_ai_service() -> EMRService:
    """Получить экземпляр AI сервиса для EMR"""
    return emr_ai_service
