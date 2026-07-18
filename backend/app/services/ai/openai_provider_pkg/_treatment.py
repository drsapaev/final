"""Treatment mixin for OpenAIProvider.

Split from openai_provider.py.
"""
from __future__ import annotations

from app.services.ai.openai_provider_pkg._base import (
    AIRequest,
    Any,
    OpenAIProviderMixinBase,
    json,
)


class TreatmentMixin(OpenAIProviderMixinBase):
    """Treatment methods for OpenAIProvider."""

    async def generate_treatment_plan(
        self,
        patient_data: dict[str, Any],
        diagnosis: str,
        medical_history: list[dict] | None = None,
    ) -> dict[str, Any]:
        """Генерация персонализированного плана лечения"""
        age = patient_data.get("age", "не указан")
        gender = patient_data.get("gender", "не указан")
        weight = patient_data.get("weight", "не указан")
        allergies = patient_data.get("allergies", [])
        comorbidities = patient_data.get("comorbidities", [])

        history_text = ""
        if medical_history:
            history_text = "\n".join(
                [
                    f"- {h.get('date', 'дата не указана')}: {h.get('diagnosis', 'диагноз не указан')} - {h.get('treatment', 'лечение не указано')}"
                    for h in medical_history
                ]
            )

        prompt = f"""
        Создайте персонализированный план лечения для пациента:

        ДАННЫЕ ПАЦИЕНТА:
        - Возраст: {age}
        - Пол: {gender}
        - Вес: {weight}
        - Аллергии: {', '.join(allergies) if allergies else 'не указаны'}
        - Сопутствующие заболевания: {', '.join(comorbidities) if comorbidities else 'не указаны'}

        ТЕКУЩИЙ ДИАГНОЗ: {diagnosis}

        МЕДИЦИНСКАЯ ИСТОРИЯ:
        {history_text if history_text else 'История отсутствует'}

        Предоставьте комплексный план лечения в формате JSON с целями лечения, медикаментозной терапией, немедикаментозными вмешательствами, рекомендациями по образу жизни и графиком наблюдения.
        """

        system_prompt = """Вы опытный врач-клиницист с экспертизой в персонализированной медицине.
        Создаете индивидуальные планы лечения с учетом всех особенностей пациента.
        Всегда учитываете возраст, пол, сопутствующие заболевания, аллергии и историю болезни.
        Ответы даете только в формате JSON."""

        request = AIRequest(
            prompt=prompt, system_prompt=system_prompt, temperature=0.2, max_tokens=2500
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


    async def optimize_medication_regimen(
        self,
        current_medications: list[dict],
        patient_profile: dict[str, Any],
        condition: str,
    ) -> dict[str, Any]:
        """Оптимизация медикаментозной терапии"""
        age = patient_profile.get("age", "не указан")
        gender = patient_profile.get("gender", "не указан")
        weight = patient_profile.get("weight", "не указан")
        kidney_function = patient_profile.get("kidney_function", "не указана")
        liver_function = patient_profile.get("liver_function", "не указана")
        allergies = patient_profile.get("allergies", [])

        medications_text = "\n".join(
            [
                f"- {med.get('name', 'не указано')}: {med.get('dosage', 'не указано')} {med.get('frequency', 'не указано')}"
                for med in current_medications
            ]
        )

        prompt = f"""
        Оптимизируйте медикаментозную терапию для пациента:

        ПРОФИЛЬ ПАЦИЕНТА:
        - Возраст: {age}
        - Пол: {gender}
        - Вес: {weight}
        - Функция почек: {kidney_function}
        - Функция печени: {liver_function}
        - Аллергии: {', '.join(allergies) if allergies else 'не указаны'}

        СОСТОЯНИЕ: {condition}

        ТЕКУЩИЕ ПРЕПАРАТЫ:
        {medications_text}

        Предоставьте оптимизированный план в формате JSON с изменениями препаратов, анализом взаимодействий и рекомендациями по мониторингу.
        """

        system_prompt = """Вы клинический фармаколог с экспертизой в оптимизации лекарственной терапии.
        Анализируете взаимодействия препаратов, корректируете дозировки с учетом функции органов.
        Всегда учитываете безопасность, эффективность и приверженность лечению.
        Ответы даете только в формате JSON."""

        request = AIRequest(
            prompt=prompt, system_prompt=system_prompt, temperature=0.1, max_tokens=2000
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


    async def assess_treatment_effectiveness(
        self, treatment_history: list[dict], patient_response: dict[str, Any]
    ) -> dict[str, Any]:
        """Оценка эффективности лечения"""
        history_text = "\n".join(
            [
                f"- {h.get('date', 'дата не указана')}: {h.get('treatment', 'лечение не указано')} - {h.get('outcome', 'результат не указан')}"
                for h in treatment_history
            ]
        )

        current_symptoms = patient_response.get("symptoms", [])
        side_effects = patient_response.get("side_effects", [])
        quality_of_life = patient_response.get("quality_of_life_score", "не указан")
        adherence = patient_response.get("adherence_rate", "не указан")

        prompt = f"""
        Оцените эффективность проводимого лечения:

        ИСТОРИЯ ЛЕЧЕНИЯ:
        {history_text}

        ТЕКУЩИЙ ОТВЕТ ПАЦИЕНТА:
        - Симптомы: {', '.join(current_symptoms) if current_symptoms else 'отсутствуют'}
        - Побочные эффекты: {', '.join(side_effects) if side_effects else 'отсутствуют'}
        - Качество жизни (1-10): {quality_of_life}
        - Приверженность лечению (%): {adherence}

        Предоставьте анализ эффективности в формате JSON с оценкой ответа на лечение, анализом побочных эффектов и рекомендациями по корректировке.
        """

        system_prompt = """Вы опытный врач-клиницист с экспертизой в оценке эффективности лечения.
        Анализируете динамику состояния пациента, приверженность терапии и качество жизни.
        Даете объективную оценку и конкретные рекомендации по корректировке лечения.
        Ответы даете только в формате JSON."""

        request = AIRequest(
            prompt=prompt, system_prompt=system_prompt, temperature=0.2, max_tokens=2000
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


    async def suggest_lifestyle_modifications(
        self, patient_profile: dict[str, Any], conditions: list[str]
    ) -> dict[str, Any]:
        """Рекомендации по изменению образа жизни"""
        age = patient_profile.get("age", "не указан")
        gender = patient_profile.get("gender", "не указан")
        bmi = patient_profile.get("bmi", "не указан")
        activity_level = patient_profile.get("activity_level", "не указан")
        smoking_status = patient_profile.get("smoking_status", "не указан")
        alcohol_consumption = patient_profile.get("alcohol_consumption", "не указано")
        occupation = patient_profile.get("occupation", "не указана")

        conditions_text = ", ".join(conditions) if conditions else "не указаны"

        prompt = f"""
        Разработайте персонализированные рекомендации по изменению образа жизни:

        ПРОФИЛЬ ПАЦИЕНТА:
        - Возраст: {age}
        - Пол: {gender}
        - ИМТ: {bmi}
        - Уровень активности: {activity_level}
        - Курение: {smoking_status}
        - Употребление алкоголя: {alcohol_consumption}
        - Профессия: {occupation}

        СОСТОЯНИЯ: {conditions_text}

        Предоставьте рекомендации в формате JSON с диетическими рекомендациями, физической активностью, управлением стрессом и модификацией привычек.
        """

        system_prompt = """Вы специалист по профилактической медицине и здоровому образу жизни.
        Создаете персонализированные, реалистичные и научно обоснованные рекомендации.
        Учитываете индивидуальные особенности пациента и его заболевания.
        Ответы даете только в формате JSON."""

        request = AIRequest(
            prompt=prompt, system_prompt=system_prompt, temperature=0.2, max_tokens=2500
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


    async def check_drug_interactions(
        self,
        medications: list[dict[str, Any]],
        patient_profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Проверка лекарственных взаимодействий"""
        medications_text = "\n".join(
            [
                f"- {med.get('name', 'не указано')}: {med.get('dosage', 'не указано')} {med.get('frequency', 'не указано')}"
                for med in medications
            ]
        )

        patient_info = ""
        if patient_profile:
            age = patient_profile.get("age", "не указан")
            gender = patient_profile.get("gender", "не указан")
            weight = patient_profile.get("weight", "не указан")
            kidney_function = patient_profile.get("kidney_function", "не указана")
            liver_function = patient_profile.get("liver_function", "не указана")
            allergies = patient_profile.get("allergies", [])

            patient_info = f"""
            ПРОФИЛЬ ПАЦИЕНТА:
            - Возраст: {age}
            - Пол: {gender}
            - Вес: {weight}
            - Функция почек: {kidney_function}
            - Функция печени: {liver_function}
            - Аллергии: {', '.join(allergies) if allergies else 'не указаны'}
            """

        prompt = f"""
        Проанализируйте лекарственные взаимодействия между препаратами:

        ПРЕПАРАТЫ:
        {medications_text}
        {patient_info}

        Предоставьте детальный анализ в формате JSON:
        {{
            "interaction_summary": {{
                "total_interactions": "количество найденных взаимодействий",
                "severity_distribution": {{
                    "critical": 0,
                    "major": 0,
                    "moderate": 0,
                    "minor": 0
                }},
                "overall_risk": "низкий/умеренный/высокий/критический"
            }},
            "interactions": [
                {{
                    "drug_1": "название первого препарата",
                    "drug_2": "название второго препарата",
                    "interaction_type": "фармакокинетическое/фармакодинамическое/физико-химическое",
                    "mechanism": "механизм взаимодействия",
                    "severity": "критическое/значительное/умеренное/незначительное",
                    "clinical_effect": "клинический эффект взаимодействия",
                    "onset": "быстрое/отсроченное/неопределенное",
                    "documentation": "хорошо документировано/умеренно/слабо",
                    "management": "рекомендации по управлению взаимодействием",
                    "monitoring": "что контролировать"
                }}
            ],
            "contraindications": [
                {{
                    "medication": "название препарата",
                    "contraindication": "противопоказание",
                    "reason": "причина противопоказания",
                    "severity": "абсолютное/относительное"
                }}
            ],
            "dosage_adjustments": [
                {{
                    "medication": "название препарата",
                    "current_dose": "текущая доза",
                    "recommended_dose": "рекомендуемая доза",
                    "reason": "причина корректировки",
                    "monitoring_required": "необходимый мониторинг"
                }}
            ],
            "timing_recommendations": [
                {{
                    "medications": ["препарат 1", "препарат 2"],
                    "recommendation": "рекомендация по времени приема",
                    "interval": "интервал между приемами",
                    "rationale": "обоснование"
                }}
            ],
            "alternative_suggestions": [
                {{
                    "problematic_drug": "проблемный препарат",
                    "alternatives": ["альтернатива 1", "альтернатива 2"],
                    "rationale": "обоснование замены"
                }}
            ],
            "monitoring_plan": {{
                "laboratory_tests": ["анализ 1", "анализ 2"],
                "clinical_parameters": ["параметр 1", "параметр 2"],
                "frequency": "частота контроля",
                "warning_signs": ["признак 1", "признак 2"]
            }},
            "patient_education": [
                "важная информация для пациента 1",
                "важная информация для пациента 2"
            ]
        }}
        """

        system_prompt = """Вы клинический фармаколог с экспертизой в лекарственных взаимодействиях.
        Анализируете взаимодействия препаратов на основе современных клинических данных.
        Учитываете фармакокинетику, фармакодинамику и индивидуальные особенности пациента.
        Предоставляете практические рекомендации по безопасному применению препаратов.
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


    async def analyze_drug_safety(
        self,
        medication: dict[str, Any],
        patient_profile: dict[str, Any],
        conditions: list[str],
    ) -> dict[str, Any]:
        """Анализ безопасности препарата для конкретного пациента"""
        med_name = medication.get("name", "не указано")
        med_dosage = medication.get("dosage", "не указано")
        med_frequency = medication.get("frequency", "не указано")

        age = patient_profile.get("age", "не указан")
        gender = patient_profile.get("gender", "не указан")
        weight = patient_profile.get("weight", "не указан")
        pregnancy_status = patient_profile.get("pregnancy_status", "не указан")
        breastfeeding = patient_profile.get("breastfeeding", "не указано")
        kidney_function = patient_profile.get("kidney_function", "не указана")
        liver_function = patient_profile.get("liver_function", "не указана")
        allergies = patient_profile.get("allergies", [])

        conditions_text = ", ".join(conditions) if conditions else "не указаны"

        prompt = f"""
        Проанализируйте безопасность препарата для конкретного пациента:

        ПРЕПАРАТ:
        - Название: {med_name}
        - Дозировка: {med_dosage}
        - Частота: {med_frequency}

        ПРОФИЛЬ ПАЦИЕНТА:
        - Возраст: {age}
        - Пол: {gender}
        - Вес: {weight}
        - Беременность: {pregnancy_status}
        - Грудное вскармливание: {breastfeeding}
        - Функция почек: {kidney_function}
        - Функция печени: {liver_function}
        - Аллергии: {', '.join(allergies) if allergies else 'не указаны'}

        ЗАБОЛЕВАНИЯ: {conditions_text}

        Предоставьте анализ безопасности в формате JSON:
        {{
            "safety_assessment": {{
                "overall_safety": "безопасно/осторожно/не рекомендуется/противопоказано",
                "risk_level": "низкий/умеренный/высокий/критический",
                "confidence": "высокая/средняя/низкая"
            }},
            "contraindications": {{
                "absolute": ["абсолютное противопоказание 1"],
                "relative": ["относительное противопоказание 1"],
                "patient_specific": ["специфичное для пациента противопоказание 1"]
            }},
            "age_considerations": {{
                "appropriate_for_age": true/false,
                "age_specific_risks": ["риск 1", "риск 2"],
                "dosage_adjustment_needed": true/false,
                "adjustment_rationale": "обоснование корректировки дозы"
            }},
            "organ_function_impact": {{
                "kidney": {{
                    "clearance_affected": true/false,
                    "adjustment_needed": true/false,
                    "recommendation": "рекомендация"
                }},
                "liver": {{
                    "metabolism_affected": true/false,
                    "adjustment_needed": true/false,
                    "recommendation": "рекомендация"
                }}
            }},
            "special_populations": {{
                "pregnancy": {{
                    "category": "A/B/C/D/X",
                    "safety": "безопасно/осторожно/не рекомендуется/противопоказано",
                    "considerations": "особые соображения"
                }},
                "breastfeeding": {{
                    "compatible": true/false,
                    "considerations": "особые соображения"
                }}
            }},
            "monitoring_requirements": {{
                "laboratory_monitoring": ["анализ 1", "анализ 2"],
                "clinical_monitoring": ["параметр 1", "параметр 2"],
                "frequency": "частота контроля",
                "baseline_tests": ["базовый тест 1", "базовый тест 2"]
            }},
            "adverse_effects": {{
                "common": ["частый побочный эффект 1"],
                "serious": ["серьезный побочный эффект 1"],
                "patient_specific_risks": ["специфичный риск 1"]
            }},
            "drug_allergy_risk": {{
                "cross_reactivity": ["препарат с перекрестной реактивностью"],
                "allergy_risk": "низкий/умеренный/высокий",
                "precautions": ["предосторожность 1"]
            }},
            "recommendations": {{
                "proceed": true/false,
                "modifications": ["модификация 1", "модификация 2"],
                "alternatives": ["альтернатива 1", "альтернатива 2"],
                "patient_counseling": ["совет пациенту 1", "совет пациенту 2"]
            }}
        }}
        """

        system_prompt = """Вы клинический фармаколог с экспертизой в безопасности лекарственных средств.
        Оцениваете безопасность препаратов с учетом индивидуальных особенностей пациента.
        Учитываете возраст, пол, функцию органов, сопутствующие заболевания и аллергии.
        Предоставляете практические рекомендации по безопасному применению.
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


    async def suggest_drug_alternatives(
        self, medication: str, reason: str, patient_profile: dict[str, Any]
    ) -> dict[str, Any]:
        """Предложение альтернативных препаратов"""
        age = patient_profile.get("age", "не указан")
        gender = patient_profile.get("gender", "не указан")
        weight = patient_profile.get("weight", "не указан")
        kidney_function = patient_profile.get("kidney_function", "не указана")
        liver_function = patient_profile.get("liver_function", "не указана")
        allergies = patient_profile.get("allergies", [])
        conditions = patient_profile.get("conditions", [])

        prompt = f"""
        Предложите альтернативные препараты для замены:

        ПРЕПАРАТ ДЛЯ ЗАМЕНЫ: {medication}
        ПРИЧИНА ЗАМЕНЫ: {reason}

        ПРОФИЛЬ ПАЦИЕНТА:
        - Возраст: {age}
        - Пол: {gender}
        - Вес: {weight}
        - Функция почек: {kidney_function}
        - Функция печени: {liver_function}
        - Аллергии: {', '.join(allergies) if allergies else 'не указаны'}
        - Заболевания: {', '.join(conditions) if conditions else 'не указаны'}

        Предоставьте альтернативы в формате JSON:
        {{
            "original_medication": {{
                "name": "{medication}",
                "replacement_reason": "{reason}",
                "therapeutic_class": "терапевтический класс"
            }},
            "alternatives": [
                {{
                    "medication_name": "название альтернативного препарата",
                    "generic_name": "международное название",
                    "therapeutic_class": "терапевтический класс",
                    "mechanism_of_action": "механизм действия",
                    "advantages": ["преимущество 1", "преимущество 2"],
                    "disadvantages": ["недостаток 1", "недостаток 2"],
                    "dosage_forms": ["форма выпуска 1", "форма выпуска 2"],
                    "typical_dosage": "типичная дозировка",
                    "administration": "способ применения",
                    "contraindications": ["противопоказание 1", "противопоказание 2"],
                    "side_effects": ["побочный эффект 1", "побочный эффект 2"],
                    "drug_interactions": ["взаимодействие 1", "взаимодействие 2"],
                    "monitoring_required": ["что контролировать 1", "что контролировать 2"],
                    "cost_consideration": "экономические соображения",
                    "availability": "доступность",
                    "patient_suitability": {{
                        "age_appropriate": true/false,
                        "renal_safe": true/false,
                        "hepatic_safe": true/false,
                        "allergy_safe": true/false,
                        "condition_appropriate": true/false
                    }},
                    "recommendation_strength": "сильная/умеренная/слабая",
                    "evidence_level": "высокий/средний/низкий"
                }}
            ],
            "comparison_table": {{
                "efficacy": {{
                    "original": "эффективность оригинального препарата",
                    "alternatives": ["эффективность альтернативы 1", "эффективность альтернативы 2"]
                }},
                "safety": {{
                    "original": "безопасность оригинального препарата",
                    "alternatives": ["безопасность альтернативы 1", "безопасность альтернативы 2"]
                }},
                "cost": {{
                    "original": "стоимость оригинального препарата",
                    "alternatives": ["стоимость альтернативы 1", "стоимость альтернативы 2"]
                }}
            }},
            "transition_plan": {{
                "washout_period": "период отмены",
                "titration_schedule": "схема титрования",
                "monitoring_during_transition": ["что контролировать при переходе"],
                "patient_education": ["что объяснить пациенту"]
            }},
            "final_recommendation": {{
                "preferred_alternative": "предпочтительная альтернатива",
                "rationale": "обоснование выбора",
                "implementation_priority": "высокий/средний/низкий"
            }}
        }}
        """

        system_prompt = """Вы клинический фармаколог с экспертизой в подборе альтернативных препаратов.
        Предлагаете безопасные и эффективные альтернативы с учетом индивидуальных особенностей пациента.
        Учитываете эффективность, безопасность, стоимость и доступность препаратов.
        Предоставляете практические рекомендации по переходу на альтернативную терапию.
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


    async def calculate_drug_dosage(
        self, medication: str, patient_profile: dict[str, Any], indication: str
    ) -> dict[str, Any]:
        """Расчет дозировки препарата"""
        age = patient_profile.get("age", "не указан")
        gender = patient_profile.get("gender", "не указан")
        weight = patient_profile.get("weight", "не указан")
        height = patient_profile.get("height", "не указан")
        bsa = patient_profile.get("body_surface_area", "не указана")
        creatinine = patient_profile.get("creatinine", "не указан")
        creatinine_clearance = patient_profile.get("creatinine_clearance", "не указан")
        liver_function = patient_profile.get("liver_function", "не указана")

        prompt = f"""
        Рассчитайте оптимальную дозировку препарата для пациента:

        ПРЕПАРАТ: {medication}
        ПОКАЗАНИЕ: {indication}

        ПАРАМЕТРЫ ПАЦИЕНТА:
        - Возраст: {age}
        - Пол: {gender}
        - Вес: {weight} кг
        - Рост: {height} см
        - Площадь поверхности тела: {bsa} м²
        - Креатинин: {creatinine} мкмоль/л
        - Клиренс креатинина: {creatinine_clearance} мл/мин
        - Функция печени: {liver_function}

        Предоставьте расчет дозировки в формате JSON:
        {{
            "medication_info": {{
                "name": "{medication}",
                "indication": "{indication}",
                "therapeutic_class": "терапевтический класс",
                "dosing_method": "по весу/по площади поверхности/фиксированная доза"
            }},
            "standard_dosing": {{
                "adult_dose": "стандартная доза для взрослых",
                "pediatric_dose": "детская доза (если применимо)",
                "elderly_dose": "доза для пожилых",
                "dose_range": "диапазон доз",
                "maximum_dose": "максимальная доза"
            }},
            "calculated_dose": {{
                "recommended_dose": "рекомендуемая доза для пациента",
                "calculation_method": "метод расчета",
                "calculation_details": "детали расчета",
                "dose_per_kg": "доза на кг веса",
                "dose_per_m2": "доза на м² поверхности тела (если применимо)"
            }},
            "dosing_schedule": {{
                "frequency": "частота приема",
                "interval": "интервал между приемами",
                "duration": "продолжительность курса",
                "timing_with_meals": "связь с приемом пищи",
                "special_instructions": ["особые указания"]
            }},
            "organ_function_adjustments": {{
                "renal_adjustment": {{
                    "needed": true/false,
                    "adjusted_dose": "скорректированная доза",
                    "rationale": "обоснование корректировки",
                    "monitoring": "необходимый мониторинг"
                }},
                "hepatic_adjustment": {{
                    "needed": true/false,
                    "adjusted_dose": "скорректированная доза",
                    "rationale": "обоснование корректировки",
                    "monitoring": "необходимый мониторинг"
                }}
            }},
            "age_specific_considerations": {{
                "pediatric_considerations": "особенности для детей",
                "elderly_considerations": "особенности для пожилых",
                "dose_adjustment_rationale": "обоснование возрастной корректировки"
            }},
            "titration_plan": {{
                "starting_dose": "начальная доза",
                "titration_schedule": "схема титрования",
                "target_dose": "целевая доза",
                "titration_parameters": "параметры для титрования",
                "stopping_criteria": "критерии прекращения титрования"
            }},
            "monitoring_plan": {{
                "therapeutic_monitoring": "терапевтический мониторинг",
                "safety_monitoring": "мониторинг безопасности",
                "laboratory_tests": ["лабораторный тест 1", "лабораторный тест 2"],
                "clinical_parameters": ["клинический параметр 1", "клинический параметр 2"],
                "monitoring_frequency": "частота мониторинга"
            }},
            "dose_modifications": {{
                "efficacy_insufficient": "корректировка при недостаточной эффективности",
                "adverse_effects": "корректировка при побочных эффектах",
                "drug_interactions": "корректировка при взаимодействиях",
                "missed_dose_instructions": "инструкции при пропуске дозы"
            }},
            "patient_counseling": {{
                "administration_instructions": ["инструкция по применению 1"],
                "storage_instructions": "условия хранения",
                "warning_signs": ["тревожный признак 1", "тревожный признак 2"],
                "lifestyle_modifications": ["модификация образа жизни 1"]
            }}
        }}
        """

        system_prompt = """Вы клинический фармаколог с экспертизой в расчете дозировок лекарственных средств.
        Рассчитываете индивидуальные дозировки с учетом возраста, веса, функции органов и показаний.
        Учитываете фармакокинетику, фармакодинамику и индивидуальную вариабельность.
        Предоставляете практические рекомендации по дозированию и мониторингу.
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


