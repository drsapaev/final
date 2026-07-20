"""Triage mixin for MockProvider.

Split from mock_provider.py.
"""
from __future__ import annotations

from app.services.ai.mock_provider_pkg._base import (
    Any,
    MockProviderMixinBase,
    asyncio,
    random,
)


class TriageMixin(MockProviderMixinBase):
    """Triage methods for MockProvider."""

    async def triage_patient(
        self,
        patient_data: dict[str, Any],
        symptoms: list[str],
        vital_signs: dict[str, Any],
    ) -> dict[str, Any]:
        """Имитация триажа пациента"""
        await asyncio.sleep(1)

        # Простая логика для демонстрации
        severity_score = 0

        # Анализ симптомов
        critical_symptoms = [
            "боль в груди",
            "затрудненное дыхание",
            "потеря сознания",
            "сильная боль",
        ]
        for symptom in symptoms:
            if any(critical in symptom.lower() for critical in critical_symptoms):
                severity_score += 3
            else:
                severity_score += 1

        # Анализ витальных показателей
        if vital_signs.get("systolic_bp", 120) > 180:
            severity_score += 3
        if vital_signs.get("heart_rate", 70) > 120:
            severity_score += 2
        if vital_signs.get("temperature", 36.6) > 38.5:
            severity_score += 2

        # Определение приоритета
        if severity_score >= 8:
            priority = "критический"
            wait_time = 0
        elif severity_score >= 5:
            priority = "высокий"
            wait_time = 15
        elif severity_score >= 3:
            priority = "средний"
            wait_time = 60
        else:
            priority = "низкий"
            wait_time = 120

        return {
            "triage_level": priority,
            "severity_score": severity_score,
            "estimated_wait_time": wait_time,
            "recommended_department": "emergency" if severity_score >= 5 else "general",
            "immediate_actions": (
                ["Мониторинг витальных функций", "Обезболивание при необходимости"]
                if severity_score >= 5
                else ["Ожидание в очереди"]
            ),
            "reassessment_interval": 15 if severity_score >= 5 else 60,
        }


    async def assess_emergency_level(
        self, clinical_presentation: dict[str, Any], patient_history: dict[str, Any]
    ) -> dict[str, Any]:
        """Имитация оценки уровня экстренности"""
        await asyncio.sleep(0.8)

        emergency_indicators = clinical_presentation.get("symptoms", [])
        critical_count = sum(
            1 for symptom in emergency_indicators if "критический" in symptom.lower()
        )

        if critical_count >= 2:
            level = "критический"
            response_time = 0
        elif critical_count >= 1:
            level = "высокий"
            response_time = 5
        else:
            level = "стандартный"
            response_time = 30

        return {
            "emergency_level": level,
            "response_time_minutes": response_time,
            "requires_immediate_attention": critical_count >= 1,
            "recommended_resources": (
                ["Реанимационная бригада", "Кардиолог"]
                if critical_count >= 2
                else ["Дежурный врач"]
            ),
            "monitoring_frequency": (
                "непрерывно" if critical_count >= 2 else "каждые 15 минут"
            ),
        }


    async def prioritize_patient_queue(
        self, patients_queue: list[dict], department_capacity: dict[str, Any]
    ) -> dict[str, Any]:
        """Имитация приоритизации очереди пациентов"""
        await asyncio.sleep(1.2)

        # Сортируем пациентов по приоритету
        prioritized = []
        for i, patient in enumerate(patients_queue):
            priority_score = random.randint(1, 10)
            prioritized.append(
                {
                    "patient_id": patient.get("id", i),
                    "name": patient.get("name", f"Пациент {i+1}"),
                    "priority_score": priority_score,
                    "estimated_service_time": random.randint(15, 45),
                    "recommended_position": i + 1,
                }
            )

        # Сортируем по приоритету
        prioritized.sort(key=lambda x: x["priority_score"], reverse=True)

        return {
            "prioritized_queue": prioritized,
            "total_patients": len(patients_queue),
            "estimated_total_time": sum(
                p["estimated_service_time"] for p in prioritized
            ),
            "capacity_utilization": min(
                100,
                len(patients_queue) / department_capacity.get("max_capacity", 10) * 100,
            ),
            "recommendations": [
                (
                    "Увеличить количество персонала"
                    if len(patients_queue) > 8
                    else "Текущая загрузка оптимальна"
                )
            ],
        }


    async def predict_deterioration_risk(
        self, patient_status: dict[str, Any], monitoring_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Имитация прогнозирования риска ухудшения"""
        await asyncio.sleep(1)

        # Анализ показателей
        risk_factors = 0
        vital_signs = monitoring_data.get("vital_signs", {})

        if vital_signs.get("heart_rate", 70) > 100:
            risk_factors += 2
        if vital_signs.get("systolic_bp", 120) < 90:
            risk_factors += 3
        if vital_signs.get("oxygen_saturation", 98) < 95:
            risk_factors += 3

        if risk_factors >= 5:
            risk_level = "высокий"
            probability = random.randint(70, 90)
        elif risk_factors >= 3:
            risk_level = "средний"
            probability = random.randint(30, 60)
        else:
            risk_level = "низкий"
            probability = random.randint(5, 25)

        return {
            "deterioration_risk": risk_level,
            "probability_percent": probability,
            "time_window_hours": 24,
            "key_indicators": (
                ["Снижение артериального давления", "Тахикардия", "Снижение сатурации"]
                if risk_factors >= 3
                else ["Стабильные показатели"]
            ),
            "recommended_actions": (
                ["Увеличить частоту мониторинга", "Подготовить к переводу в ОРИТ"]
                if risk_factors >= 5
                else ["Продолжить наблюдение"]
            ),
            "monitoring_interval_minutes": 15 if risk_factors >= 5 else 60,
        }


    async def recommend_care_pathway(
        self, triage_result: dict[str, Any], available_resources: dict[str, Any]
    ) -> dict[str, Any]:
        """Имитация рекомендации маршрута лечения"""
        await asyncio.sleep(1)

        triage_level = triage_result.get("triage_level", "низкий")

        if triage_level == "критический":
            pathway = "emergency_critical"
            department = "ОРИТ"
            specialists = ["Реаниматолог", "Кардиолог"]
        elif triage_level == "высокий":
            pathway = "emergency_urgent"
            department = "Приемное отделение"
            specialists = ["Дежурный врач", "Профильный специалист"]
        else:
            pathway = "standard_care"
            department = "Поликлиника"
            specialists = ["Участковый врач"]

        return {
            "care_pathway": pathway,
            "recommended_department": department,
            "required_specialists": specialists,
            "estimated_duration_hours": random.randint(2, 24),
            "resource_requirements": {
                "beds": 1 if triage_level in ["критический", "высокий"] else 0,
                "monitoring_equipment": triage_level == "критический",
                "laboratory_tests": True,
                "imaging_studies": triage_level in ["критический", "высокий"],
            },
            "care_steps": [
                "Первичный осмотр",
                "Диагностические процедуры",
                "Лечение",
                "Наблюдение",
            ],
            "discharge_criteria": [
                "Стабилизация состояния",
                "Отсутствие осложнений",
                "Готовность к амбулаторному лечению",
            ],
        }


