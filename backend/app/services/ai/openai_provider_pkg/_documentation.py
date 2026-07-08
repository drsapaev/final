"""Documentation mixin for OpenAIProvider.

Split from openai_provider.py.
"""
from __future__ import annotations

from app.services.ai.openai_provider_pkg._base import (
    OpenAIProviderMixinBase,
    AIRequest,
    AIResponse,
    json,
    logging,
    Any,
    base64,
)


class DocumentationMixin(OpenAIProviderMixinBase):
    """Documentation methods for OpenAIProvider."""

    async def analyze_documentation_quality(
        self, medical_records: list[dict], quality_standards: dict[str, Any]
    ) -> dict[str, Any]:
        """Анализ качества медицинской документации"""
        records_summary = []
        for record in medical_records[:10]:  # Ограничиваем для анализа
            summary = {
                "record_id": record.get("id", "не указан"),
                "record_type": record.get("type", "не указан"),
                "completeness": (
                    len([k for k, v in record.items() if v]) / len(record) * 100
                    if record
                    else 0
                ),
                "fields_count": len(record),
                "has_diagnosis": bool(record.get("diagnosis")),
                "has_treatment": bool(record.get("treatment")),
                "has_symptoms": bool(record.get("symptoms")),
            }
            records_summary.append(summary)

        standards_text = "\n".join(
            [f"- {k}: {v}" for k, v in quality_standards.items()]
        )
        records_text = "\n".join(
            [
                f"Запись {r['record_id']}: {r['record_type']}, полнота {r['completeness']:.1f}%, диагноз: {'есть' if r['has_diagnosis'] else 'нет'}"
                for r in records_summary
            ]
        )

        prompt = f"""
        Проанализируйте качество медицинской документации на соответствие стандартам:

        СТАНДАРТЫ КАЧЕСТВА:
        {standards_text}

        АНАЛИЗИРУЕМЫЕ ЗАПИСИ:
        {records_text}

        Предоставьте анализ в формате JSON:
        {{
            "quality_assessment": {{
                "overall_quality_score": "общая оценка качества от 1 до 10",
                "records_analyzed": {len(records_summary)},
                "compliance_rate": "процент соответствия стандартам",
                "quality_trend": "улучшается/стабильно/ухудшается",
                "benchmark_comparison": "сравнение с эталонными показателями"
            }},
            "quality_metrics": {{
                "completeness_score": "оценка полноты документации",
                "accuracy_score": "оценка точности информации",
                "timeliness_score": "оценка своевременности заполнения",
                "consistency_score": "оценка согласованности данных",
                "legibility_score": "оценка читаемости записей"
            }},
            "documentation_analysis": [
                {{
                    "category": "категория документации",
                    "quality_level": "высокое/среднее/низкое",
                    "common_issues": ["проблема 1", "проблема 2"],
                    "compliance_gaps": ["пробел соответствия 1", "пробел соответствия 2"],
                    "improvement_potential": "потенциал улучшения"
                }}
            ],
            "critical_findings": [
                {{
                    "finding": "критическая находка",
                    "severity": "критическая/высокая/средняя/низкая",
                    "impact": "влияние на качество помощи",
                    "frequency": "частота встречаемости",
                    "recommended_action": "рекомендуемое действие"
                }}
            ],
            "best_practices_adherence": {{
                "clinical_guidelines": {{
                    "adherence_rate": "процент соблюдения",
                    "deviations": ["отклонение 1", "отклонение 2"],
                    "justifications": ["обоснование 1", "обоснование 2"]
                }},
                "documentation_standards": {{
                    "format_compliance": "соответствие формату",
                    "required_fields": "заполнение обязательных полей",
                    "signature_requirements": "требования к подписям"
                }},
                "legal_requirements": {{
                    "regulatory_compliance": "соответствие нормативам",
                    "audit_readiness": "готовность к аудиту",
                    "risk_areas": ["область риска 1", "область риска 2"]
                }}
            }},
            "improvement_recommendations": [
                {{
                    "area": "область улучшения",
                    "priority": "высокий/средний/низкий",
                    "recommendation": "конкретная рекомендация",
                    "expected_impact": "ожидаемое влияние",
                    "implementation_effort": "усилия по внедрению",
                    "timeline": "временные рамки",
                    "success_metrics": ["метрика успеха 1", "метрика успеха 2"]
                }}
            ],
            "training_needs": [
                {{
                    "skill_area": "область навыков",
                    "target_audience": "целевая аудитория",
                    "training_type": "тип обучения",
                    "urgency": "срочность",
                    "expected_outcome": "ожидаемый результат"
                }}
            ],
            "quality_monitoring": {{
                "key_indicators": ["ключевой индикатор 1", "ключевой индикатор 2"],
                "monitoring_frequency": "частота мониторинга",
                "alert_thresholds": "пороговые значения для предупреждений",
                "reporting_schedule": "график отчетности"
            }}
        }}
        """

        system_prompt = """Вы специалист по качеству медицинской документации с экспертизой в аудите и улучшении медицинских записей.
        Анализируете документацию на соответствие медицинским стандартам, нормативным требованиям и лучшим практикам.
        Выявляете проблемы качества и предоставляете практические рекомендации по улучшению.
        Обеспечиваете соблюдение требований безопасности пациентов и правовых норм.
        Ответы даете только в формате JSON."""

        request = AIRequest(
            prompt=prompt, system_prompt=system_prompt, temperature=0.1, max_tokens=4000
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


    async def detect_documentation_gaps(
        self, patient_record: dict[str, Any], required_fields: list[str]
    ) -> dict[str, Any]:
        """Выявление пробелов в медицинской документации"""
        _record_fields = list(patient_record.keys())
        missing_fields = [
            field
            for field in required_fields
            if field not in patient_record or not patient_record.get(field)
        ]
        present_fields = [
            field
            for field in required_fields
            if field in patient_record and patient_record.get(field)
        ]

        record_summary = {
            "total_fields": len(patient_record),
            "required_fields": len(required_fields),
            "present_fields": len(present_fields),
            "missing_fields": len(missing_fields),
            "completeness_percentage": (
                (len(present_fields) / len(required_fields)) * 100
                if required_fields
                else 100
            ),
        }

        record_text = json.dumps(patient_record, ensure_ascii=False, indent=2)
        required_text = ", ".join(required_fields)
        missing_text = ", ".join(missing_fields) if missing_fields else "нет"

        prompt = f"""
        Выявите пробелы в медицинской документации пациента:

        МЕДИЦИНСКАЯ ЗАПИСЬ:
        {record_text}

        ОБЯЗАТЕЛЬНЫЕ ПОЛЯ: {required_text}
        ОТСУТСТВУЮЩИЕ ПОЛЯ: {missing_text}
        СТАТИСТИКА: {record_summary}

        Предоставьте анализ пробелов в формате JSON:
        {{
            "gap_analysis": {{
                "completeness_score": {record_summary['completeness_percentage']:.1f},
                "total_gaps": {len(missing_fields)},
                "critical_gaps": "количество критических пробелов",
                "minor_gaps": "количество незначительных пробелов",
                "gap_severity": "критическая/высокая/средняя/низкая"
            }},
            "missing_information": [
                {{
                    "field": "отсутствующее поле",
                    "category": "категория информации",
                    "importance": "критическая/высокая/средняя/низкая",
                    "impact_on_care": "влияние на качество помощи",
                    "regulatory_requirement": "нормативное требование",
                    "suggested_source": "предлагаемый источник информации",
                    "collection_method": "метод сбора информации"
                }}
            ],
            "incomplete_sections": [
                {{
                    "section": "неполная секция",
                    "missing_elements": ["отсутствующий элемент 1", "отсутствующий элемент 2"],
                    "completion_percentage": "процент заполненности",
                    "priority_for_completion": "приоритет заполнения",
                    "clinical_significance": "клиническая значимость"
                }}
            ],
            "data_quality_issues": [
                {{
                    "issue": "проблема качества данных",
                    "field": "проблемное поле",
                    "issue_type": "тип проблемы",
                    "severity": "серьезность",
                    "correction_needed": "необходимая коррекция",
                    "validation_rule": "правило валидации"
                }}
            ],
            "compliance_gaps": {{
                "regulatory_compliance": {{
                    "missing_required_fields": ["обязательное поле 1", "обязательное поле 2"],
                    "non_compliant_formats": ["некорректный формат 1", "некорректный формат 2"],
                    "signature_issues": ["проблема подписи 1", "проблема подписи 2"]
                }},
                "clinical_standards": {{
                    "missing_assessments": ["отсутствующая оценка 1", "отсутствующая оценка 2"],
                    "incomplete_histories": ["неполная история 1", "неполная история 2"],
                    "missing_follow_up": ["отсутствующее наблюдение 1", "отсутствующее наблюдение 2"]
                }}
            }},
            "risk_assessment": {{
                "patient_safety_risks": ["риск безопасности 1", "риск безопасности 2"],
                "legal_risks": ["правовой риск 1", "правовой риск 2"],
                "quality_of_care_risks": ["риск качества 1", "риск качества 2"],
                "continuity_of_care_risks": ["риск непрерывности 1", "риск непрерывности 2"]
            }},
            "remediation_plan": [
                {{
                    "gap": "пробел для устранения",
                    "action": "необходимое действие",
                    "responsible_party": "ответственная сторона",
                    "timeline": "временные рамки",
                    "resources_needed": "необходимые ресурсы",
                    "success_criteria": "критерии успеха"
                }}
            ],
            "prevention_strategies": [
                {{
                    "strategy": "стратегия предотвращения",
                    "implementation": "способ внедрения",
                    "target_audience": "целевая аудитория",
                    "expected_outcome": "ожидаемый результат"
                }}
            ]
        }}
        """

        system_prompt = """Вы специалист по анализу медицинской документации с экспертизой в выявлении пробелов и недостатков.
        Систематически анализируете медицинские записи на полноту, точность и соответствие требованиям.
        Выявляете критические пробелы, влияющие на безопасность пациентов и качество помощи.
        Предоставляете практические рекомендации по устранению недостатков документации.
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


    async def suggest_documentation_improvements(
        self, record_analysis: dict[str, Any], best_practices: dict[str, Any]
    ) -> dict[str, Any]:
        """Предложение улучшений для медицинской документации"""
        analysis_text = json.dumps(record_analysis, ensure_ascii=False, indent=2)
        practices_text = json.dumps(best_practices, ensure_ascii=False, indent=2)

        prompt = f"""
        На основе анализа медицинской документации предложите улучшения:

        АНАЛИЗ ДОКУМЕНТАЦИИ:
        {analysis_text}

        ЛУЧШИЕ ПРАКТИКИ:
        {practices_text}

        Предоставьте рекомендации по улучшению в формате JSON:
        {{
            "improvement_summary": {{
                "total_recommendations": "общее количество рекомендаций",
                "priority_areas": ["приоритетная область 1", "приоритетная область 2"],
                "expected_impact": "ожидаемое влияние улучшений",
                "implementation_complexity": "сложность внедрения",
                "estimated_timeline": "предполагаемые временные рамки"
            }},
            "structural_improvements": [
                {{
                    "area": "область структурного улучшения",
                    "current_issue": "текущая проблема",
                    "proposed_solution": "предлагаемое решение",
                    "benefits": ["преимущество 1", "преимущество 2"],
                    "implementation_steps": ["шаг 1", "шаг 2"],
                    "resources_required": ["ресурс 1", "ресурс 2"],
                    "success_metrics": ["метрика успеха 1", "метрика успеха 2"]
                }}
            ],
            "content_improvements": [
                {{
                    "section": "секция для улучшения",
                    "enhancement": "улучшение содержания",
                    "rationale": "обоснование улучшения",
                    "clinical_benefit": "клиническая польза",
                    "patient_safety_impact": "влияние на безопасность пациента",
                    "compliance_benefit": "польза для соответствия требованиям"
                }}
            ],
            "process_improvements": [
                {{
                    "process": "процесс для улучшения",
                    "current_workflow": "текущий рабочий процесс",
                    "improved_workflow": "улучшенный рабочий процесс",
                    "efficiency_gain": "повышение эффективности",
                    "quality_improvement": "улучшение качества",
                    "training_requirements": ["требование к обучению 1", "требование к обучению 2"]
                }}
            ],
            "technology_recommendations": [
                {{
                    "technology": "рекомендуемая технология",
                    "purpose": "цель использования",
                    "features": ["функция 1", "функция 2"],
                    "integration_requirements": ["требование интеграции 1", "требование интеграции 2"],
                    "cost_benefit_analysis": "анализ затрат и выгод",
                    "implementation_timeline": "график внедрения"
                }}
            ],
            "quality_assurance_measures": [
                {{
                    "measure": "мера обеспечения качества",
                    "objective": "цель меры",
                    "implementation_method": "метод внедрения",
                    "monitoring_approach": "подход к мониторингу",
                    "frequency": "частота применения",
                    "responsible_parties": ["ответственная сторона 1", "ответственная сторона 2"]
                }}
            ],
            "training_programs": [
                {{
                    "program": "программа обучения",
                    "target_audience": "целевая аудитория",
                    "learning_objectives": ["цель обучения 1", "цель обучения 2"],
                    "delivery_method": "метод проведения",
                    "duration": "продолжительность",
                    "assessment_criteria": ["критерий оценки 1", "критерий оценки 2"],
                    "certification_requirements": "требования к сертификации"
                }}
            ],
            "compliance_enhancements": {{
                "regulatory_alignment": [
                    {{
                        "regulation": "нормативный акт",
                        "current_compliance_level": "текущий уровень соответствия",
                        "required_changes": ["необходимое изменение 1", "необходимое изменение 2"],
                        "compliance_timeline": "график достижения соответствия"
                    }}
                ],
                "audit_preparedness": [
                    {{
                        "audit_area": "область аудита",
                        "preparation_steps": ["шаг подготовки 1", "шаг подготовки 2"],
                        "documentation_requirements": ["требование к документации 1", "требование к документации 2"],
                        "risk_mitigation": ["снижение риска 1", "снижение риска 2"]
                    }}
                ]
            }},
            "performance_monitoring": {{
                "key_performance_indicators": [
                    {{
                        "indicator": "ключевой показатель",
                        "measurement_method": "метод измерения",
                        "target_value": "целевое значение",
                        "reporting_frequency": "частота отчетности",
                        "responsible_party": "ответственная сторона"
                    }}
                ],
                "quality_dashboards": [
                    {{
                        "dashboard": "панель качества",
                        "metrics_displayed": ["отображаемая метрика 1", "отображаемая метрика 2"],
                        "update_frequency": "частота обновления",
                        "target_users": ["целевой пользователь 1", "целевой пользователь 2"]
                    }}
                ]
            }},
            "implementation_roadmap": {{
                "phase_1": {{
                    "duration": "длительность фазы 1",
                    "objectives": ["цель 1", "цель 2"],
                    "deliverables": ["результат 1", "результат 2"],
                    "success_criteria": ["критерий успеха 1", "критерий успеха 2"]
                }},
                "phase_2": {{
                    "duration": "длительность фазы 2",
                    "objectives": ["цель 1", "цель 2"],
                    "deliverables": ["результат 1", "результат 2"],
                    "success_criteria": ["критерий успеха 1", "критерий успеха 2"]
                }},
                "phase_3": {{
                    "duration": "длительность фазы 3",
                    "objectives": ["цель 1", "цель 2"],
                    "deliverables": ["результат 1", "результат 2"],
                    "success_criteria": ["критерий успеха 1", "критерий успеха 2"]
                }}
            }}
        }}
        """

        system_prompt = """Вы консультант по улучшению качества медицинской документации с экспертизой в оптимизации процессов и внедрении лучших практик.
        Разрабатываете комплексные стратегии улучшения документации, учитывающие клинические, технологические и регулятивные аспекты.
        Предоставляете практические, реализуемые рекомендации с четкими планами внедрения и показателями успеха.
        Обеспечиваете соответствие международным стандартам качества и безопасности пациентов.
        Ответы даете только в формате JSON."""

        request = AIRequest(
            prompt=prompt, system_prompt=system_prompt, temperature=0.2, max_tokens=4500
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


    async def validate_clinical_consistency(
        self, diagnosis: str, symptoms: list[str], treatment: dict[str, Any]
    ) -> dict[str, Any]:
        """Валидация клинической согласованности диагноза, симптомов и лечения"""
        symptoms_text = ", ".join(symptoms) if symptoms else "не указаны"
        treatment_text = (
            json.dumps(treatment, ensure_ascii=False) if treatment else "не указано"
        )

        prompt = f"""
        Проверьте клиническую согласованность диагноза, симптомов и лечения:

        ДИАГНОЗ: {diagnosis}
        СИМПТОМЫ: {symptoms_text}
        ЛЕЧЕНИЕ: {treatment_text}

        Предоставьте валидацию согласованности в формате JSON:
        {{
            "consistency_assessment": {{
                "overall_consistency": "высокая/средняя/низкая/несогласованная",
                "consistency_score": "оценка согласованности от 1 до 10",
                "clinical_logic": "логичность клинического мышления",
                "evidence_support": "поддержка доказательствами",
                "guideline_adherence": "соответствие клиническим рекомендациям"
            }},
            "diagnosis_validation": {{
                "diagnosis_accuracy": "точность диагноза",
                "symptom_alignment": {{
                    "supporting_symptoms": ["поддерживающий симптом 1", "поддерживающий симптом 2"],
                    "contradicting_symptoms": ["противоречащий симптом 1", "противоречащий симптом 2"],
                    "missing_key_symptoms": ["отсутствующий ключевой симптом 1", "отсутствующий ключевой симптом 2"],
                    "alignment_percentage": "процент соответствия симптомов"
                }},
                "differential_diagnosis": {{
                    "alternative_diagnoses": ["альтернативный диагноз 1", "альтернативный диагноз 2"],
                    "ruling_out_rationale": "обоснование исключения альтернатив",
                    "additional_tests_needed": ["дополнительный тест 1", "дополнительный тест 2"]
                }}
            }},
            "treatment_validation": {{
                "treatment_appropriateness": "соответствие лечения диагнозу",
                "medication_analysis": [
                    {{
                        "medication": "препарат",
                        "indication_match": "соответствие показаниям",
                        "dosage_appropriateness": "соответствие дозировки",
                        "contraindication_check": "проверка противопоказаний",
                        "interaction_risks": ["риск взаимодействия 1", "риск взаимодействия 2"]
                    }}
                ],
                "non_pharmacological_interventions": [
                    {{
                        "intervention": "немедикаментозное вмешательство",
                        "evidence_base": "доказательная база",
                        "appropriateness": "соответствие состоянию",
                        "expected_outcome": "ожидаемый результат"
                    }}
                ]
            }},
            "clinical_red_flags": [
                {{
                    "red_flag": "тревожный признак",
                    "category": "диагноз/симптомы/лечение",
                    "severity": "критический/высокий/средний/низкий",
                    "clinical_significance": "клиническая значимость",
                    "recommended_action": "рекомендуемое действие",
                    "urgency": "срочность действия"
                }}
            ],
            "evidence_gaps": [
                {{
                    "gap": "пробел в доказательствах",
                    "area": "область пробела",
                    "impact": "влияние на лечение",
                    "suggested_investigation": "предлагаемое исследование",
                    "priority": "приоритет устранения"
                }}
            ],
            "quality_indicators": {{
                "diagnostic_accuracy_indicators": ["индикатор точности диагностики 1", "индикатор точности диагностики 2"],
                "treatment_quality_indicators": ["индикатор качества лечения 1", "индикатор качества лечения 2"],
                "patient_safety_indicators": ["индикатор безопасности 1", "индикатор безопасности 2"],
                "outcome_predictors": ["предиктор исхода 1", "предиктор исхода 2"]
            }},
            "improvement_recommendations": [
                {{
                    "area": "область улучшения",
                    "recommendation": "рекомендация",
                    "rationale": "обоснование",
                    "expected_benefit": "ожидаемая польза",
                    "implementation_steps": ["шаг внедрения 1", "шаг внедрения 2"]
                }}
            ],
            "follow_up_requirements": {{
                "monitoring_parameters": ["параметр мониторинга 1", "параметр мониторинга 2"],
                "follow_up_timeline": "график наблюдения",
                "reassessment_triggers": ["триггер переоценки 1", "триггер переоценки 2"],
                "specialist_referral_indications": ["показание к консультации 1", "показание к консультации 2"]
            }}
        }}
        """

        system_prompt = """Вы клинический эксперт с глубокими знаниями в области диагностики и лечения заболеваний.
        Анализируете клиническую согласованность диагнозов, симптомов и назначенного лечения.
        Используете принципы доказательной медицины и современные клинические рекомендации.
        Выявляете потенциальные проблемы безопасности и качества медицинской помощи.
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


    async def audit_prescription_safety(
        self, prescriptions: list[dict], patient_profile: dict[str, Any]
    ) -> dict[str, Any]:
        """Аудит безопасности назначений и рецептов"""
        prescriptions_text = "\n".join(
            [
                f"- {p.get('medication', 'не указано')}: {p.get('dosage', 'не указано')}, {p.get('frequency', 'не указано')}, {p.get('duration', 'не указано')}"
                for p in prescriptions[:10]  # Ограничиваем для анализа
            ]
        )

        patient_text = json.dumps(patient_profile, ensure_ascii=False, indent=2)

        prompt = f"""
        Проведите аудит безопасности назначений и рецептов:

        НАЗНАЧЕНИЯ:
        {prescriptions_text}

        ПРОФИЛЬ ПАЦИЕНТА:
        {patient_text}

        Предоставьте аудит безопасности в формате JSON:
        {{
            "safety_assessment": {{
                "overall_safety_score": "общая оценка безопасности от 1 до 10",
                "prescriptions_reviewed": {len(prescriptions)},
                "high_risk_prescriptions": "количество высокорисковых назначений",
                "safety_alerts": "количество предупреждений безопасности",
                "critical_interactions": "количество критических взаимодействий"
            }},
            "medication_analysis": [
                {{
                    "medication": "название препарата",
                    "safety_profile": {{
                        "risk_category": "низкий/средний/высокий/критический",
                        "contraindications": ["противопоказание 1", "противопоказание 2"],
                        "patient_specific_risks": ["специфический риск 1", "специфический риск 2"],
                        "monitoring_requirements": ["требование мониторинга 1", "требование мониторинга 2"]
                    }},
                    "dosage_assessment": {{
                        "appropriateness": "соответствие дозировки",
                        "age_adjustment": "коррекция по возрасту",
                        "renal_adjustment": "коррекция по функции почек",
                        "hepatic_adjustment": "коррекция по функции печени",
                        "weight_based_dosing": "дозирование по весу"
                    }},
                    "administration_safety": {{
                        "route_appropriateness": "соответствие пути введения",
                        "frequency_validation": "валидация частоты приема",
                        "duration_assessment": "оценка длительности курса",
                        "timing_considerations": ["соображение по времени 1", "соображение по времени 2"]
                    }}
                }}
            ],
            "drug_interactions": [
                {{
                    "interaction_type": "тип взаимодействия",
                    "medications_involved": ["препарат 1", "препарат 2"],
                    "severity": "критическая/высокая/средняя/низкая",
                    "mechanism": "механизм взаимодействия",
                    "clinical_significance": "клиническая значимость",
                    "management_strategy": "стратегия управления",
                    "monitoring_parameters": ["параметр мониторинга 1", "параметр мониторинга 2"]
                }}
            ],
            "patient_specific_considerations": {{
                "age_related_factors": [
                    {{
                        "factor": "возрастной фактор",
                        "impact": "влияние на назначения",
                        "recommendations": ["рекомендация 1", "рекомендация 2"]
                    }}
                ],
                "comorbidity_interactions": [
                    {{
                        "comorbidity": "сопутствующее заболевание",
                        "affected_medications": ["затронутый препарат 1", "затронутый препарат 2"],
                        "risk_assessment": "оценка риска",
                        "mitigation_strategies": ["стратегия снижения риска 1", "стратегия снижения риска 2"]
                    }}
                ],
                "allergy_considerations": [
                    {{
                        "allergen": "аллерген",
                        "cross_reactivity": "перекрестная реактивность",
                        "alternative_options": ["альтернативный вариант 1", "альтернативный вариант 2"],
                        "emergency_protocols": ["протокол экстренной помощи 1", "протокол экстренной помощи 2"]
                    }}
                ]
            }},
            "safety_alerts": [
                {{
                    "alert_type": "тип предупреждения",
                    "severity": "критическое/высокое/среднее/низкое",
                    "description": "описание предупреждения",
                    "affected_prescription": "затронутое назначение",
                    "recommended_action": "рекомендуемое действие",
                    "urgency": "срочность",
                    "follow_up_required": "требуется ли наблюдение"
                }}
            ],
            "compliance_assessment": {{
                "regulatory_compliance": {{
                    "prescription_format": "соответствие формата рецепта",
                    "required_information": "наличие обязательной информации",
                    "signature_requirements": "требования к подписям",
                    "controlled_substances": "контролируемые вещества"
                }},
                "clinical_guidelines": {{
                    "guideline_adherence": "соответствие клиническим рекомендациям",
                    "evidence_based_prescribing": "назначения на основе доказательств",
                    "first_line_therapy": "терапия первой линии",
                    "rational_prescribing": "рациональное назначение"
                }}
            }},
            "monitoring_recommendations": [
                {{
                    "medication": "препарат для мониторинга",
                    "parameters": ["параметр мониторинга 1", "параметр мониторинга 2"],
                    "frequency": "частота мониторинга",
                    "baseline_requirements": ["базовое требование 1", "базовое требование 2"],
                    "alert_values": ["пороговое значение 1", "пороговое значение 2"],
                    "action_plan": "план действий при отклонениях"
                }}
            ],
            "optimization_opportunities": [
                {{
                    "opportunity": "возможность оптимизации",
                    "current_approach": "текущий подход",
                    "suggested_improvement": "предлагаемое улучшение",
                    "expected_benefit": "ожидаемая польза",
                    "implementation_considerations": ["соображение внедрения 1", "соображение внедрения 2"]
                }}
            ],
            "patient_education_needs": [
                {{
                    "topic": "тема обучения пациента",
                    "key_points": ["ключевой момент 1", "ключевой момент 2"],
                    "safety_warnings": ["предупреждение безопасности 1", "предупреждение безопасности 2"],
                    "adherence_strategies": ["стратегия приверженности 1", "стратегия приверженности 2"]
                }}
            ]
        }}
        """

        system_prompt = """Вы клинический фармаколог с экспертизой в области безопасности лекарственных средств и рационального назначения.
        Проводите комплексный аудит назначений на предмет безопасности, эффективности и соответствия стандартам.
        Анализируете лекарственные взаимодействия, противопоказания и индивидуальные факторы риска пациента.
        Предоставляете практические рекомендации по оптимизации фармакотерапии и обеспечению безопасности пациентов.
        Ответы даете только в формате JSON."""

        request = AIRequest(
            prompt=prompt, system_prompt=system_prompt, temperature=0.1, max_tokens=4000
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


