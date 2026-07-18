"""Text mixin for OpenAIProvider.

Split from openai_provider.py.
"""
from __future__ import annotations

from app.services.ai.openai_provider_pkg._base import (
    AIRequest,
    Any,
    OpenAIProviderMixinBase,
    json,
)


class TextMixin(OpenAIProviderMixinBase):
    """Text methods for OpenAIProvider."""

    async def transcribe_audio(
        self, audio_data: bytes, language: str = "ru", medical_context: bool = True
    ) -> dict[str, Any]:
        """Транскрипция аудио в текст с медицинской терминологией"""
        try:
            # Создаем временный файл для аудио
            import os
            import tempfile

            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_file:
                temp_file.write(audio_data)
                temp_file_path = temp_file.name

            try:
                # Используем Whisper API для транскрипции
                with open(temp_file_path, 'rb') as audio_file:
                    transcript = await self.client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language=language,
                        prompt=(
                            "Медицинская консультация. Включает медицинскую терминологию, симптомы, диагнозы, лечение."
                            if medical_context
                            else None
                        ),
                        response_format="verbose_json",
                        temperature=0.1,
                    )

                return {
                    "text": transcript.text,
                    "language": transcript.language,
                    "duration": transcript.duration,
                    "segments": (
                        [
                            {
                                "start": segment.start,
                                "end": segment.end,
                                "text": segment.text,
                                "confidence": getattr(segment, 'avg_logprob', 0.0),
                            }
                            for segment in transcript.segments
                        ]
                        if hasattr(transcript, 'segments')
                        else []
                    ),
                    "confidence": getattr(transcript, 'avg_logprob', 0.0),
                    "medical_context": medical_context,
                }
            finally:
                # Удаляем временный файл
                os.unlink(temp_file_path)

        except Exception:
            return {
                "error": "Ошибка транскрипции",  # sanitized
                "text": "",
                "confidence": 0.0,
            }


    async def structure_medical_text(
        self, text: str, document_type: str
    ) -> dict[str, Any]:
        """Структурирование медицинского текста в формализованные поля"""
        document_templates = {
            "consultation": {
                "fields": [
                    "жалобы",
                    "анамнез",
                    "объективный_осмотр",
                    "диагноз",
                    "лечение",
                    "рекомендации",
                ],
                "description": "консультация врача",
            },
            "prescription": {
                "fields": [
                    "препараты",
                    "дозировка",
                    "способ_применения",
                    "длительность",
                    "противопоказания",
                ],
                "description": "рецепт",
            },
            "discharge": {
                "fields": [
                    "диагноз_при_выписке",
                    "проведенное_лечение",
                    "состояние_при_выписке",
                    "рекомендации",
                    "контрольные_осмотры",
                ],
                "description": "выписной эпикриз",
            },
            "examination": {
                "fields": [
                    "вид_исследования",
                    "показания",
                    "результаты",
                    "заключение",
                    "рекомендации",
                ],
                "description": "результат обследования",
            },
        }

        template = document_templates.get(
            document_type, document_templates["consultation"]
        )
        fields_list = ", ".join(template["fields"])

        prompt = f"""
        Структурируйте медицинский текст ({template["description"]}) в формализованные поля.

        ИСХОДНЫЙ ТЕКСТ:
        {text}

        ТРЕБУЕМЫЕ ПОЛЯ: {fields_list}

        Предоставьте структурированный результат в формате JSON:
        {{
            "document_type": "{document_type}",
            "structured_data": {{
                "поле1": "извлеченная информация",
                "поле2": "извлеченная информация"
            }},
            "extracted_entities": {{
                "medications": ["препарат1", "препарат2"],
                "diagnoses": ["диагноз1", "диагноз2"],
                "symptoms": ["симптом1", "симптом2"],
                "procedures": ["процедура1", "процедура2"],
                "dosages": ["дозировка1", "дозировка2"],
                "dates": ["дата1", "дата2"]
            }},
            "completeness_score": "оценка полноты от 1 до 10",
            "missing_fields": ["отсутствующее поле1", "отсутствующее поле2"],
            "confidence_scores": {{
                "поле1": 0.95,
                "поле2": 0.87
            }},
            "suggestions": [
                "предложение по улучшению записи 1",
                "предложение по улучшению записи 2"
            ],
            "quality_indicators": {{
                "terminology_accuracy": "высокая/средняя/низкая",
                "clinical_coherence": "высокая/средняя/низкая",
                "documentation_standards": "соответствует/частично/не_соответствует"
            }}
        }}
        """

        system_prompt = """Вы медицинский документовед с экспертизой в структурировании медицинских записей.
        Извлекаете и организуете информацию из неструктурированного медицинского текста.
        Используете стандартную медицинскую терминологию и форматы документации.
        Обеспечиваете высокое качество структурирования и полноту извлечения данных.
        Ответы даете только в формате JSON."""

        request = AIRequest(
            prompt=prompt, system_prompt=system_prompt, temperature=0.1, max_tokens=2500
        )

        response = await self.generate(request)

        if response.error:
            return {"error": response.error}

        try:
            return json.loads(response.content)
        except Exception:
            return {
                "error": "Не удалось разобрать ответ AI",
                "raw_response": response.content,
            }


    async def extract_medical_entities(self, text: str) -> dict[str, Any]:
        """Извлечение медицинских сущностей из текста"""
        prompt = f"""
        Извлеките медицинские сущности из следующего текста:

        ТЕКСТ:
        {text}

        Предоставьте результат в формате JSON:
        {{
            "medications": [
                {{
                    "name": "название препарата",
                    "dosage": "дозировка",
                    "frequency": "частота приема",
                    "route": "способ введения",
                    "duration": "длительность",
                    "confidence": 0.95
                }}
            ],
            "diagnoses": [
                {{
                    "name": "название диагноза",
                    "icd_code": "код МКБ-10 (если определим)",
                    "type": "основной/сопутствующий/осложнение",
                    "confidence": 0.90
                }}
            ],
            "symptoms": [
                {{
                    "name": "симптом",
                    "severity": "легкий/умеренный/тяжелый",
                    "duration": "длительность",
                    "frequency": "частота",
                    "confidence": 0.85
                }}
            ],
            "procedures": [
                {{
                    "name": "название процедуры",
                    "type": "диагностическая/лечебная/профилактическая",
                    "date": "дата (если указана)",
                    "result": "результат (если указан)",
                    "confidence": 0.88
                }}
            ],
            "laboratory_tests": [
                {{
                    "name": "название анализа",
                    "value": "значение",
                    "unit": "единица измерения",
                    "reference_range": "референсные значения",
                    "interpretation": "норма/повышено/понижено",
                    "confidence": 0.92
                }}
            ],
            "vital_signs": [
                {{
                    "parameter": "параметр",
                    "value": "значение",
                    "unit": "единица",
                    "timestamp": "время измерения",
                    "confidence": 0.95
                }}
            ],
            "anatomical_locations": [
                {{
                    "location": "анатомическая область",
                    "side": "левый/правый/двусторонний",
                    "specificity": "точная локализация",
                    "confidence": 0.87
                }}
            ],
            "temporal_expressions": [
                {{
                    "expression": "временное выражение",
                    "normalized_date": "нормализованная дата",
                    "type": "абсолютная/относительная",
                    "confidence": 0.80
                }}
            ],
            "allergies": [
                {{
                    "allergen": "аллерген",
                    "reaction": "тип реакции",
                    "severity": "тяжесть",
                    "confidence": 0.93
                }}
            ],
            "family_history": [
                {{
                    "condition": "заболевание",
                    "relation": "степень родства",
                    "age_of_onset": "возраст начала",
                    "confidence": 0.85
                }}
            ],
            "social_history": [
                {{
                    "factor": "социальный фактор",
                    "details": "детали",
                    "impact": "влияние на здоровье",
                    "confidence": 0.78
                }}
            ],
            "entity_relationships": [
                {{
                    "entity1": "сущность 1",
                    "relationship": "тип связи",
                    "entity2": "сущность 2",
                    "confidence": 0.82
                }}
            ],
            "extraction_summary": {{
                "total_entities": "общее количество сущностей",
                "high_confidence_entities": "количество с высокой достоверностью",
                "medical_complexity": "низкая/средняя/высокая",
                "text_quality": "хорошее/удовлетворительное/плохое"
            }}
        }}
        """

        system_prompt = """Вы специалист по обработке естественного языка в медицине с экспертизой в извлечении медицинских сущностей.
        Точно идентифицируете и классифицируете медицинские термины, препараты, диагнозы и процедуры.
        Используете медицинские стандарты и классификации (МКБ-10, АТХ и др.).
        Оцениваете достоверность извлечения и предоставляете структурированные результаты.
        Ответы даете только в формате JSON."""

        request = AIRequest(
            prompt=prompt, system_prompt=system_prompt, temperature=0.1, max_tokens=3000
        )

        response = await self.generate(request)

        if response.error:
            return {"error": response.error}

        try:
            return json.loads(response.content)
        except Exception:
            return {
                "error": "Не удалось разобрать ответ AI",
                "raw_response": response.content,
            }


    async def generate_medical_summary(
        self, consultation_text: str, patient_history: str | None = None
    ) -> dict[str, Any]:
        """Генерация медицинского резюме из текста консультации"""
        history_context = (
            f"\n\nИСТОРИЯ ПАЦИЕНТА:\n{patient_history}" if patient_history else ""
        )

        prompt = f"""
        Создайте медицинское резюме на основе текста консультации:

        ТЕКСТ КОНСУЛЬТАЦИИ:
        {consultation_text}{history_context}

        Предоставьте резюме в формате JSON:
        {{
            "executive_summary": {{
                "chief_complaint": "основная жалоба пациента",
                "primary_diagnosis": "основной диагноз",
                "key_findings": ["ключевая находка 1", "ключевая находка 2"],
                "treatment_plan": "краткий план лечения",
                "prognosis": "прогноз"
            }},
            "clinical_assessment": {{
                "presenting_symptoms": [
                    {{
                        "symptom": "симптом",
                        "severity": "тяжесть",
                        "duration": "длительность",
                        "impact": "влияние на качество жизни"
                    }}
                ],
                "physical_examination": {{
                    "general_appearance": "общий вид",
                    "vital_signs": "витальные показатели",
                    "system_specific_findings": {{
                        "cardiovascular": "находки",
                        "respiratory": "находки",
                        "neurological": "находки",
                        "other": "другие находки"
                    }}
                }},
                "diagnostic_impression": {{
                    "primary_diagnosis": "основной диагноз",
                    "differential_diagnoses": ["дифференциальный диагноз 1", "дифференциальный диагноз 2"],
                    "diagnostic_confidence": "высокая/средняя/низкая",
                    "additional_testing_needed": ["необходимое исследование 1", "необходимое исследование 2"]
                }}
            }},
            "management_plan": {{
                "immediate_interventions": [
                    {{
                        "intervention": "вмешательство",
                        "rationale": "обоснование",
                        "timeline": "временные рамки"
                    }}
                ],
                "medications": [
                    {{
                        "medication": "препарат",
                        "indication": "показание",
                        "dosing": "дозировка",
                        "monitoring": "мониторинг"
                    }}
                ],
                "non_pharmacological": [
                    {{
                        "intervention": "немедикаментозное вмешательство",
                        "instructions": "инструкции",
                        "expected_outcome": "ожидаемый результат"
                    }}
                ],
                "follow_up": {{
                    "next_appointment": "следующий визит",
                    "monitoring_parameters": ["параметр мониторинга 1", "параметр мониторинга 2"],
                    "red_flags": ["тревожный признак 1", "тревожный признак 2"]
                }}
            }},
            "patient_education": {{
                "key_points": ["ключевой момент 1", "ключевой момент 2"],
                "lifestyle_modifications": ["модификация образа жизни 1", "модификация образа жизни 2"],
                "warning_signs": ["предупреждающий признак 1", "предупреждающий признак 2"],
                "resources": ["ресурс 1", "ресурс 2"]
            }},
            "quality_metrics": {{
                "documentation_completeness": "полнота документации (1-10)",
                "clinical_reasoning_clarity": "ясность клинического мышления (1-10)",
                "treatment_appropriateness": "соответствие лечения (1-10)",
                "patient_safety_considerations": "соображения безопасности (1-10)"
            }},
            "recommendations": {{
                "for_patient": ["рекомендация для пациента 1", "рекомендация для пациента 2"],
                "for_healthcare_team": ["рекомендация для команды 1", "рекомендация для команды 2"],
                "for_documentation": ["рекомендация по документации 1", "рекомендация по документации 2"]
            }}
        }}
        """

        system_prompt = """Вы опытный врач-клиницист с экспертизой в создании медицинских резюме и клинической документации.
        Анализируете консультации и создаете структурированные, клинически значимые резюме.
        Обеспечиваете полноту, точность и клиническую релевантность информации.
        Следуете стандартам медицинской документации и клинического мышления.
        Ответы даете только в формате JSON."""

        request = AIRequest(
            prompt=prompt, system_prompt=system_prompt, temperature=0.2, max_tokens=3500
        )

        response = await self.generate(request)

        if response.error:
            return {"error": response.error}

        try:
            return json.loads(response.content)
        except Exception:
            return {
                "error": "Не удалось разобрать ответ AI",
                "raw_response": response.content,
            }


    async def validate_medical_record(
        self, record_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Валидация и проверка медицинской записи на полноту и корректность"""
        record_json = json.dumps(record_data, ensure_ascii=False, indent=2)

        prompt = f"""
        Проведите валидацию медицинской записи на полноту, корректность и соответствие стандартам:

        МЕДИЦИНСКАЯ ЗАПИСЬ:
        {record_json}

        Предоставьте результат валидации в формате JSON:
        {{
            "validation_summary": {{
                "overall_score": "общая оценка от 1 до 10",
                "completeness_score": "полнота от 1 до 10",
                "accuracy_score": "точность от 1 до 10",
                "compliance_score": "соответствие стандартам от 1 до 10",
                "validation_status": "passed/warning/failed"
            }},
            "required_fields_check": {{
                "present_fields": ["присутствующее поле 1", "присутствующее поле 2"],
                "missing_fields": ["отсутствующее поле 1", "отсутствующее поле 2"],
                "incomplete_fields": ["неполное поле 1", "неполное поле 2"],
                "completeness_percentage": "процент заполненности"
            }},
            "clinical_consistency": {{
                "diagnosis_symptom_alignment": {{
                    "status": "consistent/inconsistent/unclear",
                    "issues": ["проблема согласованности 1", "проблема согласованности 2"]
                }},
                "treatment_diagnosis_alignment": {{
                    "status": "appropriate/questionable/inappropriate",
                    "concerns": ["проблема лечения 1", "проблема лечения 2"]
                }},
                "medication_interactions": {{
                    "status": "safe/caution/dangerous",
                    "interactions": ["взаимодействие 1", "взаимодействие 2"]
                }}
            }},
            "terminology_validation": {{
                "medical_terms_accuracy": "высокая/средняя/низкая",
                "icd_code_validity": "корректные/некорректные/отсутствуют",
                "medication_names": "стандартные/нестандартные/ошибочные",
                "terminology_issues": ["проблема терминологии 1", "проблема терминологии 2"]
            }},
            "data_quality_issues": [
                {{
                    "field": "поле с проблемой",
                    "issue_type": "тип проблемы",
                    "severity": "критическая/высокая/средняя/низкая",
                    "description": "описание проблемы",
                    "suggestion": "предложение по исправлению"
                }}
            ],
            "compliance_check": {{
                "documentation_standards": {{
                    "status": "compliant/partial/non_compliant",
                    "standard": "используемый стандарт",
                    "violations": ["нарушение 1", "нарушение 2"]
                }},
                "privacy_security": {{
                    "phi_protection": "защищена/частично/не_защищена",
                    "access_controls": "соответствует/не_соответствует",
                    "audit_trail": "присутствует/отсутствует"
                }}
            }},
            "improvement_recommendations": [
                {{
                    "category": "категория улучшения",
                    "priority": "высокий/средний/низкий",
                    "recommendation": "рекомендация",
                    "expected_impact": "ожидаемое влияние",
                    "implementation_effort": "усилия по внедрению"
                }}
            ],
            "risk_assessment": {{
                "patient_safety_risks": ["риск безопасности 1", "риск безопасности 2"],
                "legal_compliance_risks": ["правовой риск 1", "правовой риск 2"],
                "quality_of_care_risks": ["риск качества 1", "риск качества 2"],
                "overall_risk_level": "низкий/умеренный/высокий/критический"
            }},
            "automated_corrections": {{
                "spelling_corrections": ["исправление 1", "исправление 2"],
                "format_standardizations": ["стандартизация 1", "стандартизация 2"],
                "code_suggestions": ["предложение кода 1", "предложение кода 2"]
            }}
        }}
        """

        system_prompt = """Вы специалист по качеству медицинской документации с экспертизой в валидации медицинских записей.
        Проверяете медицинские записи на полноту, точность, клиническую согласованность и соответствие стандартам.
        Используете медицинские стандарты, классификации и требования к документации.
        Выявляете проблемы качества данных и предоставляете конструктивные рекомендации по улучшению.
        Ответы даете только в формате JSON."""

        request = AIRequest(
            prompt=prompt, system_prompt=system_prompt, temperature=0.1, max_tokens=3500
        )

        response = await self.generate(request)

        if response.error:
            return {"error": response.error}

        try:
            return json.loads(response.content)
        except Exception:
            return {
                "error": "Не удалось разобрать ответ AI",
                "raw_response": response.content,
            }


