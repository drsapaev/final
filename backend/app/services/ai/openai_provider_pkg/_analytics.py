"""Analytics mixin for OpenAIProvider.

Split from openai_provider.py.
"""
from __future__ import annotations

from app.services.ai.openai_provider_pkg._base import (
    AIRequest,
    Any,
    OpenAIProviderMixinBase,
    json,
)


class AnalyticsMixin(OpenAIProviderMixinBase):
    """Analytics methods for OpenAIProvider."""

    async def analyze_medical_trends(
        self, medical_data: list[dict], time_period: str, analysis_type: str
    ) -> dict[str, Any]:
        """Анализ медицинских трендов и паттернов в данных"""
        # Ограничиваем данные для анализа
        data_sample = medical_data[:100] if len(medical_data) > 100 else medical_data

        # Подготавливаем сводку данных
        data_summary = {
            "total_records": len(medical_data),
            "sample_size": len(data_sample),
            "time_period": time_period,
            "analysis_type": analysis_type,
            "data_types": list(
                {record.get("type", "unknown") for record in data_sample}
            ),
            "date_range": {
                "start": (
                    min([record.get("date", "2024-01-01") for record in data_sample])
                    if data_sample
                    else "N/A"
                ),
                "end": (
                    max([record.get("date", "2024-01-01") for record in data_sample])
                    if data_sample
                    else "N/A"
                ),
            },
        }

        sample_data_text = "\n".join(
            [
                f"- {record.get('type', 'unknown')}: {record.get('diagnosis', 'N/A')} ({record.get('date', 'N/A')})"
                for record in data_sample[:20]  # Показываем только первые 20 записей
            ]
        )

        prompt = f"""
        Проанализируйте медицинские тренды и паттерны в предоставленных данных:

        ПАРАМЕТРЫ АНАЛИЗА:
        - Период анализа: {time_period}
        - Тип анализа: {analysis_type}
        - Общее количество записей: {data_summary['total_records']}
        - Размер выборки: {data_summary['sample_size']}

        ОБРАЗЕЦ ДАННЫХ:
        {sample_data_text}

        СВОДКА ДАННЫХ: {json.dumps(data_summary, ensure_ascii=False)}

        Предоставьте комплексный анализ трендов в формате JSON:
        {{
            "trend_analysis": {{
                "overall_trends": [
                    {{
                        "trend": "название тренда",
                        "direction": "возрастающий/убывающий/стабильный",
                        "magnitude": "сильный/умеренный/слабый",
                        "confidence": "высокая/средняя/низкая",
                        "time_pattern": "сезонный/циклический/линейный",
                        "statistical_significance": "значимый/незначимый",
                        "clinical_relevance": "высокая/средняя/низкая"
                    }}
                ],
                "seasonal_patterns": [
                    {{
                        "pattern": "сезонный паттерн",
                        "season": "весна/лето/осень/зима",
                        "peak_months": ["месяц 1", "месяц 2"],
                        "intensity": "высокая/средняя/низкая",
                        "recurrence": "ежегодно/периодически/однократно",
                        "affected_conditions": ["состояние 1", "состояние 2"]
                    }}
                ],
                "demographic_trends": [
                    {{
                        "demographic": "возрастная группа/пол/регион",
                        "trend_description": "описание тренда",
                        "growth_rate": "процент изменения",
                        "risk_factors": ["фактор риска 1", "фактор риска 2"],
                        "prevention_opportunities": ["возможность профилактики 1", "возможность профилактики 2"]
                    }}
                ]
            }},
            "pattern_detection": {{
                "disease_patterns": [
                    {{
                        "disease": "заболевание",
                        "pattern_type": "эпидемический/эндемический/спорадический",
                        "frequency": "частота встречаемости",
                        "geographic_distribution": "географическое распределение",
                        "age_distribution": "возрастное распределение",
                        "comorbidity_patterns": ["сопутствующее заболевание 1", "сопутствующее заболевание 2"],
                        "treatment_patterns": ["паттерн лечения 1", "паттерн лечения 2"]
                    }}
                ],
                "treatment_effectiveness": [
                    {{
                        "treatment": "метод лечения",
                        "effectiveness_trend": "улучшается/ухудшается/стабильно",
                        "success_rate": "процент успеха",
                        "response_time": "время ответа на лечение",
                        "side_effects_trend": "увеличиваются/уменьшаются/стабильны",
                        "cost_effectiveness": "экономическая эффективность"
                    }}
                ],
                "resource_utilization": [
                    {{
                        "resource": "тип ресурса",
                        "utilization_trend": "увеличивается/уменьшается/стабильно",
                        "peak_usage_times": ["время пика 1", "время пика 2"],
                        "bottlenecks": ["узкое место 1", "узкое место 2"],
                        "optimization_opportunities": ["возможность оптимизации 1", "возможность оптимизации 2"]
                    }}
                ]
            }},
            "predictive_insights": {{
                "short_term_predictions": [
                    {{
                        "prediction": "краткосрочный прогноз",
                        "timeframe": "временные рамки",
                        "probability": "вероятность",
                        "impact": "влияние",
                        "confidence_interval": "доверительный интервал",
                        "key_indicators": ["индикатор 1", "индикатор 2"]
                    }}
                ],
                "long_term_forecasts": [
                    {{
                        "forecast": "долгосрочный прогноз",
                        "timeframe": "временные рамки",
                        "scenario": "оптимистичный/реалистичный/пессимистичный",
                        "assumptions": ["предположение 1", "предположение 2"],
                        "potential_interventions": ["вмешательство 1", "вмешательство 2"]
                    }}
                ],
                "risk_projections": [
                    {{
                        "risk": "прогнозируемый риск",
                        "probability": "вероятность реализации",
                        "timeline": "временные рамки",
                        "mitigation_strategies": ["стратегия снижения 1", "стратегия снижения 2"],
                        "monitoring_indicators": ["индикатор мониторинга 1", "индикатор мониторинга 2"]
                    }}
                ]
            }},
            "quality_metrics": {{
                "data_quality_assessment": {{
                    "completeness": "процент полноты данных",
                    "accuracy": "оценка точности",
                    "consistency": "оценка согласованности",
                    "timeliness": "оценка своевременности",
                    "reliability": "оценка надежности"
                }},
                "analysis_confidence": {{
                    "statistical_power": "статистическая мощность",
                    "sample_representativeness": "представительность выборки",
                    "bias_assessment": "оценка смещений",
                    "uncertainty_factors": ["фактор неопределенности 1", "фактор неопределенности 2"]
                }}
            }},
            "actionable_recommendations": [
                {{
                    "recommendation": "практическая рекомендация",
                    "priority": "высокий/средний/низкий",
                    "implementation_complexity": "сложность внедрения",
                    "expected_impact": "ожидаемое влияние",
                    "resource_requirements": ["требуемый ресурс 1", "требуемый ресурс 2"],
                    "timeline": "временные рамки внедрения",
                    "success_metrics": ["метрика успеха 1", "метрика успеха 2"],
                    "risk_mitigation": ["снижение риска 1", "снижение риска 2"]
                }}
            ],
            "visualization_suggestions": [
                {{
                    "chart_type": "тип диаграммы",
                    "data_focus": "фокус данных",
                    "key_insights": ["ключевой инсайт 1", "ключевой инсайт 2"],
                    "interactive_elements": ["интерактивный элемент 1", "интерактивный элемент 2"]
                }}
            ]
        }}
        """

        system_prompt = """Вы эксперт по медицинской аналитике и анализу данных с глубокими знаниями в области эпидемиологии, биостатистики и здравоохранения.
        Анализируете медицинские тренды, выявляете паттерны и предоставляете практические инсайты для улучшения качества медицинской помощи.
        Используете современные методы анализа данных и машинного обучения для выявления скрытых закономерностей.
        Предоставляете статистически обоснованные выводы с учетом клинической значимости.
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


    async def detect_anomalies(
        self, dataset: list[dict], baseline_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Выявление аномалий в медицинских данных"""
        # Ограничиваем данные для анализа
        data_sample = dataset[:50] if len(dataset) > 50 else dataset

        dataset_summary = {
            "total_records": len(dataset),
            "sample_size": len(data_sample),
            "data_fields": (
                list(set().union(*[record.keys() for record in data_sample]))
                if data_sample
                else []
            ),
            "record_types": list(
                {record.get("type", "unknown") for record in data_sample}
            ),
        }

        sample_text = "\n".join(
            [
                f"- Record {i+1}: {json.dumps(record, ensure_ascii=False)}"
                for i, record in enumerate(data_sample[:10])
            ]
        )

        baseline_text = json.dumps(baseline_data, ensure_ascii=False, indent=2)

        prompt = f"""
        Выявите аномалии в медицинских данных по сравнению с базовыми показателями:

        БАЗОВЫЕ ДАННЫЕ:
        {baseline_text}

        АНАЛИЗИРУЕМЫЙ ДАТАСЕТ:
        Общее количество записей: {dataset_summary['total_records']}
        Размер выборки: {dataset_summary['sample_size']}
        Типы записей: {dataset_summary['record_types']}

        ОБРАЗЕЦ ДАННЫХ:
        {sample_text}

        Предоставьте анализ аномалий в формате JSON:
        {{
            "anomaly_detection": {{
                "detection_summary": {{
                    "total_anomalies": "количество выявленных аномалий",
                    "anomaly_rate": "процент аномальных записей",
                    "severity_distribution": {{
                        "critical": "количество критических аномалий",
                        "high": "количество высокоприоритетных аномалий",
                        "medium": "количество среднеприоритетных аномалий",
                        "low": "количество низкоприоритетных аномалий"
                    }},
                    "detection_confidence": "уровень уверенности в детекции"
                }},
                "statistical_anomalies": [
                    {{
                        "field": "поле данных",
                        "anomaly_type": "выброс/тренд/паттерн",
                        "description": "описание аномалии",
                        "baseline_value": "базовое значение",
                        "observed_value": "наблюдаемое значение",
                        "deviation": "степень отклонения",
                        "statistical_significance": "статистическая значимость",
                        "z_score": "z-оценка",
                        "p_value": "p-значение"
                    }}
                ],
                "clinical_anomalies": [
                    {{
                        "anomaly": "клиническая аномалия",
                        "clinical_significance": "клиническая значимость",
                        "patient_safety_impact": "влияние на безопасность пациента",
                        "frequency": "частота встречаемости",
                        "associated_conditions": ["связанное состояние 1", "связанное состояние 2"],
                        "investigation_priority": "приоритет расследования",
                        "recommended_actions": ["рекомендуемое действие 1", "рекомендуемое действие 2"]
                    }}
                ],
                "temporal_anomalies": [
                    {{
                        "time_period": "временной период",
                        "anomaly_description": "описание временной аномалии",
                        "expected_pattern": "ожидаемый паттерн",
                        "observed_pattern": "наблюдаемый паттерн",
                        "seasonal_adjustment": "сезонная корректировка",
                        "trend_deviation": "отклонение от тренда",
                        "cyclical_analysis": "циклический анализ"
                    }}
                ]
            }},
            "root_cause_analysis": [
                {{
                    "anomaly": "аномалия для анализа",
                    "potential_causes": [
                        {{
                            "cause": "потенциальная причина",
                            "probability": "вероятность",
                            "evidence": ["доказательство 1", "доказательство 2"],
                            "impact_assessment": "оценка влияния",
                            "verification_methods": ["метод проверки 1", "метод проверки 2"]
                        }}
                    ],
                    "contributing_factors": ["способствующий фактор 1", "способствующий фактор 2"],
                    "system_factors": ["системный фактор 1", "системный фактор 2"],
                    "human_factors": ["человеческий фактор 1", "человеческий фактор 2"]
                }}
            ],
            "impact_assessment": {{
                "patient_impact": [
                    {{
                        "impact_type": "тип влияния на пациента",
                        "severity": "тяжесть",
                        "affected_population": "затронутая популяция",
                        "immediate_risks": ["немедленный риск 1", "немедленный риск 2"],
                        "long_term_consequences": ["долгосрочное последствие 1", "долгосрочное последствие 2"]
                    }}
                ],
                "operational_impact": [
                    {{
                        "area": "операционная область",
                        "impact_description": "описание влияния",
                        "resource_implications": ["влияние на ресурсы 1", "влияние на ресурсы 2"],
                        "workflow_disruption": "нарушение рабочего процесса",
                        "cost_implications": "финансовые последствия"
                    }}
                ],
                "quality_impact": [
                    {{
                        "quality_metric": "метрика качества",
                        "baseline_performance": "базовая производительность",
                        "current_performance": "текущая производительность",
                        "performance_gap": "разрыв в производительности",
                        "improvement_potential": "потенциал улучшения"
                    }}
                ]
            }},
            "corrective_actions": [
                {{
                    "action": "корректирующее действие",
                    "urgency": "срочность",
                    "responsible_party": "ответственная сторона",
                    "implementation_timeline": "график внедрения",
                    "resource_requirements": ["требуемый ресурс 1", "требуемый ресурс 2"],
                    "success_criteria": ["критерий успеха 1", "критерий успеха 2"],
                    "monitoring_plan": "план мониторинга",
                    "risk_mitigation": ["снижение риска 1", "снижение риска 2"]
                }}
            ],
            "prevention_strategies": [
                {{
                    "strategy": "стратегия предотвращения",
                    "target_anomaly_type": "тип целевой аномалии",
                    "implementation_approach": "подход к внедрению",
                    "early_warning_indicators": ["индикатор раннего предупреждения 1", "индикатор раннего предупреждения 2"],
                    "monitoring_frequency": "частота мониторинга",
                    "alert_thresholds": ["пороговое значение 1", "пороговое значение 2"]
                }}
            ],
            "continuous_monitoring": {{
                "monitoring_framework": {{
                    "key_metrics": ["ключевая метрика 1", "ключевая метрика 2"],
                    "data_sources": ["источник данных 1", "источник данных 2"],
                    "analysis_frequency": "частота анализа",
                    "reporting_schedule": "график отчетности",
                    "escalation_procedures": ["процедура эскалации 1", "процедура эскалации 2"]
                }},
                "automated_detection": {{
                    "algorithm_recommendations": ["рекомендация алгоритма 1", "рекомендация алгоритма 2"],
                    "threshold_settings": ["настройка порога 1", "настройка порога 2"],
                    "false_positive_management": "управление ложными срабатываниями",
                    "model_updating_strategy": "стратегия обновления модели"
                }}
            }}
        }}
        """

        system_prompt = """Вы специалист по выявлению аномалий в медицинских данных с экспертизой в области статистического анализа и машинного обучения.
        Анализируете медицинские данные для выявления отклонений от нормы, статистических выбросов и необычных паттернов.
        Оцениваете клиническую значимость аномалий и их влияние на безопасность пациентов и качество медицинской помощи.
        Предоставляете практические рекомендации по корректирующим действиям и предотвращению аномалий.
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


    async def predict_outcomes(
        self, patient_data: dict[str, Any], historical_outcomes: list[dict]
    ) -> dict[str, Any]:
        """Прогнозирование медицинских исходов на основе данных"""
        patient_text = json.dumps(patient_data, ensure_ascii=False, indent=2)

        # Ограничиваем исторические данные
        outcomes_sample = (
            historical_outcomes[:30]
            if len(historical_outcomes) > 30
            else historical_outcomes
        )
        outcomes_summary = {
            "total_cases": len(historical_outcomes),
            "sample_size": len(outcomes_sample),
            "outcome_types": list(
                {outcome.get("result", "unknown") for outcome in outcomes_sample}
            ),
            "success_rate": (
                len([o for o in outcomes_sample if o.get("result") == "success"])
                / len(outcomes_sample)
                * 100
                if outcomes_sample
                else 0
            ),
        }

        outcomes_text = "\n".join(
            [
                f"- Case {i+1}: {outcome.get('condition', 'N/A')} → {outcome.get('result', 'N/A')} (duration: {outcome.get('duration', 'N/A')})"
                for i, outcome in enumerate(outcomes_sample[:15])
            ]
        )

        prompt = f"""
        Спрогнозируйте медицинские исходы для пациента на основе исторических данных:

        ДАННЫЕ ПАЦИЕНТА:
        {patient_text}

        ИСТОРИЧЕСКИЕ ИСХОДЫ:
        Общее количество случаев: {outcomes_summary['total_cases']}
        Размер выборки: {outcomes_summary['sample_size']}
        Типы исходов: {outcomes_summary['outcome_types']}
        Общий процент успеха: {outcomes_summary['success_rate']:.1f}%

        ОБРАЗЕЦ ИСТОРИЧЕСКИХ СЛУЧАЕВ:
        {outcomes_text}

        Предоставьте прогноз исходов в формате JSON:
        {{
            "outcome_predictions": {{
                "primary_prediction": {{
                    "predicted_outcome": "основной прогнозируемый исход",
                    "probability": "вероятность в процентах",
                    "confidence_level": "уровень уверенности",
                    "time_to_outcome": "время до исхода",
                    "key_factors": ["ключевой фактор 1", "ключевой фактор 2"],
                    "risk_stratification": "низкий/средний/высокий риск"
                }},
                "alternative_scenarios": [
                    {{
                        "scenario": "альтернативный сценарий",
                        "probability": "вероятность",
                        "conditions": ["условие 1", "условие 2"],
                        "timeline": "временные рамки",
                        "intervention_requirements": ["требуемое вмешательство 1", "требуемое вмешательство 2"]
                    }}
                ],
                "worst_case_scenario": {{
                    "outcome": "наихудший исход",
                    "probability": "вероятность",
                    "warning_signs": ["предупреждающий знак 1", "предупреждающий знак 2"],
                    "prevention_strategies": ["стратегия предотвращения 1", "стратегия предотвращения 2"],
                    "emergency_protocols": ["протокол экстренной помощи 1", "протокол экстренной помощи 2"]
                }},
                "best_case_scenario": {{
                    "outcome": "наилучший исход",
                    "probability": "вероятность",
                    "success_factors": ["фактор успеха 1", "фактор успеха 2"],
                    "optimization_strategies": ["стратегия оптимизации 1", "стратегия оптимизации 2"],
                    "maintenance_requirements": ["требование поддержания 1", "требование поддержания 2"]
                }}
            }},
            "prognostic_factors": {{
                "positive_prognostic_factors": [
                    {{
                        "factor": "положительный прогностический фактор",
                        "impact_strength": "сильное/умеренное/слабое влияние",
                        "evidence_level": "уровень доказательности",
                        "modifiability": "модифицируемый/немодифицируемый",
                        "optimization_potential": "потенциал оптимизации"
                    }}
                ],
                "negative_prognostic_factors": [
                    {{
                        "factor": "отрицательный прогностический фактор",
                        "risk_magnitude": "величина риска",
                        "mitigation_strategies": ["стратегия снижения 1", "стратегия снижения 2"],
                        "monitoring_requirements": ["требование мониторинга 1", "требование мониторинга 2"],
                        "intervention_timing": "время вмешательства"
                    }}
                ],
                "neutral_factors": [
                    {{
                        "factor": "нейтральный фактор",
                        "monitoring_value": "ценность мониторинга",
                        "potential_changes": ["потенциальное изменение 1", "потенциальное изменение 2"]
                    }}
                ]
            }},
            "treatment_response_prediction": {{
                "expected_response": {{
                    "response_type": "тип ответа на лечение",
                    "response_timeline": "временные рамки ответа",
                    "response_magnitude": "величина ответа",
                    "response_durability": "длительность ответа",
                    "side_effect_profile": "профиль побочных эффектов"
                }},
                "treatment_modifications": [
                    {{
                        "modification": "модификация лечения",
                        "indication": "показание для модификации",
                        "expected_benefit": "ожидаемая польза",
                        "implementation_timing": "время внедрения",
                        "monitoring_parameters": ["параметр мониторинга 1", "параметр мониторинга 2"]
                    }}
                ],
                "resistance_patterns": [
                    {{
                        "resistance_type": "тип резистентности",
                        "probability": "вероятность развития",
                        "early_indicators": ["ранний индикатор 1", "ранний индикатор 2"],
                        "management_strategies": ["стратегия управления 1", "стратегия управления 2"]
                    }}
                ]
            }},
            "quality_of_life_prediction": {{
                "functional_outcomes": [
                    {{
                        "domain": "функциональная область",
                        "predicted_level": "прогнозируемый уровень",
                        "improvement_potential": "потенциал улучшения",
                        "rehabilitation_needs": ["потребность в реабилитации 1", "потребность в реабилитации 2"],
                        "adaptive_strategies": ["адаптивная стратегия 1", "адаптивная стратегия 2"]
                    }}
                ],
                "psychosocial_outcomes": [
                    {{
                        "aspect": "психосоциальный аспект",
                        "predicted_impact": "прогнозируемое влияние",
                        "support_needs": ["потребность в поддержке 1", "потребность в поддержке 2"],
                        "coping_strategies": ["стратегия совладания 1", "стратегия совладания 2"]
                    }}
                ]
            }},
            "long_term_prognosis": {{
                "5_year_outlook": {{
                    "survival_probability": "вероятность выживания",
                    "disease_progression": "прогрессирование заболевания",
                    "functional_status": "функциональный статус",
                    "quality_of_life": "качество жизни",
                    "care_requirements": ["требование к уходу 1", "требование к уходу 2"]
                }},
                "10_year_outlook": {{
                    "survival_probability": "вероятность выживания",
                    "disease_progression": "прогрессирование заболевания",
                    "functional_status": "функциональный статус",
                    "quality_of_life": "качество жизни",
                    "care_requirements": ["требование к уходу 1", "требование к уходу 2"]
                }},
                "lifetime_considerations": [
                    {{
                        "consideration": "пожизненное соображение",
                        "impact": "влияние",
                        "management_approach": "подход к управлению",
                        "family_implications": ["влияние на семью 1", "влияние на семью 2"]
                    }}
                ]
            }},
            "monitoring_recommendations": {{
                "immediate_monitoring": [
                    {{
                        "parameter": "параметр немедленного мониторинга",
                        "frequency": "частота",
                        "alert_thresholds": ["пороговое значение 1", "пороговое значение 2"],
                        "action_triggers": ["триггер действия 1", "триггер действия 2"]
                    }}
                ],
                "long_term_surveillance": [
                    {{
                        "surveillance_type": "тип долгосрочного наблюдения",
                        "schedule": "график",
                        "key_indicators": ["ключевой индикатор 1", "ключевой индикатор 2"],
                        "screening_protocols": ["протокол скрининга 1", "протокол скрининга 2"]
                    }}
                ]
            }},
            "uncertainty_analysis": {{
                "confidence_intervals": [
                    {{
                        "prediction": "прогноз",
                        "lower_bound": "нижняя граница",
                        "upper_bound": "верхняя граница",
                        "confidence_level": "уровень доверия"
                    }}
                ],
                "sensitivity_analysis": [
                    {{
                        "variable": "переменная",
                        "impact_on_prediction": "влияние на прогноз",
                        "uncertainty_contribution": "вклад в неопределенность"
                    }}
                ],
                "model_limitations": ["ограничение модели 1", "ограничение модели 2"],
                "data_quality_factors": ["фактор качества данных 1", "фактор качества данных 2"]
            }}
        }}
        """

        system_prompt = """Вы эксперт по прогнозированию медицинских исходов с глубокими знаниями в области клинической медицины, биостатистики и прогностического моделирования.
        Анализируете данные пациентов и исторические исходы для создания точных и клинически значимых прогнозов.
        Учитываете множественные факторы риска, коморбидности и индивидуальные особенности пациентов.
        Предоставляете вероятностные оценки с указанием уровня уверенности и клинических рекомендаций.
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


    async def generate_insights_report(
        self, analytics_data: dict[str, Any], report_type: str
    ) -> dict[str, Any]:
        """Генерация отчета с аналитическими инсайтами"""
        analytics_text = json.dumps(analytics_data, ensure_ascii=False, indent=2)

        prompt = f"""
        Сгенерируйте комплексный отчет с аналитическими инсайтами на основе предоставленных данных:

        ТИП ОТЧЕТА: {report_type}

        АНАЛИТИЧЕСКИЕ ДАННЫЕ:
        {analytics_text}

        Создайте структурированный отчет в формате JSON:
        {{
            "executive_summary": {{
                "report_title": "название отчета",
                "report_period": "период отчета",
                "key_findings": [
                    {{
                        "finding": "ключевая находка",
                        "significance": "значимость",
                        "impact": "влияние",
                        "confidence": "уровень уверенности"
                    }}
                ],
                "critical_insights": [
                    {{
                        "insight": "критический инсайт",
                        "implication": "последствие",
                        "urgency": "срочность",
                        "recommended_action": "рекомендуемое действие"
                    }}
                ],
                "overall_assessment": "общая оценка ситуации",
                "strategic_recommendations": ["стратегическая рекомендация 1", "стратегическая рекомендация 2"]
            }},
            "detailed_analysis": {{
                "performance_metrics": [
                    {{
                        "metric": "показатель производительности",
                        "current_value": "текущее значение",
                        "benchmark": "эталонное значение",
                        "trend": "тренд",
                        "variance_analysis": "анализ отклонений",
                        "improvement_opportunities": ["возможность улучшения 1", "возможность улучшения 2"]
                    }}
                ],
                "comparative_analysis": [
                    {{
                        "comparison_dimension": "измерение сравнения",
                        "baseline": "базовая линия",
                        "current_state": "текущее состояние",
                        "performance_gap": "разрыв в производительности",
                        "root_causes": ["основная причина 1", "основная причина 2"],
                        "corrective_actions": ["корректирующее действие 1", "корректирующее действие 2"]
                    }}
                ],
                "trend_analysis": [
                    {{
                        "trend": "тренд",
                        "direction": "направление",
                        "velocity": "скорость изменения",
                        "sustainability": "устойчивость",
                        "influencing_factors": ["влияющий фактор 1", "влияющий фактор 2"],
                        "projection": "прогноз"
                    }}
                ]
            }},
            "clinical_insights": {{
                "patient_outcomes": [
                    {{
                        "outcome_category": "категория исхода",
                        "performance_indicator": "индикатор производительности",
                        "clinical_significance": "клиническая значимость",
                        "quality_impact": "влияние на качество",
                        "safety_implications": ["влияние на безопасность 1", "влияние на безопасность 2"],
                        "improvement_strategies": ["стратегия улучшения 1", "стратегия улучшения 2"]
                    }}
                ],
                "care_quality_indicators": [
                    {{
                        "indicator": "индикатор качества помощи",
                        "measurement": "измерение",
                        "target": "целевое значение",
                        "achievement": "достижение",
                        "gap_analysis": "анализ пробелов",
                        "quality_initiatives": ["инициатива качества 1", "инициатива качества 2"]
                    }}
                ],
                "patient_safety_metrics": [
                    {{
                        "safety_metric": "метрика безопасности",
                        "incident_rate": "частота инцидентов",
                        "severity_distribution": "распределение по тяжести",
                        "prevention_effectiveness": "эффективность предотвращения",
                        "risk_mitigation": ["снижение риска 1", "снижение риска 2"]
                    }}
                ]
            }},
            "operational_insights": {{
                "resource_utilization": [
                    {{
                        "resource": "ресурс",
                        "utilization_rate": "коэффициент использования",
                        "efficiency_score": "оценка эффективности",
                        "bottlenecks": ["узкое место 1", "узкое место 2"],
                        "optimization_potential": "потенциал оптимизации",
                        "capacity_planning": ["планирование мощности 1", "планирование мощности 2"]
                    }}
                ],
                "workflow_analysis": [
                    {{
                        "process": "процесс",
                        "cycle_time": "время цикла",
                        "throughput": "пропускная способность",
                        "quality_metrics": ["метрика качества 1", "метрика качества 2"],
                        "improvement_areas": ["область улучшения 1", "область улучшения 2"],
                        "automation_opportunities": ["возможность автоматизации 1", "возможность автоматизации 2"]
                    }}
                ],
                "cost_effectiveness": [
                    {{
                        "cost_center": "центр затрат",
                        "cost_per_unit": "стоимость за единицу",
                        "value_delivered": "доставленная ценность",
                        "roi_analysis": "анализ ROI",
                        "cost_optimization": ["оптимизация затрат 1", "оптимизация затрат 2"],
                        "investment_priorities": ["приоритет инвестиций 1", "приоритет инвестиций 2"]
                    }}
                ]
            }},
            "predictive_insights": {{
                "forecasting_models": [
                    {{
                        "model": "прогностическая модель",
                        "prediction_horizon": "горизонт прогнозирования",
                        "accuracy_metrics": "метрики точности",
                        "key_variables": ["ключевая переменная 1", "ключевая переменная 2"],
                        "scenario_analysis": ["анализ сценария 1", "анализ сценария 2"],
                        "confidence_intervals": "доверительные интервалы"
                    }}
                ],
                "risk_predictions": [
                    {{
                        "risk_category": "категория риска",
                        "probability": "вероятность",
                        "impact_assessment": "оценка влияния",
                        "early_warning_indicators": ["индикатор раннего предупреждения 1", "индикатор раннего предупреждения 2"],
                        "mitigation_strategies": ["стратегия снижения 1", "стратегия снижения 2"],
                        "contingency_plans": ["план на случай непредвиденных обстоятельств 1", "план на случай непредвиденных обстоятельств 2"]
                    }}
                ]
            }},
            "actionable_recommendations": {{
                "immediate_actions": [
                    {{
                        "action": "немедленное действие",
                        "priority": "приоритет",
                        "responsible_party": "ответственная сторона",
                        "timeline": "временные рамки",
                        "resource_requirements": ["требуемый ресурс 1", "требуемый ресурс 2"],
                        "success_metrics": ["метрика успеха 1", "метрика успеха 2"],
                        "risk_assessment": "оценка риска"
                    }}
                ],
                "short_term_initiatives": [
                    {{
                        "initiative": "краткосрочная инициатива",
                        "objective": "цель",
                        "implementation_plan": "план внедрения",
                        "expected_outcomes": ["ожидаемый результат 1", "ожидаемый результат 2"],
                        "key_milestones": ["ключевая веха 1", "ключевая веха 2"],
                        "monitoring_framework": "система мониторинга"
                    }}
                ],
                "long_term_strategies": [
                    {{
                        "strategy": "долгосрочная стратегия",
                        "strategic_goal": "стратегическая цель",
                        "implementation_roadmap": "дорожная карта внедрения",
                        "investment_requirements": ["требование к инвестициям 1", "требование к инвестициям 2"],
                        "expected_roi": "ожидаемый ROI",
                        "success_factors": ["фактор успеха 1", "фактор успеха 2"]
                    }}
                ]
            }},
            "quality_assurance": {{
                "data_quality_assessment": {{
                    "completeness": "полнота данных",
                    "accuracy": "точность данных",
                    "consistency": "согласованность данных",
                    "timeliness": "своевременность данных",
                    "reliability": "надежность данных"
                }},
                "analysis_limitations": [
                    {{
                        "limitation": "ограничение анализа",
                        "impact": "влияние на результаты",
                        "mitigation": "способ снижения влияния",
                        "future_improvements": ["будущее улучшение 1", "будущее улучшение 2"]
                    }}
                ],
                "confidence_assessment": {{
                    "overall_confidence": "общий уровень уверенности",
                    "high_confidence_findings": ["находка с высокой уверенностью 1", "находка с высокой уверенностью 2"],
                    "moderate_confidence_findings": ["находка со средней уверенностью 1", "находка со средней уверенностью 2"],
                    "low_confidence_findings": ["находка с низкой уверенностью 1", "находка с низкой уверенностью 2"],
                    "uncertainty_factors": ["фактор неопределенности 1", "фактор неопределенности 2"]
                }}
            }},
            "appendices": {{
                "methodology": {{
                    "analytical_approach": "аналитический подход",
                    "data_sources": ["источник данных 1", "источник данных 2"],
                    "statistical_methods": ["статистический метод 1", "статистический метод 2"],
                    "assumptions": ["предположение 1", "предположение 2"],
                    "validation_procedures": ["процедура валидации 1", "процедура валидации 2"]
                }},
                "glossary": [
                    {{
                        "term": "термин",
                        "definition": "определение"
                    }}
                ],
                "references": [
                    {{
                        "reference": "ссылка на источник",
                        "relevance": "актуальность для анализа"
                    }}
                ]
            }}
        }}
        """

        system_prompt = """Вы эксперт по созданию аналитических отчетов в здравоохранении с глубокими знаниями в области медицинской аналитики, управления качеством и стратегического планирования.
        Создаете комплексные, структурированные отчеты с практическими инсайтами и рекомендациями для руководства медицинских учреждений.
        Анализируете данные с точки зрения клинической эффективности, операционной эффективности и финансовой устойчивости.
        Предоставляете четкие, обоснованные выводы с указанием уровня уверенности и практических шагов для внедрения.
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


    async def identify_risk_patterns(
        self, population_data: list[dict], risk_factors: list[str]
    ) -> dict[str, Any]:
        """Выявление паттернов рисков в популяционных данных"""
        # Ограничиваем данные для анализа
        data_sample = (
            population_data[:100] if len(population_data) > 100 else population_data
        )

        population_summary = {
            "total_population": len(population_data),
            "sample_size": len(data_sample),
            "age_groups": list(
                {p.get("age_group", "unknown") for p in data_sample}
            ),
            "gender_distribution": {
                "male": len([p for p in data_sample if p.get("gender") == "male"]),
                "female": len([p for p in data_sample if p.get("gender") == "female"]),
            },
            "risk_factors_analyzed": risk_factors,
        }

        sample_text = "\n".join(
            [
                f"- Patient {i+1}: Age {p.get('age', 'N/A')}, Gender {p.get('gender', 'N/A')}, Conditions: {p.get('conditions', [])}"
                for i, p in enumerate(data_sample[:15])
            ]
        )

        risk_factors_text = ", ".join(risk_factors)

        prompt = f"""
        Выявите паттерны рисков в популяционных медицинских данных:

        АНАЛИЗИРУЕМЫЕ ФАКТОРЫ РИСКА: {risk_factors_text}

        ПОПУЛЯЦИОННЫЕ ДАННЫЕ:
        Общая популяция: {population_summary['total_population']} человек
        Размер выборки: {population_summary['sample_size']} человек
        Возрастные группы: {population_summary['age_groups']}
        Распределение по полу: М={population_summary['gender_distribution']['male']}, Ж={population_summary['gender_distribution']['female']}

        ОБРАЗЕЦ ДАННЫХ:
        {sample_text}

        Предоставьте анализ паттернов рисков в формате JSON:
        {{
            "risk_pattern_analysis": {{
                "population_overview": {{
                    "total_analyzed": {population_summary['total_population']},
                    "high_risk_percentage": "процент высокого риска",
                    "moderate_risk_percentage": "процент умеренного риска",
                    "low_risk_percentage": "процент низкого риска",
                    "risk_distribution_trend": "тренд распределения рисков"
                }},
                "demographic_risk_patterns": [
                    {{
                        "demographic": "демографическая группа",
                        "risk_level": "уровень риска",
                        "prevalence": "распространенность",
                        "key_risk_factors": ["ключевой фактор риска 1", "ключевой фактор риска 2"],
                        "protective_factors": ["защитный фактор 1", "защитный фактор 2"],
                        "intervention_priorities": ["приоритет вмешательства 1", "приоритет вмешательства 2"]
                    }}
                ],
                "geographic_patterns": [
                    {{
                        "region": "регион",
                        "risk_concentration": "концентрация риска",
                        "environmental_factors": ["фактор окружающей среды 1", "фактор окружающей среды 2"],
                        "socioeconomic_influences": ["социально-экономическое влияние 1", "социально-экономическое влияние 2"],
                        "healthcare_access": "доступность медицинской помощи",
                        "targeted_interventions": ["целевое вмешательство 1", "целевое вмешательство 2"]
                    }}
                ]
            }},
            "risk_factor_analysis": [
                {{
                    "risk_factor": "фактор риска",
                    "population_prevalence": "распространенность в популяции",
                    "relative_risk": "относительный риск",
                    "attributable_risk": "атрибутивный риск",
                    "modifiability": "модифицируемость",
                    "intervention_effectiveness": "эффективность вмешательства",
                    "cost_benefit_ratio": "соотношение затрат и выгод",
                    "population_impact": "влияние на популяцию",
                    "synergistic_effects": [
                        {{
                            "interacting_factor": "взаимодействующий фактор",
                            "combined_effect": "комбинированный эффект",
                            "risk_amplification": "усиление риска"
                        }}
                    ]
                }}
            ],
            "temporal_patterns": {{
                "seasonal_variations": [
                    {{
                        "risk_factor": "фактор риска",
                        "seasonal_pattern": "сезонный паттерн",
                        "peak_periods": ["пиковый период 1", "пиковый период 2"],
                        "cyclical_trends": "циклические тренды",
                        "environmental_correlations": ["корреляция с окружающей средой 1", "корреляция с окружающей средой 2"]
                    }}
                ],
                "age_related_patterns": [
                    {{
                        "age_group": "возрастная группа",
                        "risk_trajectory": "траектория риска",
                        "critical_periods": ["критический период 1", "критический период 2"],
                        "developmental_factors": ["фактор развития 1", "фактор развития 2"],
                        "prevention_windows": ["окно профилактики 1", "окно профилактики 2"]
                    }}
                ],
                "cohort_effects": [
                    {{
                        "birth_cohort": "когорта рождения",
                        "unique_exposures": ["уникальное воздействие 1", "уникальное воздействие 2"],
                        "risk_profile": "профиль риска",
                        "long_term_implications": ["долгосрочное последствие 1", "долгосрочное последствие 2"]
                    }}
                ]
            }},
            "clustering_analysis": {{
                "risk_clusters": [
                    {{
                        "cluster_id": "идентификатор кластера",
                        "cluster_characteristics": "характеристики кластера",
                        "population_size": "размер популяции",
                        "dominant_risk_factors": ["доминирующий фактор риска 1", "доминирующий фактор риска 2"],
                        "cluster_stability": "стабильность кластера",
                        "intervention_strategies": ["стратегия вмешательства 1", "стратегия вмешательства 2"]
                    }}
                ],
                "outlier_populations": [
                    {{
                        "population": "популяция-выброс",
                        "unique_characteristics": ["уникальная характеристика 1", "уникальная характеристика 2"],
                        "risk_anomalies": ["аномалия риска 1", "аномалия риска 2"],
                        "special_considerations": ["особое соображение 1", "особое соображение 2"]
                    }}
                ]
            }},
            "predictive_modeling": {{
                "risk_prediction_models": [
                    {{
                        "model_type": "тип модели",
                        "predictive_accuracy": "точность прогнозирования",
                        "key_predictors": ["ключевой предиктор 1", "ключевой предиктор 2"],
                        "model_validation": "валидация модели",
                        "clinical_utility": "клиническая полезность",
                        "implementation_feasibility": "осуществимость внедрения"
                    }}
                ],
                "early_warning_systems": [
                    {{
                        "system": "система раннего предупреждения",
                        "trigger_conditions": ["условие срабатывания 1", "условие срабатывания 2"],
                        "sensitivity": "чувствительность",
                        "specificity": "специфичность",
                        "alert_protocols": ["протокол предупреждения 1", "протокол предупреждения 2"]
                    }}
                ]
            }},
            "intervention_recommendations": {{
                "population_level_interventions": [
                    {{
                        "intervention": "популяционное вмешательство",
                        "target_population": "целевая популяция",
                        "implementation_strategy": "стратегия внедрения",
                        "expected_impact": "ожидаемое влияние",
                        "cost_effectiveness": "экономическая эффективность",
                        "feasibility_assessment": "оценка осуществимости",
                        "monitoring_indicators": ["индикатор мониторинга 1", "индикатор мониторинга 2"]
                    }}
                ],
                "targeted_interventions": [
                    {{
                        "intervention": "целевое вмешательство",
                        "high_risk_criteria": ["критерий высокого риска 1", "критерий высокого риска 2"],
                        "intervention_intensity": "интенсивность вмешательства",
                        "personalization_factors": ["фактор персонализации 1", "фактор персонализации 2"],
                        "delivery_mechanisms": ["механизм доставки 1", "механизм доставки 2"]
                    }}
                ],
                "policy_recommendations": [
                    {{
                        "policy_area": "область политики",
                        "recommended_changes": ["рекомендуемое изменение 1", "рекомендуемое изменение 2"],
                        "evidence_base": "доказательная база",
                        "stakeholder_engagement": "вовлечение заинтересованных сторон",
                        "implementation_barriers": ["барьер внедрения 1", "барьер внедрения 2"],
                        "success_factors": ["фактор успеха 1", "фактор успеха 2"]
                    }}
                ]
            }},
            "monitoring_framework": {{
                "surveillance_systems": [
                    {{
                        "system": "система наблюдения",
                        "data_sources": ["источник данных 1", "источник данных 2"],
                        "collection_frequency": "частота сбора",
                        "quality_indicators": ["индикатор качества 1", "индикатор качества 2"],
                        "reporting_mechanisms": ["механизм отчетности 1", "механизм отчетности 2"]
                    }}
                ],
                "performance_metrics": [
                    {{
                        "metric": "показатель производительности",
                        "measurement_method": "метод измерения",
                        "target_values": ["целевое значение 1", "целевое значение 2"],
                        "benchmarking": "бенчмаркинг",
                        "improvement_tracking": "отслеживание улучшений"
                    }}
                ]
            }},
            "research_priorities": [
                {{
                    "research_question": "исследовательский вопрос",
                    "knowledge_gap": "пробел в знаниях",
                    "research_design": "дизайн исследования",
                    "expected_outcomes": ["ожидаемый результат 1", "ожидаемый результат 2"],
                    "clinical_impact": "клиническое влияние",
                    "policy_implications": ["влияние на политику 1", "влияние на политику 2"]
                }}
            ]
        }}
        """

        system_prompt = """Вы эксперт по эпидемиологии и анализу рисков в здравоохранении с глубокими знаниями в области популяционной медицины, биостатистики и общественного здравоохранения.
        Анализируете популяционные данные для выявления паттернов рисков, факторов риска и разработки стратегий профилактики.
        Используете современные методы анализа данных и машинного обучения для выявления скрытых закономерностей в здоровье популяций.
        Предоставляете практические рекомендации по вмешательствам на популяционном уровне и политике здравоохранения.
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


