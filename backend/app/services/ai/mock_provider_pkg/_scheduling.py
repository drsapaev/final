"""Scheduling mixin for MockProvider.

Split from mock_provider.py.
"""
from __future__ import annotations

from app.services.ai.mock_provider_pkg._base import (
    Any,
    MockProviderMixinBase,
    asyncio,
)


class SchedulingMixin(MockProviderMixinBase):
    """Scheduling methods for MockProvider."""

    async def optimize_doctor_schedule(
        self, schedule_data: dict[str, Any], constraints: dict[str, Any]
    ) -> dict[str, Any]:
        """Имитация оптимизации расписания врача"""
        await asyncio.sleep(2.5)

        doctor_info = schedule_data.get("doctor", {})
        _doctor_name = doctor_info.get("name", "Доктор Иванов")

        return {
            "optimization_summary": {
                "optimization_score": 8.5,
                "improvements_made": [
                    "Оптимизированы перерывы между приемами",
                    "Сбалансирована нагрузка в течение дня",
                    "Учтены предпочтения врача",
                ],
                "efficiency_gain": "25%",
                "patient_satisfaction_impact": "Повышение на 15%",
                "doctor_workload_balance": "Оптимальный",
            },
            "optimized_schedule": [
                {
                    "time_slot": "09:00-09:30",
                    "activity": "прием пациента",
                    "patient_type": "первичный",
                    "estimated_duration": 30,
                    "complexity_level": "средняя",
                    "preparation_time": 5,
                    "buffer_time": 5,
                    "priority": "высокий",
                    "notes": "Новый пациент, требует детального осмотра",
                },
                {
                    "time_slot": "09:30-10:00",
                    "activity": "прием пациента",
                    "patient_type": "повторный",
                    "estimated_duration": 20,
                    "complexity_level": "низкая",
                    "preparation_time": 2,
                    "buffer_time": 8,
                    "priority": "средний",
                    "notes": "Контрольный осмотр",
                },
                {
                    "time_slot": "10:00-10:15",
                    "activity": "перерыв",
                    "patient_type": "",
                    "estimated_duration": 15,
                    "complexity_level": "",
                    "preparation_time": 0,
                    "buffer_time": 0,
                    "priority": "высокий",
                    "notes": "Кофе-брейк и подготовка к следующему приему",
                },
            ],
            "schedule_analytics": {
                "total_working_hours": "8 часов",
                "patient_slots": 12,
                "break_time": "1.5 часа",
                "administrative_time": "1 час",
                "utilization_rate": "85%",
                "peak_hours": ["10:00-12:00", "14:00-16:00"],
                "low_activity_periods": ["13:00-14:00"],
            },
            "constraint_compliance": {
                "working_hours_respected": True,
                "break_requirements_met": True,
                "patient_limit_observed": True,
                "appointment_types_balanced": True,
                "doctor_preferences_considered": True,
                "compliance_score": "95%",
            },
            "recommendations": {
                "immediate_actions": [
                    {
                        "action": "Перенести сложные случаи на утренние часы",
                        "rationale": "Врач более эффективен утром",
                        "expected_impact": "Повышение качества диагностики",
                        "implementation_difficulty": "легко",
                    }
                ],
                "schedule_adjustments": [
                    {
                        "adjustment": "Увеличить буферное время между приемами",
                        "reason": "Снижение стресса и улучшение качества",
                        "benefit": "Меньше задержек",
                        "trade_off": "Немного меньше приемов в день",
                    }
                ],
                "long_term_improvements": [
                    {
                        "improvement": "Внедрение системы предварительной подготовки",
                        "description": "Подготовка карт пациентов заранее",
                        "timeline": "2-3 недели",
                        "resources_needed": "Дополнительный медперсонал",
                    }
                ],
            },
            "risk_assessment": {
                "scheduling_conflicts": ["Возможное наложение экстренных случаев"],
                "overload_risks": ["Накопление усталости к концу дня"],
                "patient_wait_times": "В среднем 10-15 минут",
                "doctor_fatigue_factors": ["Высокая концентрация сложных случаев"],
                "mitigation_strategies": [
                    "Регулярные короткие перерывы",
                    "Ротация типов приемов",
                ],
            },
            "alternative_schedules": [
                {
                    "scenario": "Режим повышенной нагрузки",
                    "description": "Увеличенное количество приемов",
                    "pros": ["Больше пациентов", "Выше доходы"],
                    "cons": ["Риск усталости", "Меньше времени на пациента"],
                    "suitability_score": 6,
                }
            ],
        }


    async def predict_appointment_duration(
        self, appointment_data: dict[str, Any], historical_data: list[dict]
    ) -> dict[str, Any]:
        """Имитация прогнозирования длительности приема"""
        await asyncio.sleep(1.5)

        _appointment_type = appointment_data.get("type", "консультация")
        is_first_visit = appointment_data.get("is_first_visit", False)

        # Базовая длительность в зависимости от типа
        base_duration = 45 if is_first_visit else 30

        return {
            "duration_prediction": {
                "predicted_duration": base_duration,
                "confidence_level": "высокая",
                "prediction_range": {
                    "min_duration": base_duration - 10,
                    "max_duration": base_duration + 15,
                    "most_likely": base_duration,
                },
                "factors_considered": [
                    "тип приема",
                    "первичный/повторный визит",
                    "сложность случая",
                    "исторические данные",
                ],
            },
            "duration_breakdown": {
                "consultation_time": f"{int(base_duration * 0.6)} минут",
                "examination_time": f"{int(base_duration * 0.25)} минут",
                "documentation_time": f"{int(base_duration * 0.1)} минут",
                "patient_education_time": f"{int(base_duration * 0.05)} минут",
                "buffer_time": "5 минут",
            },
            "complexity_assessment": {
                "case_complexity": "средний",
                "complexity_factors": [
                    {
                        "factor": (
                            "новый пациент" if is_first_visit else "повторный визит"
                        ),
                        "impact": (
                            "увеличивает время на 50%"
                            if is_first_visit
                            else "стандартное время"
                        ),
                        "weight": "высокий" if is_first_visit else "средний",
                    }
                ],
                "additional_time_needed": "10-15 минут при осложнениях",
            },
            "historical_analysis": {
                "similar_cases_found": len(historical_data),
                "average_duration_similar": f"{base_duration} минут",
                "duration_variance": "±10 минут",
                "seasonal_patterns": "Зимой приемы длиннее на 5-7 минут",
                "day_of_week_impact": "Понедельники +15%, пятницы -10%",
            },
            "risk_factors": {
                "overtime_probability": "25%",
                "potential_delays": [
                    "Сложный диагностический случай",
                    "Эмоциональное состояние пациента",
                ],
                "mitigation_strategies": [
                    "Предварительный сбор анамнеза",
                    "Подготовка необходимых материалов",
                ],
            },
            "scheduling_recommendations": {
                "optimal_time_slot": "Утренние часы для сложных случаев",
                "buffer_before": "5 минут",
                "buffer_after": "10 минут",
                "special_preparations": [
                    "Подготовка медицинской карты",
                    "Проверка результатов анализов",
                ],
                "resource_requirements": [
                    "Стандартное оборудование кабинета",
                    "Доступ к лабораторным данным",
                ],
            },
            "quality_indicators": {
                "patient_satisfaction_factors": [
                    "Достаточное время для вопросов",
                    "Отсутствие спешки",
                ],
                "clinical_outcome_predictors": [
                    "Качество диагностики",
                    "Полнота обследования",
                ],
                "efficiency_metrics": [
                    "Соблюдение временных рамок",
                    "Пропускная способность",
                ],
            },
        }


    async def suggest_optimal_slots(
        self,
        doctor_profile: dict[str, Any],
        patient_requirements: dict[str, Any],
        available_slots: list[dict],
    ) -> dict[str, Any]:
        """Имитация предложения оптимальных временных слотов"""
        await asyncio.sleep(2)

        urgency = patient_requirements.get("urgency", "обычная")

        return {
            "optimal_slots": [
                {
                    "slot_id": "slot_001",
                    "date": "2024-01-20",
                    "time": "10:00",
                    "optimality_score": 9.2,
                    "ranking": 1,
                    "advantages": [
                        "Врач наиболее продуктивен в утренние часы",
                        "Минимальное время ожидания",
                        "Удобное время для пациента",
                    ],
                    "considerations": [
                        "Возможны небольшие задержки из-за предыдущего приема"
                    ],
                    "doctor_performance_at_time": "Пиковая производительность",
                    "patient_convenience": "Высокая",
                    "clinic_efficiency": "Оптимальная",
                },
                {
                    "slot_id": "slot_002",
                    "date": "2024-01-20",
                    "time": "14:30",
                    "optimality_score": 7.8,
                    "ranking": 2,
                    "advantages": ["После обеденного перерыва", "Меньше очередей"],
                    "considerations": ["Послеобеденное снижение концентрации"],
                    "doctor_performance_at_time": "Хорошая",
                    "patient_convenience": "Средняя",
                    "clinic_efficiency": "Хорошая",
                },
            ],
            "selection_criteria": {
                "primary_factors": [
                    {
                        "factor": "Производительность врача",
                        "weight": "40%",
                        "description": "Время максимальной эффективности врача",
                    },
                    {
                        "factor": "Удобство для пациента",
                        "weight": "30%",
                        "description": "Соответствие предпочтениям пациента",
                    },
                ],
                "secondary_factors": [
                    {
                        "factor": "Загруженность клиники",
                        "weight": "20%",
                        "description": "Оптимизация потока пациентов",
                    }
                ],
                "urgency_adjustments": f"Приоритет {'высокий' if urgency == 'срочная' else 'стандартный'}",
            },
            "time_analysis": {
                "peak_performance_hours": ["09:00-12:00", "15:00-17:00"],
                "patient_preference_alignment": "85%",
                "waiting_time_predictions": {
                    "before_appointment": "5-10 минут",
                    "in_clinic": "15-20 минут",
                    "total_visit_duration": "45-60 минут",
                },
                "traffic_patterns": "Утром - высокая загруженность, днем - средняя",
            },
            "alternative_options": [
                {
                    "option": "Ранняя запись (08:30)",
                    "description": "Самый первый прием дня",
                    "trade_offs": ["Раннее время", "Гарантированно без задержек"],
                    "suitability": "Подходит для ранних пташек",
                }
            ],
            "scheduling_recommendations": {
                "preparation_instructions": [
                    "Принести результаты предыдущих обследований",
                    "Подготовить список текущих лекарств",
                ],
                "arrival_time": "За 15 минут до приема",
                "documents_needed": [
                    "Паспорт",
                    "Медицинская карта",
                    "Направление врача",
                ],
                "special_considerations": [
                    "Натощак не требуется",
                    "Можно принимать обычные лекарства",
                ],
            },
            "optimization_insights": {
                "schedule_efficiency": "Высокая",
                "resource_utilization": "85%",
                "patient_flow_impact": "Положительное",
                "revenue_optimization": "Оптимальное",
                "quality_of_care_factors": [
                    "Достаточное время для осмотра",
                    "Минимальный стресс для врача",
                ],
            },
        }


    async def analyze_workload_distribution(
        self, doctors_data: list[dict], time_period: str
    ) -> dict[str, Any]:
        """Имитация анализа распределения рабочей нагрузки"""
        await asyncio.sleep(2.5)

        return {
            "workload_analysis": {
                "analysis_period": time_period,
                "total_doctors": len(doctors_data),
                "overall_utilization": "78%",
                "load_balance_score": 7.2,
                "efficiency_rating": "Хорошая",
            },
            "doctor_performance": [
                {
                    "doctor_name": "Доктор Иванов",
                    "specialty": "Кардиолог",
                    "workload_metrics": {
                        "utilization_rate": "85%",
                        "patient_throughput": "12 пациентов/день",
                        "average_appointment_duration": "35 минут",
                        "overtime_frequency": "15%",
                        "cancellation_rate": "5%",
                    },
                    "performance_category": "высокая производительность",
                    "workload_status": "оптимально",
                },
                {
                    "doctor_name": "Доктор Петров",
                    "specialty": "Терапевт",
                    "workload_metrics": {
                        "utilization_rate": "65%",
                        "patient_throughput": "8 пациентов/день",
                        "average_appointment_duration": "40 минут",
                        "overtime_frequency": "5%",
                        "cancellation_rate": "8%",
                    },
                    "performance_category": "средняя производительность",
                    "workload_status": "недогружен",
                },
            ],
            "specialty_analysis": [
                {
                    "specialty": "Кардиология",
                    "total_doctors": 2,
                    "average_workload": "80%",
                    "demand_vs_capacity": "Спрос превышает мощность на 15%",
                    "bottlenecks": ["Недостаток времени на сложные случаи"],
                    "optimization_opportunities": ["Добавление еще одного кардиолога"],
                }
            ],
            "load_distribution": {
                "underutilized_doctors": [
                    {
                        "doctor": "Доктор Петров",
                        "current_load": "65%",
                        "capacity_available": "35%",
                        "potential_additional_patients": "4-5 пациентов/день",
                    }
                ],
                "overloaded_doctors": [],
                "optimal_load_doctors": [
                    {
                        "doctor": "Доктор Иванов",
                        "load_efficiency": "Высокая",
                        "best_practices": [
                            "Эффективное управление временем",
                            "Хорошая подготовка к приемам",
                        ],
                    }
                ],
            },
            "redistribution_recommendations": [
                {
                    "recommendation": "Перенаправить часть терапевтических пациентов к Доктору Петрову",
                    "from_doctor": "Очередь терапевтов",
                    "to_doctor": "Доктор Петров",
                    "patient_volume": "3-4 пациента/день",
                    "expected_benefit": "Снижение времени ожидания на 20%",
                    "implementation_complexity": "Низкая",
                }
            ],
            "capacity_optimization": {
                "additional_capacity_needed": "1 кардиолог",
                "specialties_requiring_staff": ["Кардиология"],
                "schedule_adjustments": ["Продление рабочего дня кардиологов на 1 час"],
                "resource_reallocation": [
                    "Перераспределение кабинетов в пользу кардиологии"
                ],
            },
            "quality_impact": {
                "patient_satisfaction_risks": [
                    "Длительное ожидание записи к кардиологу"
                ],
                "care_quality_indicators": [
                    "Время на пациента достаточное",
                    "Качество диагностики высокое",
                ],
                "burnout_risk_assessment": "Низкий риск",
                "recommended_interventions": [
                    "Регулярные перерывы",
                    "Ротация сложных случаев",
                ],
            },
            "financial_analysis": {
                "revenue_optimization_potential": "15%",
                "cost_efficiency_improvements": [
                    "Оптимизация использования кабинетов",
                    "Снижение простоев",
                ],
                "roi_of_redistribution": "Положительный в течение 2 месяцев",
            },
        }


    async def generate_shift_recommendations(
        self, department_data: dict[str, Any], staffing_requirements: dict[str, Any]
    ) -> dict[str, Any]:
        """Имитация генерации рекомендаций по составлению смен"""
        await asyncio.sleep(3)

        _department_name = department_data.get("name", "Терапевтическое отделение")

        return {
            "shift_recommendations": {
                "optimization_approach": "Балансировка нагрузки с учетом пиковых часов",
                "coverage_strategy": "Непрерывное покрытие с перекрытием смен",
                "staff_utilization_target": "80-85%",
                "quality_assurance_measures": [
                    "Обязательная передача смены",
                    "Контроль качества документации",
                ],
            },
            "recommended_shifts": [
                {
                    "shift_name": "Утренняя смена",
                    "time_period": "08:00-16:00",
                    "staff_assignments": [
                        {
                            "staff_member": "Доктор Иванов",
                            "role": "Ведущий врач",
                            "responsibilities": [
                                "Прием пациентов",
                                "Консультации сложных случаев",
                            ],
                            "workload_percentage": "85%",
                        },
                        {
                            "staff_member": "Медсестра Сидорова",
                            "role": "Старшая медсестра",
                            "responsibilities": [
                                "Подготовка пациентов",
                                "Выполнение назначений",
                            ],
                            "workload_percentage": "90%",
                        },
                    ],
                    "shift_characteristics": {
                        "patient_volume_expected": "15-20 пациентов",
                        "complexity_level": "Высокий",
                        "critical_tasks": [
                            "Утренний обход",
                            "Планирование дневных процедур",
                        ],
                        "support_requirements": [
                            "Доступ к лаборатории",
                            "Связь с другими отделениями",
                        ],
                    },
                },
                {
                    "shift_name": "Дневная смена",
                    "time_period": "16:00-00:00",
                    "staff_assignments": [
                        {
                            "staff_member": "Доктор Петров",
                            "role": "Дежурный врач",
                            "responsibilities": [
                                "Неотложная помощь",
                                "Мониторинг состояния пациентов",
                            ],
                            "workload_percentage": "70%",
                        }
                    ],
                    "shift_characteristics": {
                        "patient_volume_expected": "8-12 пациентов",
                        "complexity_level": "Средний",
                        "critical_tasks": [
                            "Вечерний обход",
                            "Подготовка к ночной смене",
                        ],
                        "support_requirements": [
                            "Связь с реанимацией",
                            "Доступ к экстренной диагностике",
                        ],
                    },
                },
            ],
            "staffing_optimization": {
                "cross_training_recommendations": [
                    {
                        "staff_member": "Медсестра Козлова",
                        "additional_skills_needed": [
                            "Работа с кардиомонитором",
                            "Неотложная помощь",
                        ],
                        "training_priority": "высокий",
                        "expected_benefit": "Повышение гибкости смен",
                    }
                ],
                "workload_balancing": [
                    {
                        "issue": "Перегрузка утренней смены",
                        "solution": "Перенос части плановых процедур на дневную смену",
                        "affected_staff": ["Доктор Иванов", "Медсестра Сидорова"],
                        "implementation_steps": [
                            "Анализ процедур по срочности",
                            "Перераспределение по сменам",
                        ],
                    }
                ],
                "flexibility_measures": [
                    "Возможность вызова дополнительного персонала",
                    "Система замещения при болезни",
                ],
            },
            "compliance_analysis": {
                "labor_law_compliance": {
                    "status": "соответствует",
                    "violations": [],
                    "corrective_actions": [],
                },
                "medical_standards_compliance": {
                    "status": "соответствует",
                    "requirements_met": [
                        "Непрерывность медицинской помощи",
                        "Квалификация персонала",
                    ],
                    "gaps": [],
                },
                "union_agreement_compliance": "Полное соответствие",
            },
            "contingency_planning": {
                "sick_leave_coverage": [
                    {
                        "scenario": "Болезнь ведущего врача",
                        "coverage_plan": "Замещение дежурным врачом с продлением смены",
                        "backup_staff": [
                            "Доктор Петров",
                            "Врач из соседнего отделения",
                        ],
                        "service_impact": "Минимальное, возможны небольшие задержки",
                    }
                ],
                "emergency_protocols": [
                    {
                        "emergency_type": "Массовое поступление пациентов",
                        "staffing_response": "Вызов дополнительного персонала",
                        "escalation_procedures": [
                            "Уведомление администрации",
                            "Активация резервного персонала",
                        ],
                    }
                ],
                "seasonal_adjustments": [
                    "Усиление в период эпидемий",
                    "Сокращение в летний период",
                ],
            },
            "performance_metrics": {
                "key_indicators": [
                    {
                        "metric": "Время ожидания пациентов",
                        "target_value": "< 30 минут",
                        "measurement_method": "Автоматический учет",
                        "reporting_frequency": "Ежедневно",
                    },
                    {
                        "metric": "Загруженность персонала",
                        "target_value": "80-85%",
                        "measurement_method": "Хронометраж",
                        "reporting_frequency": "Еженедельно",
                    },
                ],
                "quality_measures": [
                    "Удовлетворенность пациентов",
                    "Количество медицинских ошибок",
                ],
                "efficiency_benchmarks": [
                    "Пропускная способность отделения",
                    "Средняя длительность госпитализации",
                ],
            },
            "implementation_plan": {
                "phase_1": {
                    "duration": "2 недели",
                    "activities": [
                        "Обучение персонала новому графику",
                        "Тестирование системы замещений",
                    ],
                    "success_criteria": [
                        "Отсутствие сбоев в работе",
                        "Положительная обратная связь персонала",
                    ],
                },
                "phase_2": {
                    "duration": "1 месяц",
                    "activities": [
                        "Полное внедрение нового графика",
                        "Мониторинг показателей эффективности",
                    ],
                    "success_criteria": [
                        "Достижение целевых показателей",
                        "Стабильная работа отделения",
                    ],
                },
                "monitoring_schedule": "Еженедельные совещания в первый месяц",
                "adjustment_triggers": [
                    "Превышение времени ожидания",
                    "Жалобы персонала на перегрузку",
                ],
            },
        }


