"""Scheduling mixin for OpenAIProvider.

Split from openai_provider.py.
"""
from __future__ import annotations

from app.services.ai.openai_provider_pkg._base import (
    AIRequest,
    Any,
    OpenAIProviderMixinBase,
    json,
)


class SchedulingMixin(OpenAIProviderMixinBase):
    """Scheduling methods for OpenAIProvider."""

    async def optimize_doctor_schedule(
        self, schedule_data: dict[str, Any], constraints: dict[str, Any]
    ) -> dict[str, Any]:
        """Оптимизация расписания врача с учетом ограничений и предпочтений"""
        doctor_info = schedule_data.get("doctor", {})
        current_schedule = schedule_data.get("current_schedule", [])
        appointments = schedule_data.get("appointments", [])

        doctor_name = doctor_info.get("name", "не указан")
        specialty = doctor_info.get("specialty", "не указана")
        experience = doctor_info.get("experience_years", "не указан")
        preferences = doctor_info.get("preferences", {})

        working_hours = constraints.get("working_hours", {})
        break_requirements = constraints.get("break_requirements", {})
        max_patients_per_day = constraints.get("max_patients_per_day", "не указано")
        appointment_types = constraints.get("appointment_types", [])

        current_schedule_text = "\n".join(
            [
                f"- {slot.get('time', 'не указано')}: {slot.get('type', 'свободно')} ({slot.get('duration', 0)} мин)"
                for slot in current_schedule
            ]
        )

        appointments_text = "\n".join(
            [
                f"- {apt.get('time', 'не указано')}: {apt.get('patient_type', 'обычный')} пациент, {apt.get('complaint', 'не указано')} ({apt.get('estimated_duration', 30)} мин)"
                for apt in appointments
            ]
        )

        prompt = f"""
        Оптимизируйте расписание врача с учетом всех ограничений и предпочтений:

        ИНФОРМАЦИЯ О ВРАЧЕ:
        - Имя: {doctor_name}
        - Специальность: {specialty}
        - Опыт работы: {experience} лет
        - Предпочтения: {preferences}

        ТЕКУЩЕЕ РАСПИСАНИЕ:
        {current_schedule_text}

        ЗАПЛАНИРОВАННЫЕ ПРИЕМЫ:
        {appointments_text}

        ОГРАНИЧЕНИЯ:
        - Рабочие часы: {working_hours}
        - Требования к перерывам: {break_requirements}
        - Максимум пациентов в день: {max_patients_per_day}
        - Типы приемов: {appointment_types}

        Предоставьте оптимизированное расписание в формате JSON:
        {{
            "optimization_summary": {{
                "optimization_score": "оценка оптимизации от 1 до 10",
                "improvements_made": ["улучшение 1", "улучшение 2"],
                "efficiency_gain": "процент повышения эффективности",
                "patient_satisfaction_impact": "влияние на удовлетворенность пациентов",
                "doctor_workload_balance": "баланс рабочей нагрузки"
            }},
            "optimized_schedule": [
                {{
                    "time_slot": "09:00-09:30",
                    "activity": "прием пациента/перерыв/административная работа",
                    "patient_type": "первичный/повторный/срочный",
                    "estimated_duration": 30,
                    "complexity_level": "низкая/средняя/высокая",
                    "preparation_time": 5,
                    "buffer_time": 5,
                    "priority": "высокий/средний/низкий",
                    "notes": "особые замечания"
                }}
            ],
            "schedule_analytics": {{
                "total_working_hours": "общее время работы",
                "patient_slots": "количество слотов для пациентов",
                "break_time": "время перерывов",
                "administrative_time": "время на административные задачи",
                "utilization_rate": "коэффициент использования времени",
                "peak_hours": ["час пик 1", "час пик 2"],
                "low_activity_periods": ["период низкой активности 1"]
            }},
            "constraint_compliance": {{
                "working_hours_respected": true/false,
                "break_requirements_met": true/false,
                "patient_limit_observed": true/false,
                "appointment_types_balanced": true/false,
                "doctor_preferences_considered": true/false,
                "compliance_score": "оценка соблюдения ограничений"
            }},
            "recommendations": {{
                "immediate_actions": [
                    {{
                        "action": "немедленное действие",
                        "rationale": "обоснование",
                        "expected_impact": "ожидаемый эффект",
                        "implementation_difficulty": "легко/средне/сложно"
                    }}
                ],
                "schedule_adjustments": [
                    {{
                        "adjustment": "корректировка расписания",
                        "reason": "причина корректировки",
                        "benefit": "преимущество",
                        "trade_off": "компромисс"
                    }}
                ],
                "long_term_improvements": [
                    {{
                        "improvement": "долгосрочное улучшение",
                        "description": "описание",
                        "timeline": "временные рамки",
                        "resources_needed": "необходимые ресурсы"
                    }}
                ]
            }},
            "risk_assessment": {{
                "scheduling_conflicts": ["потенциальный конфликт 1", "потенциальный конфликт 2"],
                "overload_risks": ["риск перегрузки 1", "риск перегрузки 2"],
                "patient_wait_times": "прогноз времени ожидания",
                "doctor_fatigue_factors": ["фактор усталости 1", "фактор усталости 2"],
                "mitigation_strategies": ["стратегия снижения риска 1", "стратегия снижения риска 2"]
            }},
            "alternative_schedules": [
                {{
                    "scenario": "альтернативный сценарий",
                    "description": "описание сценария",
                    "pros": ["преимущество 1", "преимущество 2"],
                    "cons": ["недостаток 1", "недостаток 2"],
                    "suitability_score": "оценка подходящности"
                }}
            ]
        }}
        """

        system_prompt = """Вы специалист по оптимизации медицинских расписаний с экспертизой в управлении временем и ресурсами.
        Создаете эффективные расписания, учитывающие потребности врачей, пациентов и медицинского учреждения.
        Используете принципы lean-менеджмента и данные о производительности для оптимизации.
        Обеспечиваете баланс между эффективностью работы и качеством медицинской помощи.
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


    async def predict_appointment_duration(
        self, appointment_data: dict[str, Any], historical_data: list[dict]
    ) -> dict[str, Any]:
        """Прогнозирование длительности приема на основе исторических данных"""
        patient_info = appointment_data.get("patient", {})
        appointment_type = appointment_data.get("type", "не указан")
        complaint = appointment_data.get("complaint", "не указана")
        doctor_specialty = appointment_data.get("doctor_specialty", "не указана")
        is_first_visit = appointment_data.get("is_first_visit", False)

        # Обработка исторических данных
        historical_summary = {
            "total_appointments": len(historical_data),
            "average_duration": (
                sum(apt.get("actual_duration", 30) for apt in historical_data)
                / len(historical_data)
                if historical_data
                else 30
            ),
            "duration_range": {
                "min": (
                    min(apt.get("actual_duration", 30) for apt in historical_data)
                    if historical_data
                    else 15
                ),
                "max": (
                    max(apt.get("actual_duration", 30) for apt in historical_data)
                    if historical_data
                    else 60
                ),
            },
        }

        similar_cases = [
            apt
            for apt in historical_data
            if apt.get("type") == appointment_type
            or apt.get("complaint", "").lower() in complaint.lower()
        ]

        prompt = f"""
        Спрогнозируйте длительность медицинского приема на основе данных:

        ИНФОРМАЦИЯ О ПРИЕМЕ:
        - Тип приема: {appointment_type}
        - Жалоба пациента: {complaint}
        - Специальность врача: {doctor_specialty}
        - Первичный визит: {"да" if is_first_visit else "нет"}
        - Информация о пациенте: {patient_info}

        ИСТОРИЧЕСКИЕ ДАННЫЕ:
        - Всего приемов в базе: {historical_summary["total_appointments"]}
        - Средняя длительность: {historical_summary["average_duration"]:.1f} минут
        - Диапазон длительности: {historical_summary["duration_range"]["min"]}-{historical_summary["duration_range"]["max"]} минут
        - Похожих случаев: {len(similar_cases)}

        Предоставьте прогноз в формате JSON:
        {{
            "duration_prediction": {{
                "predicted_duration": "прогнозируемая длительность в минутах",
                "confidence_level": "высокая/средняя/низкая",
                "prediction_range": {{
                    "min_duration": "минимальная длительность",
                    "max_duration": "максимальная длительность",
                    "most_likely": "наиболее вероятная длительность"
                }},
                "factors_considered": ["фактор 1", "фактор 2", "фактор 3"]
            }},
            "duration_breakdown": {{
                "consultation_time": "время консультации",
                "examination_time": "время осмотра",
                "documentation_time": "время документирования",
                "patient_education_time": "время обучения пациента",
                "buffer_time": "буферное время"
            }},
            "complexity_assessment": {{
                "case_complexity": "простой/средний/сложный/очень сложный",
                "complexity_factors": [
                    {{
                        "factor": "фактор сложности",
                        "impact": "влияние на длительность",
                        "weight": "вес фактора"
                    }}
                ],
                "additional_time_needed": "дополнительное время при осложнениях"
            }},
            "historical_analysis": {{
                "similar_cases_found": {len(similar_cases)},
                "average_duration_similar": "средняя длительность похожих случаев",
                "duration_variance": "вариативность длительности",
                "seasonal_patterns": "сезонные паттерны",
                "day_of_week_impact": "влияние дня недели"
            }},
            "risk_factors": {{
                "overtime_probability": "вероятность превышения времени",
                "potential_delays": ["потенциальная задержка 1", "потенциальная задержка 2"],
                "mitigation_strategies": ["стратегия снижения риска 1", "стратегия снижения риска 2"]
            }},
            "scheduling_recommendations": {{
                "optimal_time_slot": "оптимальное время для приема",
                "buffer_before": "буферное время до приема",
                "buffer_after": "буферное время после приема",
                "special_preparations": ["специальная подготовка 1", "специальная подготовка 2"],
                "resource_requirements": ["требуемый ресурс 1", "требуемый ресурс 2"]
            }},
            "quality_indicators": {{
                "patient_satisfaction_factors": ["фактор удовлетворенности 1", "фактор удовлетворенности 2"],
                "clinical_outcome_predictors": ["предиктор исхода 1", "предиктор исхода 2"],
                "efficiency_metrics": ["метрика эффективности 1", "метрика эффективности 2"]
            }}
        }}
        """

        system_prompt = """Вы специалист по анализу медицинских данных с экспертизой в прогнозировании временных затрат на медицинские процедуры.
        Анализируете исторические данные и клинические факторы для точного прогнозирования длительности приемов.
        Учитываете сложность случаев, особенности пациентов и специфику медицинских специальностей.
        Предоставляете практические рекомендации по планированию времени и оптимизации расписания.
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


    async def suggest_optimal_slots(
        self,
        doctor_profile: dict[str, Any],
        patient_requirements: dict[str, Any],
        available_slots: list[dict],
    ) -> dict[str, Any]:
        """Предложение оптимальных временных слотов для записи"""
        doctor_name = doctor_profile.get("name", "не указан")
        specialty = doctor_profile.get("specialty", "не указана")
        working_patterns = doctor_profile.get("working_patterns", {})
        performance_metrics = doctor_profile.get("performance_metrics", {})

        patient_preferences = patient_requirements.get("preferences", {})
        urgency_level = patient_requirements.get("urgency", "обычная")
        appointment_type = patient_requirements.get("type", "консультация")
        estimated_duration = patient_requirements.get("estimated_duration", 30)

        slots_text = "\n".join(
            [
                f"- {slot.get('date', 'не указано')} {slot.get('time', 'не указано')}: {slot.get('duration', 30)} мин (загрузка: {slot.get('current_load', 0)}%)"
                for slot in available_slots
            ]
        )

        prompt = f"""
        Предложите оптимальные временные слоты для записи пациента:

        ПРОФИЛЬ ВРАЧА:
        - Имя: {doctor_name}
        - Специальность: {specialty}
        - Паттерны работы: {working_patterns}
        - Показатели производительности: {performance_metrics}

        ТРЕБОВАНИЯ ПАЦИЕНТА:
        - Предпочтения: {patient_preferences}
        - Срочность: {urgency_level}
        - Тип приема: {appointment_type}
        - Ожидаемая длительность: {estimated_duration} минут

        ДОСТУПНЫЕ СЛОТЫ:
        {slots_text}

        Предоставьте рекомендации в формате JSON:
        {{
            "optimal_slots": [
                {{
                    "slot_id": "идентификатор слота",
                    "date": "дата",
                    "time": "время",
                    "optimality_score": "оценка оптимальности от 1 до 10",
                    "ranking": "позиция в рейтинге",
                    "advantages": ["преимущество 1", "преимущество 2"],
                    "considerations": ["соображение 1", "соображение 2"],
                    "doctor_performance_at_time": "производительность врача в это время",
                    "patient_convenience": "удобство для пациента",
                    "clinic_efficiency": "эффективность для клиники"
                }}
            ],
            "selection_criteria": {{
                "primary_factors": [
                    {{
                        "factor": "основной фактор",
                        "weight": "вес фактора",
                        "description": "описание влияния"
                    }}
                ],
                "secondary_factors": [
                    {{
                        "factor": "второстепенный фактор",
                        "weight": "вес фактора",
                        "description": "описание влияния"
                    }}
                ],
                "urgency_adjustments": "корректировки по срочности"
            }},
            "time_analysis": {{
                "peak_performance_hours": ["час пик производительности 1", "час пик производительности 2"],
                "patient_preference_alignment": "соответствие предпочтениям пациента",
                "waiting_time_predictions": {{
                    "before_appointment": "время ожидания до приема",
                    "in_clinic": "время ожидания в клинике",
                    "total_visit_duration": "общая длительность визита"
                }},
                "traffic_patterns": "паттерны загруженности клиники"
            }},
            "alternative_options": [
                {{
                    "option": "альтернативный вариант",
                    "description": "описание варианта",
                    "trade_offs": ["компромисс 1", "компромисс 2"],
                    "suitability": "подходящность для пациента"
                }}
            ],
            "scheduling_recommendations": {{
                "preparation_instructions": ["инструкция по подготовке 1", "инструкция по подготовке 2"],
                "arrival_time": "рекомендуемое время прибытия",
                "documents_needed": ["необходимый документ 1", "необходимый документ 2"],
                "special_considerations": ["особое соображение 1", "особое соображение 2"]
            }},
            "optimization_insights": {{
                "schedule_efficiency": "эффективность расписания",
                "resource_utilization": "использование ресурсов",
                "patient_flow_impact": "влияние на поток пациентов",
                "revenue_optimization": "оптимизация доходов",
                "quality_of_care_factors": ["фактор качества помощи 1", "фактор качества помощи 2"]
            }}
        }}
        """

        system_prompt = """Вы специалист по оптимизации медицинского планирования с экспертизой в анализе временных слотов и предпочтений.
        Анализируете множественные факторы для предложения оптимальных временных слотов для медицинских приемов.
        Учитываете производительность врачей, удобство пациентов и эффективность клиники.
        Предоставляете обоснованные рекомендации с учетом всех заинтересованных сторон.
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


    async def analyze_workload_distribution(
        self, doctors_data: list[dict], time_period: str
    ) -> dict[str, Any]:
        """Анализ распределения рабочей нагрузки между врачами"""
        doctors_summary = []
        for doctor in doctors_data:
            summary = {
                "name": doctor.get("name", "не указан"),
                "specialty": doctor.get("specialty", "не указана"),
                "total_appointments": len(doctor.get("appointments", [])),
                "total_hours": doctor.get("total_working_hours", 0),
                "patient_load": doctor.get("patient_load", 0),
            }
            doctors_summary.append(summary)

        doctors_text = "\n".join(
            [
                f"- {doc['name']} ({doc['specialty']}): {doc['total_appointments']} приемов, {doc['total_hours']} часов, нагрузка {doc['patient_load']}%"
                for doc in doctors_summary
            ]
        )

        prompt = f"""
        Проанализируйте распределение рабочей нагрузки между врачами:

        ПЕРИОД АНАЛИЗА: {time_period}

        ДАННЫЕ ПО ВРАЧАМ:
        {doctors_text}

        Предоставьте анализ в формате JSON:
        {{
            "workload_analysis": {{
                "analysis_period": "{time_period}",
                "total_doctors": {len(doctors_data)},
                "overall_utilization": "общий коэффициент использования",
                "load_balance_score": "оценка сбалансированности нагрузки от 1 до 10",
                "efficiency_rating": "рейтинг эффективности"
            }},
            "doctor_performance": [
                {{
                    "doctor_name": "имя врача",
                    "specialty": "специальность",
                    "workload_metrics": {{
                        "utilization_rate": "коэффициент использования",
                        "patient_throughput": "пропускная способность",
                        "average_appointment_duration": "средняя длительность приема",
                        "overtime_frequency": "частота переработок",
                        "cancellation_rate": "частота отмен"
                    }},
                    "performance_category": "высокая/средняя/низкая производительность",
                    "workload_status": "недогружен/оптимально/перегружен/критически перегружен"
                }}
            ],
            "specialty_analysis": [
                {{
                    "specialty": "специальность",
                    "total_doctors": "количество врачей",
                    "average_workload": "средняя нагрузка",
                    "demand_vs_capacity": "соотношение спроса и мощности",
                    "bottlenecks": ["узкое место 1", "узкое место 2"],
                    "optimization_opportunities": ["возможность оптимизации 1", "возможность оптимизации 2"]
                }}
            ],
            "load_distribution": {{
                "underutilized_doctors": [
                    {{
                        "doctor": "имя врача",
                        "current_load": "текущая нагрузка",
                        "capacity_available": "доступная мощность",
                        "potential_additional_patients": "потенциальные дополнительные пациенты"
                    }}
                ],
                "overloaded_doctors": [
                    {{
                        "doctor": "имя врача",
                        "current_load": "текущая нагрузка",
                        "excess_load": "избыточная нагрузка",
                        "redistribution_needed": "необходимое перераспределение"
                    }}
                ],
                "optimal_load_doctors": [
                    {{
                        "doctor": "имя врача",
                        "load_efficiency": "эффективность нагрузки",
                        "best_practices": ["лучшая практика 1", "лучшая практика 2"]
                    }}
                ]
            }},
            "redistribution_recommendations": [
                {{
                    "recommendation": "рекомендация по перераспределению",
                    "from_doctor": "от врача",
                    "to_doctor": "к врачу",
                    "patient_volume": "объем пациентов",
                    "expected_benefit": "ожидаемая польза",
                    "implementation_complexity": "сложность внедрения"
                }}
            ],
            "capacity_optimization": {{
                "additional_capacity_needed": "необходимая дополнительная мощность",
                "specialties_requiring_staff": ["специальность 1", "специальность 2"],
                "schedule_adjustments": ["корректировка расписания 1", "корректировка расписания 2"],
                "resource_reallocation": ["перераспределение ресурса 1", "перераспределение ресурса 2"]
            }},
            "quality_impact": {{
                "patient_satisfaction_risks": ["риск удовлетворенности 1", "риск удовлетворенности 2"],
                "care_quality_indicators": ["индикатор качества 1", "индикатор качества 2"],
                "burnout_risk_assessment": "оценка риска выгорания",
                "recommended_interventions": ["рекомендуемое вмешательство 1", "рекомендуемое вмешательство 2"]
            }},
            "financial_analysis": {{
                "revenue_optimization_potential": "потенциал оптимизации доходов",
                "cost_efficiency_improvements": ["улучшение эффективности затрат 1", "улучшение эффективности затрат 2"],
                "roi_of_redistribution": "ROI от перераспределения нагрузки"
            }}
        }}
        """

        system_prompt = """Вы специалист по анализу рабочей нагрузки в медицинских учреждениях с экспертизой в оптимизации ресурсов.
        Анализируете распределение нагрузки между врачами и предлагаете стратегии оптимизации.
        Учитываете производительность, качество медицинской помощи и удовлетворенность персонала.
        Предоставляете практические рекомендации по перераспределению нагрузки и улучшению эффективности.
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


    async def generate_shift_recommendations(
        self, department_data: dict[str, Any], staffing_requirements: dict[str, Any]
    ) -> dict[str, Any]:
        """Генерация рекомендаций по составлению смен и графиков работы"""
        department_name = department_data.get("name", "не указано")
        staff_list = department_data.get("staff", [])
        current_shifts = department_data.get("current_shifts", [])
        patient_flow_patterns = department_data.get("patient_flow_patterns", {})

        min_staff_per_shift = staffing_requirements.get("min_staff_per_shift", 1)
        coverage_hours = staffing_requirements.get("coverage_hours", "24/7")
        skill_requirements = staffing_requirements.get("skill_requirements", [])
        compliance_rules = staffing_requirements.get("compliance_rules", {})

        staff_text = "\n".join(
            [
                f"- {staff.get('name', 'не указан')} ({staff.get('role', 'не указана')}, опыт: {staff.get('experience', 0)} лет, предпочтения: {staff.get('preferences', {})})"
                for staff in staff_list
            ]
        )

        shifts_text = "\n".join(
            [
                f"- {shift.get('time', 'не указано')}: {len(shift.get('staff', []))} сотрудников, загрузка {shift.get('workload', 0)}%"
                for shift in current_shifts
            ]
        )

        prompt = f"""
        Создайте оптимальные рекомендации по составлению смен и графиков работы:

        ИНФОРМАЦИЯ О ОТДЕЛЕНИИ:
        - Название: {department_name}
        - Паттерны потока пациентов: {patient_flow_patterns}

        ПЕРСОНАЛ:
        {staff_text}

        ТЕКУЩИЕ СМЕНЫ:
        {shifts_text}

        ТРЕБОВАНИЯ К ПЕРСОНАЛУ:
        - Минимум сотрудников на смену: {min_staff_per_shift}
        - Часы покрытия: {coverage_hours}
        - Требования к навыкам: {skill_requirements}
        - Правила соответствия: {compliance_rules}

        Предоставьте рекомендации в формате JSON:
        {{
            "shift_recommendations": {{
                "optimization_approach": "подход к оптимизации",
                "coverage_strategy": "стратегия покрытия",
                "staff_utilization_target": "целевое использование персонала",
                "quality_assurance_measures": ["мера обеспечения качества 1", "мера обеспечения качества 2"]
            }},
            "recommended_shifts": [
                {{
                    "shift_name": "название смены",
                    "time_period": "временной период",
                    "staff_assignments": [
                        {{
                            "staff_member": "сотрудник",
                            "role": "роль",
                            "responsibilities": ["обязанность 1", "обязанность 2"],
                            "workload_percentage": "процент нагрузки"
                        }}
                    ],
                    "shift_characteristics": {{
                        "patient_volume_expected": "ожидаемый объем пациентов",
                        "complexity_level": "уровень сложности",
                        "critical_tasks": ["критическая задача 1", "критическая задача 2"],
                        "support_requirements": ["требование поддержки 1", "требование поддержки 2"]
                    }}
                }}
            ],
            "staffing_optimization": {{
                "cross_training_recommendations": [
                    {{
                        "staff_member": "сотрудник",
                        "additional_skills_needed": ["навык 1", "навык 2"],
                        "training_priority": "высокий/средний/низкий",
                        "expected_benefit": "ожидаемая польза"
                    }}
                ],
                "workload_balancing": [
                    {{
                        "issue": "проблема баланса нагрузки",
                        "solution": "решение",
                        "affected_staff": ["сотрудник 1", "сотрудник 2"],
                        "implementation_steps": ["шаг 1", "шаг 2"]
                    }}
                ],
                "flexibility_measures": ["мера гибкости 1", "мера гибкости 2"]
            }},
            "compliance_analysis": {{
                "labor_law_compliance": {{
                    "status": "соответствует/не соответствует",
                    "violations": ["нарушение 1", "нарушение 2"],
                    "corrective_actions": ["корректирующее действие 1", "корректирующее действие 2"]
                }},
                "medical_standards_compliance": {{
                    "status": "соответствует/не соответствует",
                    "requirements_met": ["выполненное требование 1", "выполненное требование 2"],
                    "gaps": ["пробел 1", "пробел 2"]
                }},
                "union_agreement_compliance": "соответствие соглашениям с профсоюзом"
            }},
            "contingency_planning": {{
                "sick_leave_coverage": [
                    {{
                        "scenario": "сценарий больничного",
                        "coverage_plan": "план покрытия",
                        "backup_staff": ["резервный сотрудник 1", "резервный сотрудник 2"],
                        "service_impact": "влияние на услуги"
                    }}
                ],
                "emergency_protocols": [
                    {{
                        "emergency_type": "тип чрезвычайной ситуации",
                        "staffing_response": "ответ персонала",
                        "escalation_procedures": ["процедура эскалации 1", "процедура эскалации 2"]
                    }}
                ],
                "seasonal_adjustments": ["сезонная корректировка 1", "сезонная корректировка 2"]
            }},
            "performance_metrics": {{
                "key_indicators": [
                    {{
                        "metric": "ключевой показатель",
                        "target_value": "целевое значение",
                        "measurement_method": "метод измерения",
                        "reporting_frequency": "частота отчетности"
                    }}
                ],
                "quality_measures": ["мера качества 1", "мера качества 2"],
                "efficiency_benchmarks": ["бенчмарк эффективности 1", "бенчмарк эффективности 2"]
            }},
            "implementation_plan": {{
                "phase_1": {{
                    "duration": "длительность фазы 1",
                    "activities": ["активность 1", "активность 2"],
                    "success_criteria": ["критерий успеха 1", "критерий успеха 2"]
                }},
                "phase_2": {{
                    "duration": "длительность фазы 2",
                    "activities": ["активность 1", "активность 2"],
                    "success_criteria": ["критерий успеха 1", "критерий успеха 2"]
                }},
                "monitoring_schedule": "график мониторинга",
                "adjustment_triggers": ["триггер корректировки 1", "триггер корректировки 2"]
            }}
        }}
        """

        system_prompt = """Вы специалист по управлению медицинским персоналом с экспертизой в составлении оптимальных графиков работы.
        Создаете эффективные системы смен, учитывающие потребности пациентов, возможности персонала и требования регулирования.
        Используете принципы управления человеческими ресурсами и данные о производительности для оптимизации.
        Обеспечиваете соблюдение трудового законодательства и медицинских стандартов.
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


