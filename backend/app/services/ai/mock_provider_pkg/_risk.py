"""Risk mixin for MockProvider.

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


class RiskMixin(MockProviderMixinBase):
    """Risk methods for MockProvider."""

    async def assess_patient_risk(
        self, patient_data: dict[str, Any], risk_factors: list[str], condition: str
    ) -> dict[str, Any]:
        """Имитация комплексной оценки рисков пациента"""
        await asyncio.sleep(2)

        age = patient_data.get("age", 45)
        _gender = patient_data.get("gender", "не указан")

        # Имитируем различные уровни риска в зависимости от возраста
        if age < 30:
            overall_risk = "низкий"
            risk_score = 25
        elif age < 50:
            overall_risk = "умеренный"
            risk_score = 45
        elif age < 70:
            overall_risk = "высокий"
            risk_score = 70
        else:
            overall_risk = "критический"
            risk_score = 85

        return {
            "overall_risk_assessment": {
                "risk_level": overall_risk,
                "risk_score": risk_score,
                "confidence_level": "высокая",
                "assessment_date": "2024-01-15",
            },
            "risk_categories": {
                "cardiovascular_risk": {
                    "level": "умеренный",
                    "score": 35,
                    "contributing_factors": ["возраст", "артериальная гипертензия"],
                    "10_year_risk": "15%",
                },
                "metabolic_risk": {
                    "level": "низкий",
                    "score": 20,
                    "contributing_factors": ["ИМТ в норме"],
                    "diabetes_risk": "8%",
                },
                "oncological_risk": {
                    "level": "низкий",
                    "score": 15,
                    "contributing_factors": ["отсутствие семейного анамнеза"],
                    "screening_recommendations": ["маммография", "колоноскопия"],
                },
                "infectious_risk": {
                    "level": "низкий",
                    "score": 10,
                    "contributing_factors": ["хороший иммунный статус"],
                    "vaccination_status": "актуальная",
                },
            },
            "modifiable_risk_factors": [
                {
                    "factor": "курение",
                    "current_status": "10 сигарет в день",
                    "target_value": "полный отказ",
                    "intervention": "никотинзаместительная терапия",
                    "potential_risk_reduction": "30%",
                },
                {
                    "factor": "физическая активность",
                    "current_status": "малоподвижный образ жизни",
                    "target_value": "150 минут умеренной активности в неделю",
                    "intervention": "программа физических упражнений",
                    "potential_risk_reduction": "20%",
                },
            ],
            "non_modifiable_risk_factors": [
                {
                    "factor": "возраст",
                    "impact": "увеличивает риск на 15%",
                    "management_strategy": "усиленный мониторинг",
                },
                {
                    "factor": "семейный анамнез",
                    "impact": "увеличивает риск на 10%",
                    "management_strategy": "раннее скрининговое обследование",
                },
            ],
            "risk_stratification": {
                "primary_prevention": {
                    "applicable": True,
                    "recommendations": ["контроль АД", "здоровое питание"],
                    "timeline": "немедленно",
                },
                "secondary_prevention": {
                    "applicable": False,
                    "recommendations": [],
                    "timeline": "не применимо",
                },
            },
            "monitoring_plan": {
                "frequency": "каждые 6 месяцев",
                "parameters": ["АД", "холестерин", "глюкоза"],
                "laboratory_tests": ["липидограмма", "HbA1c"],
                "imaging_studies": ["ЭКГ", "УЗИ сердца"],
                "specialist_referrals": ["кардиолог", "эндокринолог"],
            },
            "risk_communication": {
                "patient_friendly_explanation": "Ваш общий риск умеренный, но его можно значительно снизить",
                "visual_aids": ["диаграмма риска", "график прогресса"],
                "key_messages": [
                    "отказ от курения критически важен",
                    "регулярные упражнения снизят риск",
                ],
            },
            "emergency_indicators": [
                {
                    "indicator": "боль в груди",
                    "action": "немедленно вызвать скорую помощь",
                    "urgency": "немедленно",
                },
                {
                    "indicator": "одышка в покое",
                    "action": "обратиться к врачу",
                    "urgency": "в течение часа",
                },
            ],
        }


    async def predict_complications(
        self,
        patient_profile: dict[str, Any],
        procedure_or_condition: str,
        timeline: str,
    ) -> dict[str, Any]:
        """Имитация прогнозирования возможных осложнений"""
        await asyncio.sleep(2.5)

        _age = patient_profile.get("age", 45)

        return {
            "complication_overview": {
                "overall_risk": "умеренный",
                "total_complications_predicted": 5,
                "timeline_analysis": f"В течение {timeline} ожидается развитие 2-3 осложнений",
                "confidence_level": "высокая",
            },
            "immediate_complications": [
                {
                    "complication": "кровотечение",
                    "probability": "15%",
                    "severity": "умеренное",
                    "onset_time": "в течение 24 часов",
                    "risk_factors": ["антикоагулянты", "возраст"],
                    "early_signs": ["снижение гемоглобина", "тахикардия"],
                    "prevention_strategies": [
                        "контроль коагуляции",
                        "мониторинг витальных функций",
                    ],
                    "management_approach": "консервативное лечение с возможностью хирургического вмешательства",
                }
            ],
            "short_term_complications": [
                {
                    "complication": "инфекция",
                    "probability": "10%",
                    "severity": "умеренное",
                    "onset_time": "3-7 дней",
                    "risk_factors": ["сахарный диабет", "иммуносупрессия"],
                    "monitoring_parameters": ["температура", "лейкоциты", "СРБ"],
                    "intervention_threshold": "температура >38°C или лейкоциты >12000",
                }
            ],
            "long_term_complications": [
                {
                    "complication": "хроническая боль",
                    "probability": "8%",
                    "severity": "легкое",
                    "onset_time": "через 3-6 месяцев",
                    "risk_factors": [
                        "предыдущие болевые синдромы",
                        "психологические факторы",
                    ],
                    "screening_recommendations": [
                        "оценка боли",
                        "психологическое консультирование",
                    ],
                    "long_term_monitoring": "ежемесячная оценка в течение года",
                }
            ],
            "system_specific_risks": {
                "cardiovascular": ["аритмии", "гипотония"],
                "respiratory": ["ателектазы", "пневмония"],
                "neurological": ["делирий", "когнитивные нарушения"],
                "gastrointestinal": ["тошнота", "запоры"],
                "renal": ["острое повреждение почек"],
                "infectious": ["раневая инфекция", "сепсис"],
            },
            "patient_specific_factors": {
                "age_related_risks": [
                    "замедленное заживление",
                    "повышенная чувствительность к препаратам",
                ],
                "gender_specific_risks": ["гормональные изменения"],
                "comorbidity_interactions": ["взаимодействие диабета и заживления ран"],
                "medication_related_risks": [
                    "лекарственные взаимодействия",
                    "побочные эффекты",
                ],
            },
            "prevention_protocol": {
                "pre_procedure_measures": [
                    "оптимизация состояния",
                    "профилактическая антибиотикотерапия",
                ],
                "intra_procedure_precautions": ["асептика", "контроль гемостаза"],
                "post_procedure_monitoring": [
                    "витальные функции",
                    "лабораторные показатели",
                ],
                "patient_education": [
                    "признаки осложнений",
                    "когда обращаться за помощью",
                ],
            },
            "emergency_preparedness": {
                "high_risk_scenarios": [
                    "массивное кровотечение",
                    "анафилактический шок",
                ],
                "emergency_protocols": [
                    "алгоритм остановки кровотечения",
                    "протокол анафилаксии",
                ],
                "required_resources": [
                    "препараты крови",
                    "реанимационное оборудование",
                ],
                "escalation_criteria": ["снижение АД >20%", "SpO2 <90%"],
            },
        }


    async def calculate_mortality_risk(
        self,
        patient_data: dict[str, Any],
        condition: str,
        scoring_system: str | None = None,
    ) -> dict[str, Any]:
        """Имитация расчета риска смертности"""
        await asyncio.sleep(1.5)

        age = patient_data.get("age", 65)

        # Имитируем расчет на основе возраста
        if age < 50:
            mortality_30_day = "2%"
            risk_category = "низкий"
            total_score = 15
        elif age < 70:
            mortality_30_day = "8%"
            risk_category = "умеренный"
            total_score = 35
        else:
            mortality_30_day = "15%"
            risk_category = "высокий"
            total_score = 55

        return {
            "mortality_assessment": {
                "primary_scoring_system": scoring_system or "APACHE II",
                "total_score": total_score,
                "risk_category": risk_category,
                "predicted_mortality": {
                    "in_hospital": "5%",
                    "30_day": mortality_30_day,
                    "90_day": "12%",
                    "1_year": "25%",
                },
                "confidence_interval": "95% ДИ: 3-18%",
                "calibration_note": "Шкала хорошо калибрована для данной популяции",
            },
            "scoring_breakdown": {
                "age_points": 8,
                "gender_points": 0,
                "comorbidity_points": 12,
                "vital_signs_points": 10,
                "laboratory_points": 15,
                "severity_points": 10,
            },
            "risk_factors_analysis": {
                "major_risk_factors": [
                    {
                        "factor": "возраст >65 лет",
                        "contribution": "высокий вклад",
                        "modifiable": False,
                        "intervention_potential": "низкий",
                    },
                    {
                        "factor": "хроническая сердечная недостаточность",
                        "contribution": "умеренный вклад",
                        "modifiable": True,
                        "intervention_potential": "высокий",
                    },
                ],
                "protective_factors": [
                    {
                        "factor": "отсутствие курения",
                        "benefit": "снижение риска на 20%",
                        "enhancement_potential": "поддержание статуса",
                    }
                ],
            },
            "alternative_scores": [
                {
                    "scoring_system": "SOFA",
                    "score": 8,
                    "predicted_mortality": "15-20%",
                    "applicability": "хорошо применима",
                },
                {
                    "scoring_system": "SAPS II",
                    "score": 42,
                    "predicted_mortality": "18%",
                    "applicability": "умеренно применима",
                },
            ],
            "clinical_interpretation": {
                "risk_level_description": "Умеренно высокий риск смертности",
                "clinical_implications": "Требуется интенсивное наблюдение и лечение",
                "treatment_intensity": "высокая",
                "monitoring_frequency": "каждые 4 часа",
            },
            "interventions_by_risk": {
                "immediate_interventions": [
                    "стабилизация гемодинамики",
                    "коррекция электролитов",
                ],
                "short_term_goals": [
                    "улучшение органной функции",
                    "профилактика осложнений",
                ],
                "long_term_strategies": ["реабилитация", "вторичная профилактика"],
            },
            "prognostic_indicators": {
                "favorable_indicators": [
                    "стабильная гемодинамика",
                    "сохранная функция почек",
                ],
                "unfavorable_indicators": [
                    "полиорганная недостаточность",
                    "рефрактерный шок",
                ],
                "monitoring_parameters": ["лактат", "диурез", "ментальный статус"],
            },
            "family_communication": {
                "risk_explanation": "Состояние серьезное, но есть хорошие шансы на выздоровление",
                "prognosis_discussion": "Прогноз зависит от ответа на лечение в ближайшие 48 часов",
                "decision_support": "Обсуждение целей лечения и предпочтений пациента",
            },
        }


    async def assess_surgical_risk(
        self, patient_profile: dict[str, Any], surgery_type: str, anesthesia_type: str
    ) -> dict[str, Any]:
        """Имитация оценки хирургических рисков"""
        await asyncio.sleep(2)

        _age = patient_profile.get("age", 55)
        asa_class = patient_profile.get("asa_class", "II")

        return {
            "surgical_risk_assessment": {
                "overall_risk": "умеренный",
                "asa_classification": f"ASA {asa_class} - пациент с легким системным заболеванием",
                "predicted_mortality": "1.5%",
                "predicted_morbidity": "12%",
                "risk_stratification": "умеренный риск",
            },
            "perioperative_risks": {
                "preoperative_risks": [
                    {
                        "risk": "сердечно-сосудистые осложнения",
                        "probability": "8%",
                        "severity": "умеренный",
                        "mitigation_strategies": [
                            "оптимизация терапии",
                            "кардиологическая консультация",
                        ],
                    }
                ],
                "intraoperative_risks": [
                    {
                        "risk": "кровотечение",
                        "probability": "5%",
                        "severity": "умеренный",
                        "prevention_measures": [
                            "контроль коагуляции",
                            "готовность к гемотрансфузии",
                        ],
                    }
                ],
                "postoperative_risks": [
                    {
                        "risk": "тромбоэмболические осложнения",
                        "probability": "3%",
                        "severity": "тяжелый",
                        "monitoring_requirements": [
                            "оценка признаков ТЭЛА",
                            "контроль D-димера",
                        ],
                    }
                ],
            },
            "anesthesia_considerations": {
                "anesthesia_risk": "низкий",
                "specific_concerns": ["возможная трудная интубация"],
                "airway_assessment": "Mallampati II, нормальная подвижность шеи",
                "cardiovascular_considerations": "стабильная ИБС, компенсированная",
                "drug_interactions": ["взаимодействие с антикоагулянтами"],
                "monitoring_requirements": [
                    "инвазивный мониторинг АД",
                    "контроль нейромышечной блокады",
                ],
            },
            "procedure_specific_risks": {
                "technical_complexity": "умеренная",
                "duration_considerations": "длительность 2-3 часа увеличивает риск",
                "positioning_risks": ["компрессия нервов", "пролежни"],
                "blood_loss_risk": "умеренный",
                "infection_risk": "низкий",
                "organ_specific_risks": ["повреждение соседних органов"],
            },
            "optimization_recommendations": {
                "preoperative_optimization": [
                    {
                        "intervention": "коррекция анемии",
                        "timeline": "за 2-4 недели",
                        "expected_benefit": "снижение риска переливания",
                        "monitoring_parameters": ["гемоглобин", "ферритин"],
                    }
                ],
                "medication_adjustments": [
                    {
                        "medication": "варфарин",
                        "adjustment": "отмена за 5 дней",
                        "rationale": "снижение риска кровотечения",
                        "timing": "с переходом на НМГ",
                    }
                ],
            },
            "postoperative_care_plan": {
                "monitoring_level": "палата интенсивной терапии",
                "duration_of_monitoring": "24 часа",
                "key_parameters": ["гемодинамика", "диурез", "неврологический статус"],
                "early_mobilization": "активизация через 6 часов",
                "pain_management": "мультимодальная анальгезия",
                "discharge_criteria": [
                    "стабильная гемодинамика",
                    "адекватный диурез",
                    "отсутствие осложнений",
                ],
            },
            "alternative_approaches": [
                {
                    "approach": "лапароскопический доступ",
                    "risk_benefit_ratio": "более благоприятный",
                    "suitability": "подходит для данного пациента",
                    "considerations": [
                        "меньшая травматичность",
                        "быстрое восстановление",
                    ],
                }
            ],
            "informed_consent_points": [
                "риск кровотечения и необходимость переливания крови",
                "возможность конверсии в открытую операцию",
                "риск инфекционных осложнений",
                "возможность повреждения соседних органов",
            ],
        }


    async def predict_readmission_risk(
        self,
        patient_data: dict[str, Any],
        discharge_condition: str,
        social_factors: dict[str, Any],
    ) -> dict[str, Any]:
        """Имитация прогнозирования риска повторной госпитализации"""
        await asyncio.sleep(2)

        age = patient_data.get("age", 65)
        social_support = social_factors.get("social_support", "умеренная")

        # Имитируем различные уровни риска
        if age < 50 and social_support == "хорошая":
            overall_risk = "низкий"
            risk_score = 25
            readmission_30_day = "8%"
        elif age < 70:
            overall_risk = "умеренный"
            risk_score = 55
            readmission_30_day = "15%"
        else:
            overall_risk = "высокий"
            risk_score = 75
            readmission_30_day = "25%"

        return {
            "readmission_risk_assessment": {
                "overall_risk": overall_risk,
                "risk_score": risk_score,
                "predicted_readmission_rates": {
                    "7_day": "5%",
                    "30_day": readmission_30_day,
                    "90_day": "30%",
                    "1_year": "45%",
                },
                "confidence_level": "высокая",
            },
            "risk_factor_analysis": {
                "medical_risk_factors": [
                    {
                        "factor": "множественные сопутствующие заболевания",
                        "weight": "высокий",
                        "modifiable": True,
                        "intervention_potential": "умеренный",
                    },
                    {
                        "factor": "предыдущие госпитализации",
                        "weight": "высокий",
                        "modifiable": False,
                        "intervention_potential": "низкий",
                    },
                ],
                "social_risk_factors": [
                    {
                        "factor": "ограниченная социальная поддержка",
                        "weight": "умеренный",
                        "modifiable": True,
                        "intervention_potential": "высокий",
                    },
                    {
                        "factor": "низкая медицинская грамотность",
                        "weight": "умеренный",
                        "modifiable": True,
                        "intervention_potential": "высокий",
                    },
                ],
                "system_risk_factors": [
                    {
                        "factor": "недостаточная координация помощи",
                        "weight": "умеренный",
                        "modifiable": True,
                        "intervention_potential": "высокий",
                    }
                ],
            },
            "high_risk_scenarios": [
                {
                    "scenario": "обострение хронического заболевания",
                    "probability": "35%",
                    "timeline": "в течение 2 недель",
                    "warning_signs": ["ухудшение симптомов", "несоблюдение режима"],
                    "prevention_strategies": ["телемониторинг", "обучение пациента"],
                }
            ],
            "discharge_planning_recommendations": {
                "medication_reconciliation": {
                    "priority": "высокий",
                    "specific_actions": [
                        "сверка всех препаратов",
                        "объяснение изменений",
                    ],
                    "follow_up_required": True,
                },
                "follow_up_appointments": {
                    "primary_care": "запись в течение 7 дней",
                    "specialist_care": "запись в течение 14 дней",
                    "timeline": "до выписки",
                    "priority_level": "высокий",
                },
                "patient_education": {
                    "key_topics": [
                        "управление симптомами",
                        "когда обращаться за помощью",
                    ],
                    "education_methods": ["письменные инструкции", "демонстрация"],
                    "comprehension_assessment": "метод обратной связи",
                },
            },
            "care_coordination": {
                "care_team_members": [
                    "лечащий врач",
                    "медсестра",
                    "социальный работник",
                ],
                "communication_plan": "еженедельные междисциплинарные совещания",
                "care_transitions": ["госпиталь-дом", "специалист-первичная помощь"],
                "monitoring_responsibilities": [
                    "мониторинг симптомов",
                    "контроль приверженности",
                ],
            },
            "intervention_strategies": {
                "high_intensity_interventions": [
                    {
                        "intervention": "программа управления переходами",
                        "target_population": "пациенты высокого риска",
                        "expected_benefit": "снижение реадмиссии на 30%",
                        "resource_requirements": [
                            "координатор выписки",
                            "телемониторинг",
                        ],
                    }
                ],
                "moderate_intensity_interventions": [
                    {
                        "intervention": "структурированное наблюдение",
                        "target_population": "пациенты умеренного риска",
                        "expected_benefit": "снижение реадмиссии на 20%",
                        "resource_requirements": ["медсестра амбулаторного звена"],
                    }
                ],
                "low_intensity_interventions": [
                    {
                        "intervention": "образовательные материалы",
                        "target_population": "все пациенты",
                        "expected_benefit": "снижение реадмиссии на 10%",
                        "resource_requirements": ["печатные материалы"],
                    }
                ],
            },
            "monitoring_plan": {
                "post_discharge_contacts": {
                    "24_hours": "телефонный звонок медсестры",
                    "72_hours": "оценка состояния и приверженности",
                    "1_week": "визит на дом или в клинику",
                    "1_month": "комплексная оценка",
                },
                "red_flag_symptoms": ["ухудшение одышки", "отеки", "боль в груди"],
                "emergency_contact_criteria": ["температура >38.5°C", "SpO2 <90%"],
            },
        }


