"""
Интеграция EMR с лабораторными данными
"""

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.orm import Session

from app.crud import lab, lab_result
from app.models.appointment import Appointment
from app.models.emr import EMR
from app.models.lab import LabOrder, LabResult

logger = logging.getLogger(__name__)


class EMRLabIntegrationService:
    """Сервис интеграции EMR с лабораторными данными"""

    def __init__(self):
        self.normal_ranges = {
            "hemoglobin": {"min": 120, "max": 160, "unit": "g/L"},
            "glucose": {"min": 3.9, "max": 5.6, "unit": "mmol/L"},
            "cholesterol": {"min": 0, "max": 5.2, "unit": "mmol/L"},
            "creatinine": {"min": 60, "max": 120, "unit": "μmol/L"},
            "alt": {"min": 0, "max": 40, "unit": "U/L"},
            "ast": {"min": 0, "max": 40, "unit": "U/L"},
        }

    async def get_patient_lab_results(
        self,
        db: Session,
        patient_id: int,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        test_types: list[str] | None = None,
        *,
        _include_trend_evidence: bool = False,
    ) -> list[dict[str, Any]]:
        """Получить лабораторные результаты пациента"""
        try:
            results = lab.get_patient_lab_results(
                db,
                patient_id,
                limit=None,
                date_from=date_from,
                date_to=date_to,
                include_observation=_include_trend_evidence,
            )

            # Фильтруем по типам тестов если указано
            if test_types:
                results = [r for r in results if r["test_code"] in test_types]

            # Форматируем результаты
            formatted_results = []
            for result in results:
                formatted_result = {
                    key: result[key]
                    for key in (
                        "id",
                        "test_name",
                        "test_code",
                        "value",
                        "unit",
                        "ref_range",
                        "abnormal",
                        "created_at",
                        "notes",
                    )
                }
                source_id = result["source_instance_id"]
                if source_id is None:
                    formatted_result["is_abnormal"] = await self._check_abnormal_value(
                        result["test_code"], result["value"], result["unit"]
                    )
                else:
                    snapshot = result["evaluation_snapshot"]
                    if not isinstance(snapshot, dict):
                        snapshot = {}
                    status = snapshot.get("status") or "unknown"
                    interpretation = snapshot.get("interpretation")
                    is_abnormal: bool | None = None
                    if status == "evaluated" and result["value"]:
                        if interpretation in (
                            "low",
                            "high",
                            "warning",
                            "abnormal",
                            "critical",
                        ):
                            is_abnormal = True
                        elif interpretation == "normal":
                            is_abnormal = False
                    formatted_result.update(
                        abnormal=is_abnormal,
                        is_abnormal=is_abnormal,
                        evaluation_status=status,
                        interpretation=interpretation,
                        source_instance_id=source_id,
                        source_root_instance_id=result["source_root_instance_id"],
                        supersedes_instance_id=result["supersedes_instance_id"],
                        released_at=result["released_at"],
                    )
                    if snapshot:
                        formatted_result.update(
                            unit=snapshot.get("unit"),
                            ref_range=result["resolved_reference_text"],
                        )
                    if _include_trend_evidence:
                        formatted_result["_trend_evidence"] = (
                            result["result_payload"],
                            snapshot,
                            result["value_numeric"],
                        )
                formatted_results.append(formatted_result)

            return formatted_results

        except Exception as e:
            logger.error(f"Ошибка получения лабораторных результатов: {e}")
            raise

    async def get_lab_result_trend(
        self, db: Session, *, patient_id: int, test_type: str, period_days: int
    ) -> dict[str, Any]:
        results = await self.get_patient_lab_results(
            db,
            patient_id,
            date_from=datetime.now(UTC) - timedelta(days=period_days),
            test_types=[test_type],
            _include_trend_evidence=True,
        )

        def result_date(result: dict[str, Any]) -> datetime:
            timestamp = result.get("released_at") or result["created_at"]
            return (
                timestamp.replace(tzinfo=UTC)
                if timestamp.tzinfo is None
                else timestamp.astimezone(UTC)
            )

        results.sort(key=lambda result: (result_date(result), result["id"]))
        trend_data = [
            {
                "date": result_date(result).date().isoformat(),
                "value": result["value"],
                "unit": result["unit"],
                "is_abnormal": result["is_abnormal"],
                "normal_range": result["ref_range"],
            }
            for result in results
        ]
        return {
            "patient_id": patient_id,
            "test_type": test_type,
            "period_days": period_days,
            "trend_data": trend_data,
            "trend_stats": self._comparable_numeric_trend(results),
            "total_measurements": len(trend_data),
        }

    @staticmethod
    def _comparable_numeric_trend(results: list[dict[str, Any]]) -> dict[str, Any]:
        # A single summary needs matching measurement context and a known
        # ordering between the numerical observations.
        comparison = None
        previous_release = None
        values: list[Decimal] = []
        assessments: list[bool] = []
        for result in results:
            if not result["value"]:
                continue
            evidence = result.get("_trend_evidence")
            if evidence is None:
                return {}
            payload, snapshot, numeric = evidence
            kind = payload.get("kind") if isinstance(payload, dict) else None
            if kind in ("qualified_numeric", "coded_qualitative", "text", "absent"):
                continue
            released_at = result["released_at"]
            if (
                kind != "numeric"
                or payload.get("comparator") is not None
                or released_at is None
                or released_at == previous_release
                or snapshot.get("visible") is not True
                or snapshot.get("status")
                not in ("evaluated", "not_evaluated", "not_applicable")
                or not isinstance(numeric, Decimal)
                or not numeric.is_finite()
            ):
                return {}
            context = tuple(
                snapshot.get(key)
                for key in (
                    "analyte_code",
                    "unit_code",
                    "unit",
                    "material_code",
                    "method_code",
                )
            )
            if not all(isinstance(code, str) and code.strip() for code in context):
                return {}
            if comparison is not None and context != comparison:
                return {}
            try:
                if Decimal(result["value"]) != numeric:
                    return {}
            except (InvalidOperation, TypeError):
                return {}
            comparison = context
            previous_release = released_at
            values.append(numeric)
            if result["is_abnormal"] is not None:
                assessments.append(result["is_abnormal"])

        if len(values) < 2:
            return {}
        if values[-1] == values[0]:
            direction = "stable"
        else:
            direction = "increasing" if values[-1] > values[0] else "decreasing"
        return {
            "min_value": float(min(values)),
            "max_value": float(max(values)),
            "avg_value": float(sum(values) / len(values)),
            "trend_direction": direction,
            "abnormal_percentage": sum(assessments) / len(assessments) * 100
            if assessments
            else None,
        }

    async def integrate_lab_results_with_emr(
        self, db: Session, emr_id: int, lab_result_ids: list[int]
    ) -> dict[str, Any]:
        """Интегрировать лабораторные результаты с EMR"""
        try:
            # Получаем EMR
            emr_record = db.query(EMR).filter(EMR.id == emr_id).first()
            if not emr_record:
                raise ValueError("EMR не найден")

            # Получаем лабораторные результаты
            appointment = (
                db.query(Appointment)
                .filter(Appointment.id == emr_record.appointment_id)
                .first()
            )
            if not appointment:
                raise ValueError("EMR appointment not found")

            lab_results = []
            for result_id in lab_result_ids:
                result = lab_result.get_lab_result(db, result_id)
                if result:
                    result_patient_id = (
                        db.query(LabOrder.patient_id)
                        .filter(LabOrder.id == result.order_id)
                        .scalar()
                    )
                    if result_patient_id != appointment.patient_id:
                        raise ValueError(
                            "Lab result does not belong to the target EMR patient"
                        )
                    lab_results.append(result)

            # Обновляем EMR с лабораторными данными
            lab_data = await self._format_lab_data_for_emr(lab_results)

            # Обновляем поле lab_results в EMR
            import json

            current_lab_results = emr_record.lab_results or "{}"
            if isinstance(current_lab_results, str):
                current_lab_results = json.loads(current_lab_results)
            current_lab_results.update(lab_data)

            # Обновляем EMR
            emr_record.lab_results = current_lab_results
            emr_record.updated_at = datetime.now(UTC)
            db.commit()

            return {
                "emr_id": emr_id,
                "integrated_results": len(lab_results),
                "lab_data": lab_data,
                "updated_at": emr_record.updated_at,
            }

        except Exception as e:
            logger.error(f"Ошибка интеграции лабораторных данных: {e}")
            raise

    async def get_abnormal_lab_results(
        self, db: Session, patient_id: int, date_from: datetime | None = None
    ) -> list[dict[str, Any]]:
        """Получить аномальные лабораторные результаты пациента"""
        try:
            results = await self.get_patient_lab_results(
                db, patient_id=patient_id, date_from=date_from
            )

            abnormal_results = []
            for result in results:
                if result["is_abnormal"] is not True:
                    continue
                finding = {
                    key: result[key]
                    for key in (
                        "id",
                        "test_name",
                        "test_code",
                        "value",
                        "unit",
                        "ref_range",
                        "created_at",
                    )
                }
                if "source_instance_id" in result:
                    finding.update(
                        evaluation_status=result["evaluation_status"],
                        interpretation=result["interpretation"],
                        source_instance_id=result["source_instance_id"],
                        source_root_instance_id=result["source_root_instance_id"],
                        supersedes_instance_id=result["supersedes_instance_id"],
                        released_at=result["released_at"],
                        severity="critical"
                        if result["interpretation"] == "critical"
                        else "unknown",
                        deviation={
                            "deviation_percent": None,
                            "deviation_type": "unknown",
                        },
                    )
                else:
                    finding["deviation"] = await self._calculate_deviation(
                        result["test_code"], result["value"], result["unit"]
                    )
                    finding["severity"] = await self._assess_severity(
                        result["test_code"], result["value"], result["unit"]
                    )
                abnormal_results.append(finding)

            return abnormal_results

        except Exception as e:
            logger.error(f"Ошибка получения аномальных результатов: {e}")
            raise

    async def generate_lab_summary_for_emr(
        self, db: Session, patient_id: int, emr_id: int
    ) -> dict[str, Any]:
        """Сгенерировать сводку лабораторных данных для EMR"""
        try:
            # Получаем последние результаты (за последние 30 дней)
            date_from = datetime.now(UTC) - timedelta(days=30)
            results = await self.get_patient_lab_results(
                db, patient_id, date_from=date_from
            )

            # Группируем по типам тестов
            grouped_results = {}
            for result in results:
                test_code = result.get("test_code", "unknown")
                if test_code not in grouped_results:
                    grouped_results[test_code] = []
                grouped_results[test_code].append(result)

            # Генерируем сводку
            summary = {
                "total_tests": len(results),
                "test_types": len(grouped_results),
                "abnormal_count": len([r for r in results if r["is_abnormal"]]),
                "latest_date": (
                    max(r.get("released_at") or r["created_at"] for r in results)
                    if results
                    else None
                ),
                "grouped_results": grouped_results,
                "recommendations": await self._generate_lab_recommendations(results),
            }

            return {
                "success": True,
                "summary": summary,
                "message": "Сводка лабораторных данных сгенерирована",
            }

        except Exception as e:
            logger.error(f"Ошибка генерации сводки лабораторных данных: {e}")
            raise

    async def notify_doctor_about_lab_results(
        self, db: Session, patient_id: int, doctor_id: int, result_id: int
    ) -> dict[str, Any]:
        """Уведомить врача о готовности лабораторных результатов"""
        try:
            # Получаем результат
            result = lab_result.get_lab_result(db, result_id)
            if not result:
                raise ValueError("Лабораторный результат не найден")

            # Проверяем, является ли результат аномальным
            is_abnormal = await self._check_abnormal_value(
                result.test_code, result.value, result.unit
            )

            # Создаем уведомление
            notification = {
                "type": "lab_result_ready",
                "patient_id": patient_id,
                "doctor_id": doctor_id,
                "result_id": result_id,
                "test_name": result.test_name,
                "is_abnormal": is_abnormal,
                "priority": "high" if is_abnormal else "normal",
                "message": f"Готов результат анализа: {result.test_name}",
                "created_at": datetime.now(UTC),
            }

            # Здесь будет отправка уведомления (email, push, etc.)
            logger.info(f"Уведомление врача {doctor_id} о результате {result_id}")

            return notification

        except Exception as e:
            logger.error(f"Ошибка уведомления врача: {e}")
            raise

    async def _check_abnormal_value(
        self, test_code: str, value: str, unit: str
    ) -> bool:
        """Проверить, является ли значение аномальным"""
        try:
            if test_code not in self.normal_ranges:
                return False

            normal_range = self.normal_ranges[test_code]
            if unit != normal_range["unit"]:
                return False

            try:
                numeric_value = float(value)
                return (
                    numeric_value < normal_range["min"]
                    or numeric_value > normal_range["max"]
                )
            except (ValueError, TypeError):
                return False

        except Exception:
            return False

    async def _calculate_deviation(
        self, test_code: str, value: float, unit: str
    ) -> dict[str, Any]:
        """Рассчитать отклонение от нормы"""
        try:
            if test_code not in self.normal_ranges:
                return {"deviation_percent": 0, "deviation_type": "unknown"}

            normal_range = self.normal_ranges[test_code]
            if unit != normal_range["unit"]:
                return {"deviation_percent": 0, "deviation_type": "unit_mismatch"}

            min_val = normal_range["min"]
            max_val = normal_range["max"]
            mid_val = (min_val + max_val) / 2

            if value < min_val:
                deviation_percent = ((min_val - value) / mid_val) * 100
                deviation_type = "below_normal"
            elif value > max_val:
                deviation_percent = ((value - max_val) / mid_val) * 100
                deviation_type = "above_normal"
            else:
                deviation_percent = 0
                deviation_type = "normal"

            return {
                "deviation_percent": round(deviation_percent, 2),
                "deviation_type": deviation_type,
            }

        except Exception:
            return {"deviation_percent": 0, "deviation_type": "error"}

    async def _assess_severity(self, test_code: str, value: float, unit: str) -> str:
        """Оценить серьезность отклонения"""
        try:
            deviation = await self._calculate_deviation(test_code, value, unit)
            deviation_percent = deviation["deviation_percent"]

            if deviation_percent < 10:
                return "mild"
            elif deviation_percent < 25:
                return "moderate"
            elif deviation_percent < 50:
                return "severe"
            else:
                return "critical"

        except Exception:
            return "unknown"

    async def _format_lab_data_for_emr(
        self, lab_results: list[LabResult]
    ) -> dict[str, Any]:
        """Форматировать лабораторные данные для EMR"""
        formatted_data = {}

        for result in lab_results:
            test_code = result.test_code or "unknown"
            if test_code not in formatted_data:
                formatted_data[test_code] = []

            formatted_data[test_code].append(
                {
                    "id": result.id,
                    "test_name": result.test_name,
                    "value": result.value,
                    "unit": result.unit,
                    "ref_range": result.ref_range,
                    "abnormal": result.abnormal,
                    "created_at": result.created_at.isoformat(),
                }
            )

        return formatted_data

    async def _generate_lab_recommendations(
        self, results: list[dict[str, Any]]
    ) -> list[str]:
        """Генерировать рекомендации на основе лабораторных данных"""
        recommendations = []

        # Keep legacy recommendations scoped to independently entered results.
        abnormal_results = [
            r for r in results if r["is_abnormal"] and "source_instance_id" not in r
        ]

        if not abnormal_results:
            if results and all(r["is_abnormal"] is False for r in results):
                recommendations.append("Все лабораторные показатели в пределах нормы")
            return recommendations

        # Группируем аномальные результаты по типам
        abnormal_by_type = {}
        for result in abnormal_results:
            test_code = result.get("test_code", "unknown")
            if test_code not in abnormal_by_type:
                abnormal_by_type[test_code] = []
            abnormal_by_type[test_code].append(result)

        # Генерируем рекомендации для каждого типа
        for test_code, _type_results in abnormal_by_type.items():
            if test_code == "glucose":
                recommendations.append(
                    "Рекомендуется контроль уровня глюкозы и консультация эндокринолога"
                )
            elif test_code == "cholesterol":
                recommendations.append(
                    "Рекомендуется диета с низким содержанием холестерина и консультация кардиолога"
                )
            elif test_code == "hemoglobin":
                recommendations.append(
                    "Рекомендуется дополнительное обследование для выявления причины анемии"
                )
            elif test_code in ["alt", "ast"]:
                recommendations.append(
                    "Рекомендуется консультация гастроэнтеролога для оценки функции печени"
                )
            else:
                recommendations.append(
                    f"Рекомендуется повторное исследование {test_code} через 2-4 недели"
                )

        return recommendations


# Создаем экземпляр сервиса
emr_lab_integration = EMRLabIntegrationService()
