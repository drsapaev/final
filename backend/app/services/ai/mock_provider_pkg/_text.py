"""Text mixin for MockProvider.

Split from mock_provider.py.
"""
from __future__ import annotations

from app.services.ai.mock_provider_pkg._base import (
    MockProviderMixinBase,
    AIRequest,
    AIResponse,
    asyncio,
    logging,
    random,
    Any,
)


class TextMixin(MockProviderMixinBase):
    """Text methods for MockProvider."""

    async def transcribe_audio(
        self, audio_data: bytes, language: str = "ru", medical_context: bool = True
    ) -> dict[str, Any]:
        """Имитация транскрипции аудио в текст"""
        await asyncio.sleep(1.5)

        # Имитируем различные типы медицинских записей
        sample_texts = [
            "Пациент жалуется на головную боль, тошноту и головокружение в течение трех дней. При осмотре артериальное давление 160 на 95, пульс 88 ударов в минуту. Назначаю каптоприл 25 миллиграмм два раза в день.",
            "Больная поступила с жалобами на боли в правом подреберье, тошноту, рвоту. При пальпации живот мягкий, болезненный в правом подреберье. Симптом Мерфи положительный. Диагноз острый холецистит.",
            "Ребенок 5 лет, температура 38.5, кашель сухой, насморк. При аускультации дыхание везикулярное, хрипов нет. Диагноз ОРВИ. Назначено симптоматическое лечение.",
        ]

        # Выбираем случайный текст на основе размера аудио
        import hashlib

        audio_hash = hashlib.md5(audio_data[:100], usedforsecurity=False).hexdigest()
        text_index = int(audio_hash[:2], 16) % len(sample_texts)
        selected_text = sample_texts[text_index]

        return {
            "text": selected_text,
            "language": language,
            "duration": len(audio_data) / 16000,  # Примерная длительность
            "segments": [
                {
                    "start": 0.0,
                    "end": 5.2,
                    "text": selected_text[:50] + "...",
                    "confidence": 0.92,
                },
                {
                    "start": 5.2,
                    "end": 10.8,
                    "text": "..." + selected_text[50:100] + "...",
                    "confidence": 0.88,
                },
                {
                    "start": 10.8,
                    "end": 15.5,
                    "text": "..." + selected_text[100:],
                    "confidence": 0.91,
                },
            ],
            "confidence": 0.90,
            "medical_context": medical_context,
        }


    async def structure_medical_text(
        self, text: str, document_type: str
    ) -> dict[str, Any]:
        """Имитация структурирования медицинского текста"""
        await asyncio.sleep(2)

        # Базовая структура для разных типов документов
        if document_type == "consultation":
            structured_data = {
                "жалобы": "Головная боль, тошнота, головокружение",
                "анамнез": "Симптомы появились 3 дня назад",
                "объективный_осмотр": "АД 160/95, пульс 88 уд/мин",
                "диагноз": "Артериальная гипертензия",
                "лечение": "Каптоприл 25 мг 2 раза в день",
                "рекомендации": "Контроль АД, диета с ограничением соли",
            }
        elif document_type == "prescription":
            structured_data = {
                "препараты": "Каптоприл",
                "дозировка": "25 мг",
                "способ_применения": "внутрь",
                "длительность": "14 дней",
                "противопоказания": "беременность, ангионевротический отек",
            }
        else:
            structured_data = {
                "основная_информация": "Извлеченная из текста информация",
                "дополнительные_данные": "Дополнительная структурированная информация",
            }

        return {
            "document_type": document_type,
            "structured_data": structured_data,
            "extracted_entities": {
                "medications": ["каптоприл"],
                "diagnoses": ["артериальная гипертензия"],
                "symptoms": ["головная боль", "тошнота", "головокружение"],
                "procedures": ["измерение АД"],
                "dosages": ["25 мг"],
                "dates": ["3 дня назад"],
            },
            "completeness_score": 8,
            "missing_fields": ["аллергии", "семейный анамнез"],
            "confidence_scores": {"жалобы": 0.95, "диагноз": 0.88, "лечение": 0.92},
            "suggestions": [
                "Добавить информацию об аллергиях пациента",
                "Уточнить длительность симптомов",
                "Указать результаты дополнительных исследований",
            ],
            "quality_indicators": {
                "terminology_accuracy": "высокая",
                "clinical_coherence": "высокая",
                "documentation_standards": "соответствует",
            },
        }


    async def extract_medical_entities(self, text: str) -> dict[str, Any]:
        """Имитация извлечения медицинских сущностей"""
        await asyncio.sleep(1.5)

        return {
            "medications": [
                {
                    "name": "каптоприл",
                    "dosage": "25 мг",
                    "frequency": "2 раза в день",
                    "route": "внутрь",
                    "duration": "14 дней",
                    "confidence": 0.95,
                }
            ],
            "diagnoses": [
                {
                    "name": "артериальная гипертензия",
                    "icd_code": "I10",
                    "type": "основной",
                    "confidence": 0.90,
                }
            ],
            "symptoms": [
                {
                    "name": "головная боль",
                    "severity": "умеренная",
                    "duration": "3 дня",
                    "frequency": "постоянная",
                    "confidence": 0.92,
                },
                {
                    "name": "тошнота",
                    "severity": "легкая",
                    "duration": "3 дня",
                    "frequency": "периодическая",
                    "confidence": 0.88,
                },
            ],
            "procedures": [
                {
                    "name": "измерение артериального давления",
                    "type": "диагностическая",
                    "date": "сегодня",
                    "result": "160/95 мм рт.ст.",
                    "confidence": 0.95,
                }
            ],
            "laboratory_tests": [
                {
                    "name": "общий анализ крови",
                    "value": "в пределах нормы",
                    "unit": "",
                    "reference_range": "норма",
                    "interpretation": "норма",
                    "confidence": 0.85,
                }
            ],
            "vital_signs": [
                {
                    "parameter": "артериальное давление",
                    "value": "160/95",
                    "unit": "мм рт.ст.",
                    "timestamp": "сегодня",
                    "confidence": 0.98,
                },
                {
                    "parameter": "пульс",
                    "value": "88",
                    "unit": "уд/мин",
                    "timestamp": "сегодня",
                    "confidence": 0.95,
                },
            ],
            "anatomical_locations": [
                {
                    "location": "голова",
                    "side": "двусторонний",
                    "specificity": "височная область",
                    "confidence": 0.87,
                }
            ],
            "temporal_expressions": [
                {
                    "expression": "3 дня назад",
                    "normalized_date": "2024-01-12",
                    "type": "относительная",
                    "confidence": 0.90,
                }
            ],
            "allergies": [
                {
                    "allergen": "пенициллин",
                    "reaction": "сыпь",
                    "severity": "умеренная",
                    "confidence": 0.85,
                }
            ],
            "family_history": [
                {
                    "condition": "гипертония",
                    "relation": "мать",
                    "age_of_onset": "50 лет",
                    "confidence": 0.80,
                }
            ],
            "social_history": [
                {
                    "factor": "курение",
                    "details": "10 сигарет в день",
                    "impact": "фактор риска сердечно-сосудистых заболеваний",
                    "confidence": 0.88,
                }
            ],
            "entity_relationships": [
                {
                    "entity1": "головная боль",
                    "relationship": "симптом",
                    "entity2": "артериальная гипертензия",
                    "confidence": 0.85,
                }
            ],
            "extraction_summary": {
                "total_entities": 15,
                "high_confidence_entities": 12,
                "medical_complexity": "средняя",
                "text_quality": "хорошее",
            },
        }


    async def generate_medical_summary(
        self, consultation_text: str, patient_history: str | None = None
    ) -> dict[str, Any]:
        """Имитация генерации медицинского резюме"""
        await asyncio.sleep(2.5)

        return {
            "executive_summary": {
                "chief_complaint": "Головная боль, тошнота и головокружение",
                "primary_diagnosis": "Артериальная гипертензия",
                "key_findings": ["повышенное АД 160/95", "головная боль 3 дня"],
                "treatment_plan": "Антигипертензивная терапия каптоприлом",
                "prognosis": "благоприятный при соблюдении рекомендаций",
            },
            "clinical_assessment": {
                "presenting_symptoms": [
                    {
                        "symptom": "головная боль",
                        "severity": "умеренная",
                        "duration": "3 дня",
                        "impact": "снижает качество жизни",
                    },
                    {
                        "symptom": "тошнота",
                        "severity": "легкая",
                        "duration": "3 дня",
                        "impact": "минимальное",
                    },
                ],
                "physical_examination": {
                    "general_appearance": "удовлетворительное",
                    "vital_signs": "АД 160/95, пульс 88 уд/мин",
                    "system_specific_findings": {
                        "cardiovascular": "тоны сердца ясные, ритмичные",
                        "respiratory": "дыхание везикулярное",
                        "neurological": "без очаговой симптоматики",
                        "other": "без особенностей",
                    },
                },
                "diagnostic_impression": {
                    "primary_diagnosis": "Артериальная гипертензия I степени",
                    "differential_diagnoses": [
                        "вторичная гипертензия",
                        "гипертонический криз",
                    ],
                    "diagnostic_confidence": "высокая",
                    "additional_testing_needed": [
                        "ЭКГ",
                        "анализ мочи",
                        "биохимия крови",
                    ],
                },
            },
            "management_plan": {
                "immediate_interventions": [
                    {
                        "intervention": "начало антигипертензивной терапии",
                        "rationale": "снижение АД до целевых значений",
                        "timeline": "немедленно",
                    }
                ],
                "medications": [
                    {
                        "medication": "каптоприл 25 мг",
                        "indication": "артериальная гипертензия",
                        "dosing": "2 раза в день",
                        "monitoring": "контроль АД, функция почек",
                    }
                ],
                "non_pharmacological": [
                    {
                        "intervention": "диетические рекомендации",
                        "instructions": "ограничение соли до 5 г/день",
                        "expected_outcome": "снижение АД на 5-10 мм рт.ст.",
                    }
                ],
                "follow_up": {
                    "next_appointment": "через 2 недели",
                    "monitoring_parameters": ["АД", "самочувствие", "побочные эффекты"],
                    "red_flags": ["АД >180/110", "боль в груди", "одышка"],
                },
            },
            "patient_education": {
                "key_points": [
                    "важность регулярного приема препаратов",
                    "необходимость контроля АД дома",
                ],
                "lifestyle_modifications": [
                    "ограничение соли в рационе",
                    "регулярная физическая активность",
                    "отказ от курения",
                ],
                "warning_signs": [
                    "сильная головная боль",
                    "нарушение зрения",
                    "боль в груди",
                ],
                "resources": ["памятка по измерению АД", "диетические рекомендации"],
            },
            "quality_metrics": {
                "documentation_completeness": 8,
                "clinical_reasoning_clarity": 9,
                "treatment_appropriateness": 8,
                "patient_safety_considerations": 9,
            },
            "recommendations": {
                "for_patient": [
                    "ведение дневника АД",
                    "соблюдение диеты и режима приема препаратов",
                ],
                "for_healthcare_team": [
                    "контроль приверженности лечению",
                    "мониторинг эффективности терапии",
                ],
                "for_documentation": [
                    "добавить информацию о семейном анамнезе",
                    "уточнить данные о курении",
                ],
            },
        }


    async def validate_medical_record(
        self, record_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Имитация валидации медицинской записи"""
        await asyncio.sleep(2)

        return {
            "validation_summary": {
                "overall_score": 8,
                "completeness_score": 7,
                "accuracy_score": 9,
                "compliance_score": 8,
                "validation_status": "warning",
            },
            "required_fields_check": {
                "present_fields": ["жалобы", "диагноз", "лечение", "осмотр"],
                "missing_fields": ["аллергии", "семейный анамнез"],
                "incomplete_fields": ["анамнез заболевания"],
                "completeness_percentage": 75,
            },
            "clinical_consistency": {
                "diagnosis_symptom_alignment": {"status": "consistent", "issues": []},
                "treatment_diagnosis_alignment": {
                    "status": "appropriate",
                    "concerns": [],
                },
                "medication_interactions": {"status": "safe", "interactions": []},
            },
            "terminology_validation": {
                "medical_terms_accuracy": "высокая",
                "icd_code_validity": "корректные",
                "medication_names": "стандартные",
                "terminology_issues": [],
            },
            "data_quality_issues": [
                {
                    "field": "аллергии",
                    "issue_type": "missing_data",
                    "severity": "средняя",
                    "description": "Отсутствует информация об аллергических реакциях",
                    "suggestion": "Добавить раздел об аллергиях и непереносимости",
                },
                {
                    "field": "анамнез",
                    "issue_type": "incomplete_data",
                    "severity": "низкая",
                    "description": "Недостаточно подробный анамнез заболевания",
                    "suggestion": "Расширить описание развития заболевания",
                },
            ],
            "compliance_check": {
                "documentation_standards": {
                    "status": "compliant",
                    "standard": "Приказ МЗ РФ №834н",
                    "violations": [],
                },
                "privacy_security": {
                    "phi_protection": "защищена",
                    "access_controls": "соответствует",
                    "audit_trail": "присутствует",
                },
            },
            "improvement_recommendations": [
                {
                    "category": "полнота документации",
                    "priority": "средний",
                    "recommendation": "Добавить информацию об аллергиях",
                    "expected_impact": "повышение безопасности пациента",
                    "implementation_effort": "низкий",
                },
                {
                    "category": "клиническое обоснование",
                    "priority": "низкий",
                    "recommendation": "Расширить обоснование выбора терапии",
                    "expected_impact": "улучшение качества документации",
                    "implementation_effort": "средний",
                },
            ],
            "risk_assessment": {
                "patient_safety_risks": ["неучтенные аллергии"],
                "legal_compliance_risks": [],
                "quality_of_care_risks": ["неполная оценка анамнеза"],
                "overall_risk_level": "низкий",
            },
            "automated_corrections": {
                "spelling_corrections": [],
                "format_standardizations": ["стандартизация единиц измерения"],
                "code_suggestions": ["I10 - Эссенциальная гипертензия"],
            },
        }


