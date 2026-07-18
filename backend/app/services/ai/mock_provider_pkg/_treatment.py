"""Treatment mixin for MockProvider.

Split from mock_provider.py.
"""
from __future__ import annotations

from app.services.ai.mock_provider_pkg._base import (
    Any,
    MockProviderMixinBase,
    asyncio,
)


class TreatmentMixin(MockProviderMixinBase):
    """Treatment methods for MockProvider."""

    async def generate_treatment_plan(
        self,
        patient_data: dict[str, Any],
        diagnosis: str,
        medical_history: list[dict] | None = None,
    ) -> dict[str, Any]:
        """Имитация генерации плана лечения"""
        await asyncio.sleep(2)

        _age = patient_data.get("age", 45)
        _gender = patient_data.get("gender", "не указан")

        return {
            "treatment_goals": [
                {
                    "goal": "Устранение основных симптомов",
                    "priority": "высокий",
                    "timeline": "2-4 недели",
                },
                {
                    "goal": "Предотвращение осложнений",
                    "priority": "средний",
                    "timeline": "1-3 месяца",
                },
            ],
            "medication_plan": [
                {
                    "medication": "Препарат A",
                    "dosage": "10 мг",
                    "frequency": "2 раза в день",
                    "duration": "14 дней",
                    "instructions": "Принимать во время еды",
                    "monitoring": "Контроль АД каждые 3 дня",
                }
            ],
            "non_pharmacological": [
                {
                    "intervention": "Физиотерапия",
                    "description": "Лечебная физкультура",
                    "frequency": "3 раза в неделю",
                    "duration": "4 недели",
                }
            ],
            "lifestyle_recommendations": [
                {
                    "category": "диета",
                    "recommendation": "Ограничение соли до 5г/день",
                    "rationale": "Снижение нагрузки на сердечно-сосудистую систему",
                }
            ],
            "follow_up_schedule": [
                {
                    "timepoint": "через 1 неделю",
                    "assessments": ["общее состояние", "переносимость терапии"],
                    "tests": ["общий анализ крови"],
                }
            ],
            "warning_signs": ["усиление болей", "повышение температуры"],
            "contraindications": ["беременность", "тяжелая почечная недостаточность"],
            "expected_outcomes": {
                "short_term": "Улучшение самочувствия в течение 1-2 недель",
                "long_term": "Полное выздоровление через 1-2 месяца",
                "success_criteria": ["отсутствие симптомов", "нормализация анализов"],
            },
        }


    async def optimize_medication_regimen(
        self,
        current_medications: list[dict],
        patient_profile: dict[str, Any],
        condition: str,
    ) -> dict[str, Any]:
        """Имитация оптимизации медикаментозной терапии"""
        await asyncio.sleep(1.5)

        return {
            "optimization_summary": "Рекомендована корректировка дозировки и добавление нового препарата",
            "medication_changes": [
                {
                    "action": "изменить",
                    "current_medication": "Препарат A",
                    "new_medication": "Препарат A",
                    "new_dosage": "15 мг",
                    "new_frequency": "1 раз в день",
                    "rationale": "Улучшение переносимости",
                    "monitoring_required": "Контроль функции печени",
                },
                {
                    "action": "добавить",
                    "current_medication": None,
                    "new_medication": "Препарат B",
                    "new_dosage": "5 мг",
                    "new_frequency": "2 раза в день",
                    "rationale": "Синергический эффект",
                    "monitoring_required": "Контроль АД",
                },
            ],
            "drug_interactions": [
                {
                    "medications": ["Препарат A", "Препарат B"],
                    "interaction_type": "фармакокинетическое",
                    "severity": "умеренная",
                    "management": "Контроль концентрации в крови",
                }
            ],
            "dosage_adjustments": [
                {
                    "medication": "Препарат A",
                    "reason": "возраст пациента",
                    "adjustment": "снижение дозы на 25%",
                    "monitoring": "функция почек",
                }
            ],
            "adherence_strategies": [
                "использование органайзера для таблеток",
                "установка напоминаний на телефоне",
            ],
            "cost_considerations": "Возможна замена на более доступный аналог",
            "follow_up_timeline": "контроль через 2 недели",
        }


    async def assess_treatment_effectiveness(
        self, treatment_history: list[dict], patient_response: dict[str, Any]
    ) -> dict[str, Any]:
        """Имитация оценки эффективности лечения"""
        await asyncio.sleep(1.5)

        return {
            "overall_effectiveness": {
                "score": "7",
                "category": "хорошая",
                "rationale": "Значительное улучшение основных симптомов",
            },
            "symptom_response": {
                "improved_symptoms": ["головная боль", "слабость"],
                "unchanged_symptoms": ["периодическое головокружение"],
                "worsened_symptoms": [],
                "new_symptoms": [],
            },
            "side_effect_profile": {
                "severity": "легкие",
                "tolerability": "хорошая",
                "management_needed": False,
            },
            "adherence_analysis": {
                "level": "высокая",
                "barriers": [],
                "improvement_strategies": ["продолжить текущий режим"],
            },
            "treatment_modifications": [
                {
                    "type": "продолжить текущую терапию",
                    "recommendation": "сохранить дозировку",
                    "rationale": "хороший ответ на лечение",
                    "urgency": "плановое",
                }
            ],
            "monitoring_recommendations": [
                "контроль АД еженедельно",
                "общий анализ крови через месяц",
            ],
            "prognosis": {
                "short_term": "продолжение улучшения",
                "long_term": "благоприятный",
                "factors_affecting": ["приверженность лечению"],
            },
        }


    async def suggest_lifestyle_modifications(
        self, patient_profile: dict[str, Any], conditions: list[str]
    ) -> dict[str, Any]:
        """Имитация рекомендаций по образу жизни"""
        await asyncio.sleep(1.5)

        _age = patient_profile.get("age", 45)
        _bmi = patient_profile.get("bmi", 25)

        return {
            "dietary_recommendations": {
                "general_principles": [
                    "сбалансированное питание",
                    "регулярные приемы пищи",
                ],
                "specific_foods": {
                    "recommended": ["овощи", "фрукты", "цельнозерновые"],
                    "limited": ["сладости", "жирная пища"],
                    "avoided": ["алкоголь", "курение"],
                },
                "meal_planning": {
                    "frequency": "5-6 раз в день малыми порциями",
                    "portion_sizes": "размер с ладонь",
                    "timing": "последний прием за 3 часа до сна",
                },
                "supplements": [
                    {
                        "supplement": "Витамин D",
                        "dosage": "1000 МЕ/день",
                        "rationale": "профилактика дефицита",
                    }
                ],
            },
            "physical_activity": {
                "aerobic_exercise": {
                    "type": "ходьба, плавание",
                    "frequency": "5 раз в неделю",
                    "duration": "30 минут",
                    "intensity": "умеренная",
                },
                "strength_training": {
                    "frequency": "2 раза в неделю",
                    "exercises": ["приседания", "отжимания"],
                },
                "flexibility": {
                    "activities": ["йога", "растяжка"],
                    "frequency": "ежедневно",
                },
                "precautions": [
                    "избегать перегрузок",
                    "постепенное увеличение нагрузки",
                ],
            },
            "stress_management": {
                "techniques": ["медитация", "дыхательные упражнения"],
                "relaxation_methods": ["прогулки на природе", "чтение"],
                "sleep_hygiene": ["режим сна", "комфортная температура в спальне"],
            },
            "habit_modifications": {
                "smoking_cessation": {
                    "applicable": False,
                    "strategies": [],
                    "resources": [],
                },
                "alcohol_reduction": {
                    "applicable": True,
                    "recommendations": ["не более 1 бокала вина в день"],
                },
            },
            "environmental_modifications": [
                {
                    "area": "дом",
                    "modification": "улучшение вентиляции",
                    "rationale": "качество воздуха",
                }
            ],
            "monitoring_parameters": ["вес", "АД", "самочувствие"],
            "implementation_timeline": {
                "immediate": ["начать ведение дневника питания"],
                "short_term": ["увеличить физическую активность"],
                "long_term": ["поддержание здорового образа жизни"],
            },
        }


    async def check_drug_interactions(
        self,
        medications: list[dict[str, Any]],
        patient_profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Имитация проверки лекарственных взаимодействий"""
        await asyncio.sleep(2)

        # Имитируем различные типы взаимодействий
        interactions = []
        if len(medications) >= 2:
            interactions.append(
                {
                    "drug_1": medications[0].get("name", "Препарат A"),
                    "drug_2": medications[1].get("name", "Препарат B"),
                    "interaction_type": "фармакокинетическое",
                    "mechanism": "Конкуренция за CYP3A4",
                    "severity": "умеренное",
                    "clinical_effect": "Повышение концентрации препарата B",
                    "onset": "отсроченное",
                    "documentation": "хорошо документировано",
                    "management": "Контроль концентрации в крови, возможно снижение дозы",
                    "monitoring": "Функция печени, клинические симптомы",
                }
            )

        return {
            "interaction_summary": {
                "total_interactions": len(interactions),
                "severity_distribution": {
                    "critical": 0,
                    "major": 0,
                    "moderate": len(interactions),
                    "minor": 0,
                },
                "overall_risk": "умеренный",
            },
            "interactions": interactions,
            "contraindications": [
                {
                    "medication": "Препарат A",
                    "contraindication": "тяжелая почечная недостаточность",
                    "reason": "накопление активных метаболитов",
                    "severity": "абсолютное",
                }
            ],
            "dosage_adjustments": [
                {
                    "medication": "Препарат B",
                    "current_dose": "100 мг",
                    "recommended_dose": "75 мг",
                    "reason": "взаимодействие с препаратом A",
                    "monitoring_required": "концентрация в крови",
                }
            ],
            "timing_recommendations": [
                {
                    "medications": ["Препарат A", "Препарат C"],
                    "recommendation": "принимать с интервалом 2 часа",
                    "interval": "2 часа",
                    "rationale": "предотвращение физико-химического взаимодействия",
                }
            ],
            "alternative_suggestions": [
                {
                    "problematic_drug": "Препарат A",
                    "alternatives": ["Препарат D", "Препарат E"],
                    "rationale": "отсутствие взаимодействий с текущей терапией",
                }
            ],
            "monitoring_plan": {
                "laboratory_tests": ["функция печени", "функция почек"],
                "clinical_parameters": ["АД", "ЧСС", "общее состояние"],
                "frequency": "еженедельно первый месяц, затем ежемесячно",
                "warning_signs": ["тошнота", "головокружение", "сыпь"],
            },
            "patient_education": [
                "Принимать препараты строго по расписанию",
                "Немедленно сообщать о любых побочных эффектах",
                "Не изменять дозировку без консультации врача",
            ],
        }


    async def analyze_drug_safety(
        self,
        medication: dict[str, Any],
        patient_profile: dict[str, Any],
        conditions: list[str],
    ) -> dict[str, Any]:
        """Имитация анализа безопасности препарата"""
        await asyncio.sleep(1.5)

        _med_name = medication.get("name", "Тестовый препарат")
        _age = patient_profile.get("age", 45)

        return {
            "safety_assessment": {
                "overall_safety": "осторожно",
                "risk_level": "умеренный",
                "confidence": "высокая",
            },
            "contraindications": {
                "absolute": [],
                "relative": ["возраст старше 65 лет"],
                "patient_specific": ["сопутствующая гипертония"],
            },
            "age_considerations": {
                "appropriate_for_age": True,
                "age_specific_risks": ["повышенная чувствительность"],
                "dosage_adjustment_needed": _age > 65,
                "adjustment_rationale": "снижение клиренса с возрастом",
            },
            "organ_function_impact": {
                "kidney": {
                    "clearance_affected": True,
                    "adjustment_needed": True,
                    "recommendation": "снижение дозы на 25% при КК < 60 мл/мин",
                },
                "liver": {
                    "metabolism_affected": False,
                    "adjustment_needed": False,
                    "recommendation": "стандартная дозировка",
                },
            },
            "special_populations": {
                "pregnancy": {
                    "category": "B",
                    "safety": "осторожно",
                    "considerations": "использовать только при необходимости",
                },
                "breastfeeding": {
                    "compatible": True,
                    "considerations": "минимальное проникновение в молоко",
                },
            },
            "monitoring_requirements": {
                "laboratory_monitoring": ["функция почек", "электролиты"],
                "clinical_monitoring": ["АД", "отеки", "одышка"],
                "frequency": "каждые 2 недели первый месяц",
                "baseline_tests": ["креатинин", "мочевина", "электролиты"],
            },
            "adverse_effects": {
                "common": ["головная боль", "тошнота"],
                "serious": ["аллергические реакции"],
                "patient_specific_risks": ["гипотония у пожилых"],
            },
            "drug_allergy_risk": {
                "cross_reactivity": [],
                "allergy_risk": "низкий",
                "precautions": ["начинать с минимальной дозы"],
            },
            "recommendations": {
                "proceed": True,
                "modifications": ["снижение начальной дозы", "частый мониторинг"],
                "alternatives": ["Препарат X", "Препарат Y"],
                "patient_counseling": [
                    "Принимать во время еды",
                    "Контролировать АД дома",
                    "Сообщать о головокружении",
                ],
            },
        }


    async def suggest_drug_alternatives(
        self, medication: str, reason: str, patient_profile: dict[str, Any]
    ) -> dict[str, Any]:
        """Имитация предложения альтернативных препаратов"""
        await asyncio.sleep(2)

        return {
            "original_medication": {
                "name": medication,
                "replacement_reason": reason,
                "therapeutic_class": "Ингибиторы АПФ",
            },
            "alternatives": [
                {
                    "medication_name": "Лозартан",
                    "generic_name": "Losartan",
                    "therapeutic_class": "Блокаторы рецепторов ангиотензина II",
                    "mechanism_of_action": "Блокада AT1 рецепторов",
                    "advantages": ["Не вызывает кашель", "Хорошая переносимость"],
                    "disadvantages": ["Более высокая стоимость"],
                    "dosage_forms": [
                        "таблетки 25 мг",
                        "таблетки 50 мг",
                        "таблетки 100 мг",
                    ],
                    "typical_dosage": "50-100 мг 1 раз в день",
                    "administration": "независимо от приема пищи",
                    "contraindications": [
                        "беременность",
                        "двусторонний стеноз почечных артерий",
                    ],
                    "side_effects": ["головокружение", "гиперкалиемия"],
                    "drug_interactions": ["калийсберегающие диуретики", "НПВС"],
                    "monitoring_required": ["АД", "функция почек", "калий"],
                    "cost_consideration": "средняя стоимость",
                    "availability": "широко доступен",
                    "patient_suitability": {
                        "age_appropriate": True,
                        "renal_safe": True,
                        "hepatic_safe": True,
                        "allergy_safe": True,
                        "condition_appropriate": True,
                    },
                    "recommendation_strength": "сильная",
                    "evidence_level": "высокий",
                },
                {
                    "medication_name": "Амлодипин",
                    "generic_name": "Amlodipine",
                    "therapeutic_class": "Блокаторы кальциевых каналов",
                    "mechanism_of_action": "Блокада кальциевых каналов L-типа",
                    "advantages": ["Длительное действие", "Хорошая эффективность"],
                    "disadvantages": ["Отеки лодыжек", "Приливы"],
                    "dosage_forms": ["таблетки 5 мг", "таблетки 10 мг"],
                    "typical_dosage": "5-10 мг 1 раз в день",
                    "administration": "независимо от приема пищи",
                    "contraindications": [
                        "кардиогенный шок",
                        "тяжелый аортальный стеноз",
                    ],
                    "side_effects": ["отеки", "головная боль", "приливы"],
                    "drug_interactions": ["симвастатин", "грейпфрутовый сок"],
                    "monitoring_required": ["АД", "отеки", "ЧСС"],
                    "cost_consideration": "низкая стоимость",
                    "availability": "широко доступен",
                    "patient_suitability": {
                        "age_appropriate": True,
                        "renal_safe": True,
                        "hepatic_safe": False,
                        "allergy_safe": True,
                        "condition_appropriate": True,
                    },
                    "recommendation_strength": "умеренная",
                    "evidence_level": "высокий",
                },
            ],
            "comparison_table": {
                "efficacy": {
                    "original": "высокая эффективность",
                    "alternatives": ["высокая эффективность", "высокая эффективность"],
                },
                "safety": {
                    "original": "хорошая, но кашель",
                    "alternatives": [
                        "отличная переносимость",
                        "хорошая, возможны отеки",
                    ],
                },
                "cost": {
                    "original": "низкая стоимость",
                    "alternatives": ["средняя стоимость", "низкая стоимость"],
                },
            },
            "transition_plan": {
                "washout_period": "не требуется",
                "titration_schedule": "начать с минимальной дозы, титровать еженедельно",
                "monitoring_during_transition": ["АД ежедневно", "самочувствие"],
                "patient_education": ["как измерять АД", "когда обращаться к врачу"],
            },
            "final_recommendation": {
                "preferred_alternative": "Лозартан",
                "rationale": "отсутствие кашля, хорошая переносимость",
                "implementation_priority": "высокий",
            },
        }


    async def calculate_drug_dosage(
        self, medication: str, patient_profile: dict[str, Any], indication: str
    ) -> dict[str, Any]:
        """Имитация расчета дозировки препарата"""
        await asyncio.sleep(1.5)

        _age = patient_profile.get("age", 45)
        weight = patient_profile.get("weight", 70)

        return {
            "medication_info": {
                "name": medication,
                "indication": indication,
                "therapeutic_class": "Антибиотик",
                "dosing_method": "по весу",
            },
            "standard_dosing": {
                "adult_dose": "500 мг каждые 8 часов",
                "pediatric_dose": "20 мг/кг каждые 8 часов",
                "elderly_dose": "250-500 мг каждые 8-12 часов",
                "dose_range": "250-1000 мг каждые 8 часов",
                "maximum_dose": "4 г в сутки",
            },
            "calculated_dose": {
                "recommended_dose": f"{int(weight * 10)} мг каждые 8 часов",
                "calculation_method": "10 мг/кг каждые 8 часов",
                "calculation_details": f"Вес {weight} кг × 10 мг/кг = {int(weight * 10)} мг",
                "dose_per_kg": "10 мг/кг",
                "dose_per_m2": "не применимо",
            },
            "dosing_schedule": {
                "frequency": "каждые 8 часов",
                "interval": "8 часов",
                "duration": "7-10 дней",
                "timing_with_meals": "независимо от приема пищи",
                "special_instructions": ["запивать большим количеством воды"],
            },
            "organ_function_adjustments": {
                "renal_adjustment": {
                    "needed": True,
                    "adjusted_dose": "снижение дозы на 50% при КК < 30 мл/мин",
                    "rationale": "почечная элиминация препарата",
                    "monitoring": "функция почек, креатинин",
                },
                "hepatic_adjustment": {
                    "needed": False,
                    "adjusted_dose": "стандартная доза",
                    "rationale": "минимальный печеночный метаболизм",
                    "monitoring": "не требуется",
                },
            },
            "age_specific_considerations": {
                "pediatric_considerations": "расчет по весу, контроль переносимости",
                "elderly_considerations": "начинать с меньшей дозы, частый мониторинг",
                "dose_adjustment_rationale": "изменение фармакокинетики с возрастом",
            },
            "titration_plan": {
                "starting_dose": f"{int(weight * 8)} мг каждые 8 часов",
                "titration_schedule": "увеличение до полной дозы через 2-3 дня",
                "target_dose": f"{int(weight * 10)} мг каждые 8 часов",
                "titration_parameters": "переносимость, эффективность",
                "stopping_criteria": "достижение клинического эффекта",
            },
            "monitoring_plan": {
                "therapeutic_monitoring": "клинический ответ",
                "safety_monitoring": "функция почек, аллергические реакции",
                "laboratory_tests": ["креатинин", "мочевина"],
                "clinical_parameters": ["температура", "симптомы инфекции"],
                "monitoring_frequency": "каждые 2-3 дня",
            },
            "dose_modifications": {
                "efficacy_insufficient": "увеличение дозы до максимальной",
                "adverse_effects": "снижение дозы или смена препарата",
                "drug_interactions": "корректировка с учетом взаимодействий",
                "missed_dose_instructions": "принять как можно скорее, не удваивать дозу",
            },
            "patient_counseling": {
                "administration_instructions": [
                    "принимать через равные промежутки времени",
                    "завершить полный курс лечения",
                ],
                "storage_instructions": "хранить при комнатной температуре",
                "warning_signs": ["сыпь", "диарея", "затрудненное дыхание"],
                "lifestyle_modifications": ["избегать алкоголя во время лечения"],
            },
        }


