"""
Сервис для работы с шаблонами EMR
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class EMRTemplateService:
    """Сервис для работы с шаблонами EMR"""

    @staticmethod
    def get_default_templates() -> List[Dict[str, Any]]:
        """Получить предустановленные шаблоны EMR"""
        return [
            EMRTemplateService._get_cardiology_template(),
            EMRTemplateService._get_dermatology_template(),
            EMRTemplateService._get_dentistry_template(),
            EMRTemplateService._get_general_template(),
        ]

    @staticmethod
    def _get_cardiology_template() -> Dict[str, Any]:
        """Шаблон для кардиологии"""
        return {
            "template_name": "Кардиологический осмотр",
            "description": "Стандартный шаблон для кардиологического приема",
            "specialty": "cardiology",
            "sections": [
                {
                    "section_name": "complaints",
                    "section_title": "Жалобы",
                    "order": 1,
                    "required": True,
                    "fields": [
                        {
                            "field_name": "chest_pain",
                            "field_type": "checkbox",
                            "label": "Боли в груди",
                            "order": 1,
                        },
                        {
                            "field_name": "shortness_of_breath",
                            "field_type": "checkbox",
                            "label": "Одышка",
                            "order": 2,
                        },
                        {
                            "field_name": "palpitations",
                            "field_type": "checkbox",
                            "label": "Сердцебиение",
                            "order": 3,
                        },
                        {
                            "field_name": "swelling",
                            "field_type": "checkbox",
                            "label": "Отеки",
                            "order": 4,
                        },
                        {
                            "field_name": "additional_complaints",
                            "field_type": "textarea",
                            "label": "Дополнительные жалобы",
                            "placeholder": "Опишите дополнительные жалобы...",
                            "order": 5,
                        },
                    ],
                },
                {
                    "section_name": "anamnesis",
                    "section_title": "Анамнез",
                    "order": 2,
                    "required": True,
                    "fields": [
                        {
                            "field_name": "previous_heart_attacks",
                            "field_type": "checkbox",
                            "label": "Инфаркты в анамнезе",
                            "order": 1,
                        },
                        {
                            "field_name": "hypertension",
                            "field_type": "checkbox",
                            "label": "Артериальная гипертензия",
                            "order": 2,
                        },
                        {
                            "field_name": "diabetes",
                            "field_type": "checkbox",
                            "label": "Сахарный диабет",
                            "order": 3,
                        },
                        {
                            "field_name": "family_history",
                            "field_type": "textarea",
                            "label": "Семейный анамнез",
                            "placeholder": "Сердечно-сосудистые заболевания у родственников...",
                            "order": 4,
                        },
                    ],
                },
                {
                    "section_name": "examination",
                    "section_title": "Объективный осмотр",
                    "order": 3,
                    "required": True,
                    "fields": [
                        {
                            "field_name": "blood_pressure",
                            "field_type": "text",
                            "label": "Артериальное давление",
                            "placeholder": "120/80",
                            "required": True,
                            "order": 1,
                        },
                        {
                            "field_name": "heart_rate",
                            "field_type": "text",
                            "label": "ЧСС",
                            "placeholder": "72",
                            "required": True,
                            "order": 2,
                        },
                        {
                            "field_name": "heart_sounds",
                            "field_type": "select",
                            "label": "Тоны сердца",
                            "options": ["Ясные", "Приглушенные", "Глухие", "Шумы"],
                            "order": 3,
                        },
                        {
                            "field_name": "ecg_findings",
                            "field_type": "textarea",
                            "label": "ЭКГ",
                            "placeholder": "Описание ЭКГ...",
                            "order": 4,
                        },
                        {
                            "field_name": "echo_findings",
                            "field_type": "textarea",
                            "label": "ЭхоКГ",
                            "placeholder": "Описание ЭхоКГ...",
                            "order": 5,
                        },
                    ],
                },
                {
                    "section_name": "diagnosis",
                    "section_title": "Диагноз",
                    "order": 4,
                    "required": True,
                    "fields": [
                        {
                            "field_name": "main_diagnosis",
                            "field_type": "textarea",
                            "label": "Основной диагноз",
                            "placeholder": "Основной диагноз...",
                            "required": True,
                            "order": 1,
                        },
                        {
                            "field_name": "icd10_code",
                            "field_type": "text",
                            "label": "Код МКБ-10",
                            "placeholder": "I25.9",
                            "order": 2,
                        },
                        {
                            "field_name": "comorbidities",
                            "field_type": "textarea",
                            "label": "Сопутствующие заболевания",
                            "placeholder": "Сопутствующие заболевания...",
                            "order": 3,
                        },
                    ],
                },
                {
                    "section_name": "recommendations",
                    "section_title": "Рекомендации",
                    "order": 5,
                    "required": True,
                    "fields": [
                        {
                            "field_name": "medications",
                            "field_type": "textarea",
                            "label": "Медикаментозное лечение",
                            "placeholder": "Назначенные препараты...",
                            "order": 1,
                        },
                        {
                            "field_name": "lifestyle",
                            "field_type": "textarea",
                            "label": "Образ жизни",
                            "placeholder": "Рекомендации по образу жизни...",
                            "order": 2,
                        },
                        {
                            "field_name": "follow_up",
                            "field_type": "text",
                            "label": "Повторный прием",
                            "placeholder": "Через 3 месяца",
                            "order": 3,
                        },
                    ],
                },
            ],
        }

    @staticmethod
    def _get_dermatology_template() -> Dict[str, Any]:
        """Шаблон для дерматологии"""
        return {
            "template_name": "Дерматологический осмотр",
            "description": "Стандартный шаблон для дерматологического приема",
            "specialty": "dermatology",
            "sections": [
                {
                    "section_name": "complaints",
                    "section_title": "Жалобы",
                    "order": 1,
                    "required": True,
                    "fields": [
                        {
                            "field_name": "skin_lesions",
                            "field_type": "checkbox",
                            "label": "Высыпания на коже",
                            "order": 1,
                        },
                        {
                            "field_name": "itching",
                            "field_type": "checkbox",
                            "label": "Зуд",
                            "order": 2,
                        },
                        {
                            "field_name": "pain",
                            "field_type": "checkbox",
                            "label": "Болезненность",
                            "order": 3,
                        },
                        {
                            "field_name": "additional_complaints",
                            "field_type": "textarea",
                            "label": "Дополнительные жалобы",
                            "placeholder": "Опишите дополнительные жалобы...",
                            "order": 4,
                        },
                    ],
                },
                {
                    "section_name": "examination",
                    "section_title": "Объективный осмотр",
                    "order": 2,
                    "required": True,
                    "fields": [
                        {
                            "field_name": "skin_condition",
                            "field_type": "textarea",
                            "label": "Состояние кожи",
                            "placeholder": "Описание состояния кожи...",
                            "required": True,
                            "order": 1,
                        },
                        {
                            "field_name": "lesion_location",
                            "field_type": "text",
                            "label": "Локализация высыпаний",
                            "placeholder": "Лицо, руки, туловище...",
                            "order": 2,
                        },
                        {
                            "field_name": "lesion_description",
                            "field_type": "textarea",
                            "label": "Описание высыпаний",
                            "placeholder": "Размер, цвет, форма, консистенция...",
                            "order": 3,
                        },
                        {
                            "field_name": "dermoscopy",
                            "field_type": "textarea",
                            "label": "Дерматоскопия",
                            "placeholder": "Результаты дерматоскопии...",
                            "order": 4,
                        },
                    ],
                },
                {
                    "section_name": "diagnosis",
                    "section_title": "Диагноз",
                    "order": 3,
                    "required": True,
                    "fields": [
                        {
                            "field_name": "main_diagnosis",
                            "field_type": "textarea",
                            "label": "Основной диагноз",
                            "placeholder": "Основной диагноз...",
                            "required": True,
                            "order": 1,
                        },
                        {
                            "field_name": "icd10_code",
                            "field_type": "text",
                            "label": "Код МКБ-10",
                            "placeholder": "L30.9",
                            "order": 2,
                        },
                    ],
                },
                {
                    "section_name": "recommendations",
                    "section_title": "Рекомендации",
                    "order": 4,
                    "required": True,
                    "fields": [
                        {
                            "field_name": "topical_treatment",
                            "field_type": "textarea",
                            "label": "Наружное лечение",
                            "placeholder": "Мази, кремы, лосьоны...",
                            "order": 1,
                        },
                        {
                            "field_name": "systemic_treatment",
                            "field_type": "textarea",
                            "label": "Системное лечение",
                            "placeholder": "Таблетки, инъекции...",
                            "order": 2,
                        },
                        {
                            "field_name": "skin_care",
                            "field_type": "textarea",
                            "label": "Уход за кожей",
                            "placeholder": "Рекомендации по уходу...",
                            "order": 3,
                        },
                    ],
                },
            ],
        }

    @staticmethod
    def _get_dentistry_template() -> Dict[str, Any]:
        """Шаблон для стоматологии"""
        return {
            "template_name": "Стоматологический осмотр",
            "description": "Стандартный шаблон для стоматологического приема",
            "specialty": "dentistry",
            "sections": [
                {
                    "section_name": "complaints",
                    "section_title": "Жалобы",
                    "order": 1,
                    "required": True,
                    "fields": [
                        {
                            "field_name": "tooth_pain",
                            "field_type": "checkbox",
                            "label": "Зубная боль",
                            "order": 1,
                        },
                        {
                            "field_name": "gum_bleeding",
                            "field_type": "checkbox",
                            "label": "Кровоточивость десен",
                            "order": 2,
                        },
                        {
                            "field_name": "bad_breath",
                            "field_type": "checkbox",
                            "label": "Неприятный запах изо рта",
                            "order": 3,
                        },
                        {
                            "field_name": "additional_complaints",
                            "field_type": "textarea",
                            "label": "Дополнительные жалобы",
                            "placeholder": "Опишите дополнительные жалобы...",
                            "order": 4,
                        },
                    ],
                },
                {
                    "section_name": "examination",
                    "section_title": "Объективный осмотр",
                    "order": 2,
                    "required": True,
                    "fields": [
                        {
                            "field_name": "oral_hygiene",
                            "field_type": "select",
                            "label": "Гигиена полости рта",
                            "options": ["Хорошая", "Удовлетворительная", "Плохая"],
                            "order": 1,
                        },
                        {
                            "field_name": "gum_condition",
                            "field_type": "textarea",
                            "label": "Состояние десен",
                            "placeholder": "Описание состояния десен...",
                            "order": 2,
                        },
                        {
                            "field_name": "tooth_condition",
                            "field_type": "textarea",
                            "label": "Состояние зубов",
                            "placeholder": "Описание состояния зубов...",
                            "order": 3,
                        },
                        {
                            "field_name": "xray_findings",
                            "field_type": "textarea",
                            "label": "Рентгенография",
                            "placeholder": "Результаты рентгенографии...",
                            "order": 4,
                        },
                    ],
                },
                {
                    "section_name": "diagnosis",
                    "section_title": "Диагноз",
                    "order": 3,
                    "required": True,
                    "fields": [
                        {
                            "field_name": "main_diagnosis",
                            "field_type": "textarea",
                            "label": "Основной диагноз",
                            "placeholder": "Основной диагноз...",
                            "required": True,
                            "order": 1,
                        },
                        {
                            "field_name": "icd10_code",
                            "field_type": "text",
                            "label": "Код МКБ-10",
                            "placeholder": "K02.9",
                            "order": 2,
                        },
                    ],
                },
                {
                    "section_name": "treatment",
                    "section_title": "Лечение",
                    "order": 4,
                    "required": True,
                    "fields": [
                        {
                            "field_name": "procedures_performed",
                            "field_type": "textarea",
                            "label": "Выполненные процедуры",
                            "placeholder": "Список выполненных процедур...",
                            "order": 1,
                        },
                        {
                            "field_name": "recommendations",
                            "field_type": "textarea",
                            "label": "Рекомендации",
                            "placeholder": "Рекомендации по уходу...",
                            "order": 2,
                        },
                        {
                            "field_name": "follow_up",
                            "field_type": "text",
                            "label": "Повторный прием",
                            "placeholder": "Через 6 месяцев",
                            "order": 3,
                        },
                    ],
                },
            ],
        }

    @staticmethod
    def _get_general_template() -> Dict[str, Any]:
        """Общий шаблон EMR"""
        return {
            "template_name": "Общий медицинский осмотр",
            "description": "Универсальный шаблон для медицинского приема",
            "specialty": "general",
            "sections": [
                {
                    "section_name": "complaints",
                    "section_title": "Жалобы",
                    "order": 1,
                    "required": True,
                    "fields": [
                        {
                            "field_name": "main_complaint",
                            "field_type": "textarea",
                            "label": "Основная жалоба",
                            "placeholder": "Опишите основную жалобу...",
                            "required": True,
                            "order": 1,
                        },
                        {
                            "field_name": "additional_complaints",
                            "field_type": "textarea",
                            "label": "Дополнительные жалобы",
                            "placeholder": "Дополнительные жалобы...",
                            "order": 2,
                        },
                    ],
                },
                {
                    "section_name": "anamnesis",
                    "section_title": "Анамнез",
                    "order": 2,
                    "required": True,
                    "fields": [
                        {
                            "field_name": "medical_history",
                            "field_type": "textarea",
                            "label": "Медицинский анамнез",
                            "placeholder": "Перенесенные заболевания...",
                            "order": 1,
                        },
                        {
                            "field_name": "allergies",
                            "field_type": "textarea",
                            "label": "Аллергии",
                            "placeholder": "Аллергические реакции...",
                            "order": 2,
                        },
                        {
                            "field_name": "medications",
                            "field_type": "textarea",
                            "label": "Принимаемые препараты",
                            "placeholder": "Список принимаемых препаратов...",
                            "order": 3,
                        },
                    ],
                },
                {
                    "section_name": "examination",
                    "section_title": "Объективный осмотр",
                    "order": 3,
                    "required": True,
                    "fields": [
                        {
                            "field_name": "vital_signs",
                            "field_type": "textarea",
                            "label": "Жизненные показатели",
                            "placeholder": "АД, ЧСС, температура, дыхание...",
                            "order": 1,
                        },
                        {
                            "field_name": "physical_examination",
                            "field_type": "textarea",
                            "label": "Физикальный осмотр",
                            "placeholder": "Результаты осмотра...",
                            "order": 2,
                        },
                    ],
                },
                {
                    "section_name": "diagnosis",
                    "section_title": "Диагноз",
                    "order": 4,
                    "required": True,
                    "fields": [
                        {
                            "field_name": "main_diagnosis",
                            "field_type": "textarea",
                            "label": "Основной диагноз",
                            "placeholder": "Основной диагноз...",
                            "required": True,
                            "order": 1,
                        },
                        {
                            "field_name": "icd10_code",
                            "field_type": "text",
                            "label": "Код МКБ-10",
                            "placeholder": "Z00.0",
                            "order": 2,
                        },
                    ],
                },
                {
                    "section_name": "recommendations",
                    "section_title": "Рекомендации",
                    "order": 5,
                    "required": True,
                    "fields": [
                        {
                            "field_name": "treatment",
                            "field_type": "textarea",
                            "label": "Лечение",
                            "placeholder": "Назначенное лечение...",
                            "order": 1,
                        },
                        {
                            "field_name": "follow_up",
                            "field_type": "text",
                            "label": "Повторный прием",
                            "placeholder": "Дата повторного приема...",
                            "order": 2,
                        },
                    ],
                },
            ],
        }

    @staticmethod
    def create_template_from_structure(structure: Dict[str, Any]) -> Dict[str, Any]:
        """Создать шаблон из структуры"""
        return {
            "name": structure.get("template_name", "Новый шаблон"),
            "description": structure.get("description", ""),
            "specialty": structure.get("specialty", "general"),
            "template_structure": structure,
            "is_active": True,
            "is_public": True,
        }
