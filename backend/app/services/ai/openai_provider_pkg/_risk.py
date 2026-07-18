"""Risk mixin for OpenAIProvider.

Split from openai_provider.py.
"""
from __future__ import annotations

from app.services.ai.openai_provider_pkg._base import (
    AIRequest,
    Any,
    OpenAIProviderMixinBase,
    json,
)


class RiskMixin(OpenAIProviderMixinBase):
    """Risk methods for OpenAIProvider."""

    async def assess_patient_risk(
        self, patient_data: dict[str, Any], risk_factors: list[str], condition: str
    ) -> dict[str, Any]:
        """Комплексная оценка рисков пациента"""
        age = patient_data.get("age", "не указан")
        gender = patient_data.get("gender", "не указан")
        weight = patient_data.get("weight", "не указан")
        height = patient_data.get("height", "не указан")
        bmi = patient_data.get("bmi", "не указан")
        smoking_status = patient_data.get("smoking_status", "не указан")
        alcohol_consumption = patient_data.get("alcohol_consumption", "не указано")
        comorbidities = patient_data.get("comorbidities", [])
        medications = patient_data.get("medications", [])
        family_history = patient_data.get("family_history", [])

        risk_factors_text = ", ".join(risk_factors) if risk_factors else "не указаны"
        comorbidities_text = ", ".join(comorbidities) if comorbidities else "не указаны"
        medications_text = (
            ", ".join([med.get("name", "не указано") for med in medications])
            if medications
            else "не указаны"
        )
        family_history_text = (
            ", ".join(family_history) if family_history else "не указан"
        )

        prompt = f"""
        Проведите комплексную оценку рисков для пациента:

        ДАННЫЕ ПАЦИЕНТА:
        - Возраст: {age}
        - Пол: {gender}
        - Вес: {weight} кг
        - Рост: {height} см
        - ИМТ: {bmi}
        - Курение: {smoking_status}
        - Употребление алкоголя: {alcohol_consumption}
        - Сопутствующие заболевания: {comorbidities_text}
        - Текущие препараты: {medications_text}
        - Семейный анамнез: {family_history_text}

        СОСТОЯНИЕ/ЗАБОЛЕВАНИЕ: {condition}
        ФАКТОРЫ РИСКА: {risk_factors_text}

        Предоставьте детальную оценку рисков в формате JSON:
        {{
            "overall_risk_assessment": {{
                "risk_level": "низкий/умеренный/высокий/критический",
                "risk_score": "числовая оценка от 1 до 100",
                "confidence_level": "высокая/средняя/низкая",
                "assessment_date": "дата оценки"
            }},
            "risk_categories": {{
                "cardiovascular_risk": {{
                    "level": "низкий/умеренный/высокий/критический",
                    "score": "числовая оценка",
                    "contributing_factors": ["фактор 1", "фактор 2"],
                    "10_year_risk": "процент риска на 10 лет"
                }},
                "metabolic_risk": {{
                    "level": "низкий/умеренный/высокий/критический",
                    "score": "числовая оценка",
                    "contributing_factors": ["фактор 1", "фактор 2"],
                    "diabetes_risk": "процент риска развития диабета"
                }},
                "oncological_risk": {{
                    "level": "низкий/умеренный/высокий/критический",
                    "score": "числовая оценка",
                    "contributing_factors": ["фактор 1", "фактор 2"],
                    "screening_recommendations": ["рекомендация 1", "рекомендация 2"]
                }},
                "infectious_risk": {{
                    "level": "низкий/умеренный/высокий/критический",
                    "score": "числовая оценка",
                    "contributing_factors": ["фактор 1", "фактор 2"],
                    "vaccination_status": "актуальность вакцинации"
                }}
            }},
            "modifiable_risk_factors": [
                {{
                    "factor": "название фактора",
                    "current_status": "текущее состояние",
                    "target_value": "целевое значение",
                    "intervention": "рекомендуемое вмешательство",
                    "potential_risk_reduction": "потенциальное снижение риска в %"
                }}
            ],
            "non_modifiable_risk_factors": [
                {{
                    "factor": "название фактора",
                    "impact": "влияние на общий риск",
                    "management_strategy": "стратегия управления"
                }}
            ],
            "risk_stratification": {{
                "primary_prevention": {{
                    "applicable": true/false,
                    "recommendations": ["рекомендация 1", "рекомендация 2"],
                    "timeline": "временные рамки"
                }},
                "secondary_prevention": {{
                    "applicable": true/false,
                    "recommendations": ["рекомендация 1", "рекомендация 2"],
                    "timeline": "временные рамки"
                }}
            }},
            "monitoring_plan": {{
                "frequency": "частота наблюдения",
                "parameters": ["параметр 1", "параметр 2"],
                "laboratory_tests": ["анализ 1", "анализ 2"],
                "imaging_studies": ["исследование 1", "исследование 2"],
                "specialist_referrals": ["специалист 1", "специалист 2"]
            }},
            "risk_communication": {{
                "patient_friendly_explanation": "объяснение для пациента",
                "visual_aids": ["тип визуализации 1", "тип визуализации 2"],
                "key_messages": ["ключевое сообщение 1", "ключевое сообщение 2"]
            }},
            "emergency_indicators": [
                {{
                    "indicator": "тревожный признак",
                    "action": "необходимые действия",
                    "urgency": "немедленно/в течение часа/в течение дня"
                }}
            ]
        }}
        """

        system_prompt = """Вы врач-эпидемиолог и специалист по оценке рисков с экспертизой в профилактической медицине.
        Проводите комплексную оценку рисков на основе современных клинических рекомендаций и доказательной медицины.
        Учитываете все факторы риска, их взаимодействие и кумулятивный эффект.
        Предоставляете практические рекомендации по снижению рисков и мониторингу.
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


    async def predict_complications(
        self,
        patient_profile: dict[str, Any],
        procedure_or_condition: str,
        timeline: str,
    ) -> dict[str, Any]:
        """Прогнозирование возможных осложнений"""
        age = patient_profile.get("age", "не указан")
        gender = patient_profile.get("gender", "не указан")
        comorbidities = patient_profile.get("comorbidities", [])
        medications = patient_profile.get("medications", [])
        allergies = patient_profile.get("allergies", [])
        previous_complications = patient_profile.get("previous_complications", [])

        comorbidities_text = ", ".join(comorbidities) if comorbidities else "не указаны"
        medications_text = (
            ", ".join([med.get("name", "не указано") for med in medications])
            if medications
            else "не указаны"
        )
        allergies_text = ", ".join(allergies) if allergies else "не указаны"
        complications_text = (
            ", ".join(previous_complications)
            if previous_complications
            else "не указаны"
        )

        prompt = f"""
        Спрогнозируйте возможные осложнения для пациента:

        ПРОФИЛЬ ПАЦИЕНТА:
        - Возраст: {age}
        - Пол: {gender}
        - Сопутствующие заболевания: {comorbidities_text}
        - Текущие препараты: {medications_text}
        - Аллергии: {allergies_text}
        - Предыдущие осложнения: {complications_text}

        ПРОЦЕДУРА/СОСТОЯНИЕ: {procedure_or_condition}
        ВРЕМЕННЫЕ РАМКИ: {timeline}

        Предоставьте прогноз осложнений в формате JSON:
        {{
            "complication_overview": {{
                "overall_risk": "низкий/умеренный/высокий/критический",
                "total_complications_predicted": "количество возможных осложнений",
                "timeline_analysis": "анализ временных рамок",
                "confidence_level": "высокая/средняя/низкая"
            }},
            "immediate_complications": [
                {{
                    "complication": "название осложнения",
                    "probability": "вероятность в %",
                    "severity": "легкое/умеренное/тяжелое/критическое",
                    "onset_time": "время развития",
                    "risk_factors": ["фактор риска 1", "фактор риска 2"],
                    "early_signs": ["ранний признак 1", "ранний признак 2"],
                    "prevention_strategies": ["стратегия профилактики 1", "стратегия профилактики 2"],
                    "management_approach": "подход к лечению"
                }}
            ],
            "short_term_complications": [
                {{
                    "complication": "название осложнения",
                    "probability": "вероятность в %",
                    "severity": "легкое/умеренное/тяжелое/критическое",
                    "onset_time": "время развития",
                    "risk_factors": ["фактор риска 1", "фактор риска 2"],
                    "monitoring_parameters": ["параметр мониторинга 1", "параметр мониторинга 2"],
                    "intervention_threshold": "пороговые значения для вмешательства"
                }}
            ],
            "long_term_complications": [
                {{
                    "complication": "название осложнения",
                    "probability": "вероятность в %",
                    "severity": "легкое/умеренное/тяжелое/критическое",
                    "onset_time": "время развития",
                    "risk_factors": ["фактор риска 1", "фактор риска 2"],
                    "screening_recommendations": ["рекомендация по скринингу 1", "рекомендация по скринингу 2"],
                    "long_term_monitoring": "долгосрочное наблюдение"
                }}
            ],
            "system_specific_risks": {{
                "cardiovascular": ["риск 1", "риск 2"],
                "respiratory": ["риск 1", "риск 2"],
                "neurological": ["риск 1", "риск 2"],
                "gastrointestinal": ["риск 1", "риск 2"],
                "renal": ["риск 1", "риск 2"],
                "infectious": ["риск 1", "риск 2"]
            }},
            "patient_specific_factors": {{
                "age_related_risks": ["возрастной риск 1", "возрастной риск 2"],
                "gender_specific_risks": ["гендерный риск 1", "гендерный риск 2"],
                "comorbidity_interactions": ["взаимодействие 1", "взаимодействие 2"],
                "medication_related_risks": ["лекарственный риск 1", "лекарственный риск 2"]
            }},
            "prevention_protocol": {{
                "pre_procedure_measures": ["мера 1", "мера 2"],
                "intra_procedure_precautions": ["предосторожность 1", "предосторожность 2"],
                "post_procedure_monitoring": ["мониторинг 1", "мониторинг 2"],
                "patient_education": ["образование 1", "образование 2"]
            }},
            "emergency_preparedness": {{
                "high_risk_scenarios": ["сценарий 1", "сценарий 2"],
                "emergency_protocols": ["протокол 1", "протокол 2"],
                "required_resources": ["ресурс 1", "ресурс 2"],
                "escalation_criteria": ["критерий эскалации 1", "критерий эскалации 2"]
            }}
        }}
        """

        system_prompt = """Вы опытный врач-клиницист с экспертизой в прогнозировании и профилактике осложнений.
        Анализируете риски на основе современных клинических данных и доказательной медицины.
        Учитываете индивидуальные особенности пациента и специфику процедуры/состояния.
        Предоставляете практические рекомендации по профилактике и раннему выявлению осложнений.
        Ответы даете только в формате JSON."""

        request = AIRequest(
            prompt=prompt, system_prompt=system_prompt, temperature=0.2, max_tokens=4000
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


    async def calculate_mortality_risk(
        self,
        patient_data: dict[str, Any],
        condition: str,
        scoring_system: str | None = None,
    ) -> dict[str, Any]:
        """Расчет риска смертности"""
        age = patient_data.get("age", "не указан")
        gender = patient_data.get("gender", "не указан")
        vital_signs = patient_data.get("vital_signs", {})
        laboratory_values = patient_data.get("laboratory_values", {})
        comorbidities = patient_data.get("comorbidities", [])
        severity_indicators = patient_data.get("severity_indicators", {})

        vital_signs_text = (
            ", ".join([f"{k}: {v}" for k, v in vital_signs.items()])
            if vital_signs
            else "не указаны"
        )
        lab_values_text = (
            ", ".join([f"{k}: {v}" for k, v in laboratory_values.items()])
            if laboratory_values
            else "не указаны"
        )
        comorbidities_text = ", ".join(comorbidities) if comorbidities else "не указаны"
        severity_text = (
            ", ".join([f"{k}: {v}" for k, v in severity_indicators.items()])
            if severity_indicators
            else "не указаны"
        )

        scoring_system_info = (
            f"Используйте шкалу: {scoring_system}"
            if scoring_system
            else "Используйте наиболее подходящую валидированную шкалу"
        )

        prompt = f"""
        Рассчитайте риск смертности для пациента:

        ДАННЫЕ ПАЦИЕНТА:
        - Возраст: {age}
        - Пол: {gender}
        - Витальные показатели: {vital_signs_text}
        - Лабораторные показатели: {lab_values_text}
        - Сопутствующие заболевания: {comorbidities_text}
        - Показатели тяжести: {severity_text}

        СОСТОЯНИЕ: {condition}
        СИСТЕМА ОЦЕНКИ: {scoring_system_info}

        Предоставьте расчет риска смертности в формате JSON:
        {{
            "mortality_assessment": {{
                "primary_scoring_system": "название используемой шкалы",
                "total_score": "общий балл по шкале",
                "risk_category": "низкий/умеренный/высокий/критический",
                "predicted_mortality": {{
                    "in_hospital": "процент внутрибольничной смертности",
                    "30_day": "процент 30-дневной смертности",
                    "90_day": "процент 90-дневной смертности",
                    "1_year": "процент годовой смертности"
                }},
                "confidence_interval": "доверительный интервал",
                "calibration_note": "примечание о калибровке шкалы"
            }},
            "scoring_breakdown": {{
                "age_points": "баллы за возраст",
                "gender_points": "баллы за пол",
                "comorbidity_points": "баллы за сопутствующие заболевания",
                "vital_signs_points": "баллы за витальные показатели",
                "laboratory_points": "баллы за лабораторные показатели",
                "severity_points": "баллы за тяжесть состояния"
            }},
            "risk_factors_analysis": {{
                "major_risk_factors": [
                    {{
                        "factor": "название фактора",
                        "contribution": "вклад в общий риск",
                        "modifiable": true/false,
                        "intervention_potential": "потенциал для вмешательства"
                    }}
                ],
                "protective_factors": [
                    {{
                        "factor": "название защитного фактора",
                        "benefit": "защитный эффект",
                        "enhancement_potential": "потенциал для усиления"
                    }}
                ]
            }},
            "alternative_scores": [
                {{
                    "scoring_system": "альтернативная шкала",
                    "score": "балл",
                    "predicted_mortality": "прогнозируемая смертность",
                    "applicability": "применимость к данному случаю"
                }}
            ],
            "clinical_interpretation": {{
                "risk_level_description": "описание уровня риска",
                "clinical_implications": "клинические последствия",
                "treatment_intensity": "рекомендуемая интенсивность лечения",
                "monitoring_frequency": "частота мониторинга"
            }},
            "interventions_by_risk": {{
                "immediate_interventions": ["немедленное вмешательство 1", "немедленное вмешательство 2"],
                "short_term_goals": ["краткосрочная цель 1", "краткосрочная цель 2"],
                "long_term_strategies": ["долгосрочная стратегия 1", "долгосрочная стратегия 2"]
            }},
            "prognostic_indicators": {{
                "favorable_indicators": ["благоприятный показатель 1", "благоприятный показатель 2"],
                "unfavorable_indicators": ["неблагоприятный показатель 1", "неблагоприятный показатель 2"],
                "monitoring_parameters": ["параметр мониторинга 1", "параметр мониторинга 2"]
            }},
            "family_communication": {{
                "risk_explanation": "объяснение риска для семьи",
                "prognosis_discussion": "обсуждение прогноза",
                "decision_support": "поддержка в принятии решений"
            }}
        }}
        """

        system_prompt = """Вы врач-реаниматолог и специалист по интенсивной терапии с экспертизой в оценке тяжести состояния.
        Используете валидированные шкалы оценки риска смертности (APACHE, SOFA, SAPS, CHA2DS2-VASc и др.).
        Интерпретируете результаты в клиническом контексте и предоставляете практические рекомендации.
        Учитываете ограничения шкал и индивидуальные особенности пациента.
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


    async def assess_surgical_risk(
        self, patient_profile: dict[str, Any], surgery_type: str, anesthesia_type: str
    ) -> dict[str, Any]:
        """Оценка хирургических рисков"""
        age = patient_profile.get("age", "не указан")
        gender = patient_profile.get("gender", "не указан")
        weight = patient_profile.get("weight", "не указан")
        height = patient_profile.get("height", "не указан")
        asa_class = patient_profile.get("asa_class", "не указан")
        comorbidities = patient_profile.get("comorbidities", [])
        medications = patient_profile.get("medications", [])
        previous_surgeries = patient_profile.get("previous_surgeries", [])
        allergies = patient_profile.get("allergies", [])
        functional_status = patient_profile.get("functional_status", "не указан")

        comorbidities_text = ", ".join(comorbidities) if comorbidities else "не указаны"
        medications_text = (
            ", ".join([med.get("name", "не указано") for med in medications])
            if medications
            else "не указаны"
        )
        surgeries_text = (
            ", ".join(previous_surgeries) if previous_surgeries else "не указаны"
        )
        allergies_text = ", ".join(allergies) if allergies else "не указаны"

        prompt = f"""
        Оцените хирургические риски для пациента:

        ПРОФИЛЬ ПАЦИЕНТА:
        - Возраст: {age}
        - Пол: {gender}
        - Вес: {weight} кг
        - Рост: {height} см
        - Класс ASA: {asa_class}
        - Сопутствующие заболевания: {comorbidities_text}
        - Текущие препараты: {medications_text}
        - Предыдущие операции: {surgeries_text}
        - Аллергии: {allergies_text}
        - Функциональный статус: {functional_status}

        ТИП ОПЕРАЦИИ: {surgery_type}
        ТИП АНЕСТЕЗИИ: {anesthesia_type}

        Предоставьте оценку хирургических рисков в формате JSON:
        {{
            "surgical_risk_assessment": {{
                "overall_risk": "низкий/умеренный/высокий/критический",
                "asa_classification": "класс ASA с обоснованием",
                "predicted_mortality": "прогнозируемая смертность в %",
                "predicted_morbidity": "прогнозируемая заболеваемость в %",
                "risk_stratification": "стратификация риска"
            }},
            "perioperative_risks": {{
                "preoperative_risks": [
                    {{
                        "risk": "название риска",
                        "probability": "вероятность в %",
                        "severity": "легкий/умеренный/тяжелый/критический",
                        "mitigation_strategies": ["стратегия 1", "стратегия 2"]
                    }}
                ],
                "intraoperative_risks": [
                    {{
                        "risk": "название риска",
                        "probability": "вероятность в %",
                        "severity": "легкий/умеренный/тяжелый/критический",
                        "prevention_measures": ["мера 1", "мера 2"]
                    }}
                ],
                "postoperative_risks": [
                    {{
                        "risk": "название риска",
                        "probability": "вероятность в %",
                        "severity": "легкий/умеренный/тяжелый/критический",
                        "monitoring_requirements": ["требование 1", "требование 2"]
                    }}
                ]
            }},
            "anesthesia_considerations": {{
                "anesthesia_risk": "низкий/умеренный/высокий/критический",
                "specific_concerns": ["проблема 1", "проблема 2"],
                "airway_assessment": "оценка дыхательных путей",
                "cardiovascular_considerations": "сердечно-сосудистые соображения",
                "drug_interactions": ["взаимодействие 1", "взаимодействие 2"],
                "monitoring_requirements": ["требование мониторинга 1", "требование мониторинга 2"]
            }},
            "procedure_specific_risks": {{
                "technical_complexity": "низкая/умеренная/высокая/критическая",
                "duration_considerations": "соображения по продолжительности",
                "positioning_risks": ["риск позиционирования 1", "риск позиционирования 2"],
                "blood_loss_risk": "риск кровопотери",
                "infection_risk": "риск инфекции",
                "organ_specific_risks": ["органоспецифичный риск 1", "органоспецифичный риск 2"]
            }},
            "optimization_recommendations": {{
                "preoperative_optimization": [
                    {{
                        "intervention": "вмешательство",
                        "timeline": "временные рамки",
                        "expected_benefit": "ожидаемая польза",
                        "monitoring_parameters": ["параметр 1", "параметр 2"]
                    }}
                ],
                "medication_adjustments": [
                    {{
                        "medication": "препарат",
                        "adjustment": "корректировка",
                        "rationale": "обоснование",
                        "timing": "время выполнения"
                    }}
                ]
            }},
            "postoperative_care_plan": {{
                "monitoring_level": "уровень мониторинга (палата/ПИТ/ОРИТ)",
                "duration_of_monitoring": "продолжительность мониторинга",
                "key_parameters": ["ключевой параметр 1", "ключевой параметр 2"],
                "early_mobilization": "план ранней мобилизации",
                "pain_management": "план обезболивания",
                "discharge_criteria": ["критерий выписки 1", "критерий выписки 2"]
            }},
            "alternative_approaches": [
                {{
                    "approach": "альтернативный подход",
                    "risk_benefit_ratio": "соотношение риск/польза",
                    "suitability": "подходящность для пациента",
                    "considerations": ["соображение 1", "соображение 2"]
                }}
            ],
            "informed_consent_points": [
                "ключевой пункт для информированного согласия 1",
                "ключевой пункт для информированного согласия 2"
            ]
        }}
        """

        system_prompt = """Вы анестезиолог-реаниматолог с экспертизой в периоперационной медицине.
        Оцениваете хирургические риски на основе современных клинических рекомендаций и валидированных шкал.
        Учитываете все аспекты периоперационного периода и индивидуальные особенности пациента.
        Предоставляете практические рекомендации по оптимизации и минимизации рисков.
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


    async def predict_readmission_risk(
        self,
        patient_data: dict[str, Any],
        discharge_condition: str,
        social_factors: dict[str, Any],
    ) -> dict[str, Any]:
        """Прогнозирование риска повторной госпитализации"""
        age = patient_data.get("age", "не указан")
        gender = patient_data.get("gender", "не указан")
        primary_diagnosis = patient_data.get("primary_diagnosis", "не указан")
        comorbidities = patient_data.get("comorbidities", [])
        medications = patient_data.get("medications", [])
        length_of_stay = patient_data.get("length_of_stay", "не указана")
        previous_admissions = patient_data.get("previous_admissions", "не указаны")

        social_support = social_factors.get("social_support", "не указана")
        insurance_status = social_factors.get("insurance_status", "не указан")
        transportation = social_factors.get("transportation", "не указан")
        housing_situation = social_factors.get("housing_situation", "не указана")
        caregiver_availability = social_factors.get(
            "caregiver_availability", "не указана"
        )
        health_literacy = social_factors.get("health_literacy", "не указана")

        comorbidities_text = ", ".join(comorbidities) if comorbidities else "не указаны"
        medications_text = (
            ", ".join([med.get("name", "не указано") for med in medications])
            if medications
            else "не указаны"
        )

        prompt = f"""
        Спрогнозируйте риск повторной госпитализации для пациента:

        ДАННЫЕ ПАЦИЕНТА:
        - Возраст: {age}
        - Пол: {gender}
        - Основной диагноз: {primary_diagnosis}
        - Сопутствующие заболевания: {comorbidities_text}
        - Текущие препараты: {medications_text}
        - Длительность госпитализации: {length_of_stay}
        - Предыдущие госпитализации: {previous_admissions}

        СОСТОЯНИЕ ПРИ ВЫПИСКЕ: {discharge_condition}

        СОЦИАЛЬНЫЕ ФАКТОРЫ:
        - Социальная поддержка: {social_support}
        - Страховой статус: {insurance_status}
        - Транспорт: {transportation}
        - Жилищные условия: {housing_situation}
        - Доступность ухода: {caregiver_availability}
        - Медицинская грамотность: {health_literacy}

        Предоставьте прогноз риска повторной госпитализации в формате JSON:
        {{
            "readmission_risk_assessment": {{
                "overall_risk": "низкий/умеренный/высокий/критический",
                "risk_score": "числовая оценка от 1 до 100",
                "predicted_readmission_rates": {{
                    "7_day": "процент 7-дневной реадмиссии",
                    "30_day": "процент 30-дневной реадмиссии",
                    "90_day": "процент 90-дневной реадмиссии",
                    "1_year": "процент годовой реадмиссии"
                }},
                "confidence_level": "высокая/средняя/низкая"
            }},
            "risk_factor_analysis": {{
                "medical_risk_factors": [
                    {{
                        "factor": "медицинский фактор риска",
                        "weight": "вес фактора",
                        "modifiable": true/false,
                        "intervention_potential": "потенциал для вмешательства"
                    }}
                ],
                "social_risk_factors": [
                    {{
                        "factor": "социальный фактор риска",
                        "weight": "вес фактора",
                        "modifiable": true/false,
                        "intervention_potential": "потенциал для вмешательства"
                    }}
                ],
                "system_risk_factors": [
                    {{
                        "factor": "системный фактор риска",
                        "weight": "вес фактора",
                        "modifiable": true/false,
                        "intervention_potential": "потенциал для вмешательства"
                    }}
                ]
            }},
            "high_risk_scenarios": [
                {{
                    "scenario": "сценарий высокого риска",
                    "probability": "вероятность в %",
                    "timeline": "временные рамки",
                    "warning_signs": ["предупреждающий признак 1", "предупреждающий признак 2"],
                    "prevention_strategies": ["стратегия профилактики 1", "стратегия профилактики 2"]
                }}
            ],
            "discharge_planning_recommendations": {{
                "medication_reconciliation": {{
                    "priority": "высокий/средний/низкий",
                    "specific_actions": ["действие 1", "действие 2"],
                    "follow_up_required": true/false
                }},
                "follow_up_appointments": {{
                    "primary_care": "рекомендации по первичной помощи",
                    "specialist_care": "рекомендации по специализированной помощи",
                    "timeline": "временные рамки для записи",
                    "priority_level": "высокий/средний/низкий"
                }},
                "patient_education": {{
                    "key_topics": ["ключевая тема 1", "ключевая тема 2"],
                    "education_methods": ["метод обучения 1", "метод обучения 2"],
                    "comprehension_assessment": "оценка понимания"
                }}
            }},
            "care_coordination": {{
                "care_team_members": ["член команды 1", "член команды 2"],
                "communication_plan": "план коммуникации",
                "care_transitions": ["переход 1", "переход 2"],
                "monitoring_responsibilities": ["ответственность за мониторинг 1", "ответственность за мониторинг 2"]
            }},
            "intervention_strategies": {{
                "high_intensity_interventions": [
                    {{
                        "intervention": "интенсивное вмешательство",
                        "target_population": "целевая популяция",
                        "expected_benefit": "ожидаемая польза",
                        "resource_requirements": ["требуемый ресурс 1", "требуемый ресурс 2"]
                    }}
                ],
                "moderate_intensity_interventions": [
                    {{
                        "intervention": "умеренное вмешательство",
                        "target_population": "целевая популяция",
                        "expected_benefit": "ожидаемая польза",
                        "resource_requirements": ["требуемый ресурс 1", "требуемый ресурс 2"]
                    }}
                ],
                "low_intensity_interventions": [
                    {{
                        "intervention": "низкоинтенсивное вмешательство",
                        "target_population": "целевая популяция",
                        "expected_benefit": "ожидаемая польза",
                        "resource_requirements": ["требуемый ресурс 1", "требуемый ресурс 2"]
                    }}
                ]
            }},
            "monitoring_plan": {{
                "post_discharge_contacts": {{
                    "24_hours": "контакт в течение 24 часов",
                    "72_hours": "контакт в течение 72 часов",
                    "1_week": "контакт через неделю",
                    "1_month": "контакт через месяц"
                }},
                "red_flag_symptoms": ["тревожный симптом 1", "тревожный симптом 2"],
                "emergency_contact_criteria": ["критерий экстренного контакта 1", "критерий экстренного контакта 2"]
            }}
        }}
        """

        system_prompt = """Вы специалист по управлению переходами в медицинской помощи с экспертизой в предотвращении повторных госпитализаций.
        Анализируете медицинские, социальные и системные факторы риска повторной госпитализации.
        Используете валидированные инструменты оценки риска и доказательные вмешательства.
        Предоставляете комплексные рекомендации по планированию выписки и координации помощи.
        Ответы даете только в формате JSON."""

        request = AIRequest(
            prompt=prompt, system_prompt=system_prompt, temperature=0.2, max_tokens=4000
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


