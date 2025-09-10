"""
Интеграция EMR с лабораторными данными
"""
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models.lab import LabResult, LabOrder
from app.models.emr import EMR
from app.crud import lab_result, emr

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
            "ast": {"min": 0, "max": 40, "unit": "U/L"}
        }

    async def get_patient_lab_results(
        self,
        db: Session,
        patient_id: int,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        test_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Получить лабораторные результаты пациента"""
        try:
            # Получаем результаты анализов
            results = lab_result.get_lab_results_by_patient(
                db,
                patient_id=patient_id,
                date_from=date_from,
                date_to=date_to
            )
            
            # Фильтруем по типам тестов если указано
            if test_types:
                results = [r for r in results if r.test_code in test_types]
            
            # Форматируем результаты
            formatted_results = []
            for result in results:
                formatted_result = {
                    "id": result.id,
                    "test_name": result.test_name,
                    "test_code": result.test_code,
                    "value": result.value,
                    "unit": result.unit,
                    "ref_range": result.ref_range,
                    "abnormal": result.abnormal,
                    "is_abnormal": await self._check_abnormal_value(
                        result.test_code, result.value, result.unit
                    ),
                    "created_at": result.created_at,
                    "notes": result.notes
                }
                formatted_results.append(formatted_result)
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Ошибка получения лабораторных результатов: {e}")
            raise

    async def integrate_lab_results_with_emr(
        self,
        db: Session,
        emr_id: int,
        lab_result_ids: List[int]
    ) -> Dict[str, Any]:
        """Интегрировать лабораторные результаты с EMR"""
        try:
            # Получаем EMR
            emr_record = db.query(EMR).filter(EMR.id == emr_id).first()
            if not emr_record:
                raise ValueError("EMR не найден")
            
            # Получаем лабораторные результаты
            lab_results = []
            for result_id in lab_result_ids:
                result = lab_result.get_lab_result(db, result_id)
                if result:
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
            emr_record.updated_at = datetime.utcnow()
            db.commit()
            
            return {
                "emr_id": emr_id,
                "integrated_results": len(lab_results),
                "lab_data": lab_data,
                "updated_at": emr_record.updated_at
            }
            
        except Exception as e:
            logger.error(f"Ошибка интеграции лабораторных данных: {e}")
            raise

    async def get_abnormal_lab_results(
        self,
        db: Session,
        patient_id: int,
        date_from: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Получить аномальные лабораторные результаты пациента"""
        try:
            # Получаем все результаты за период
            results = lab_result.get_lab_results_by_patient(
                db,
                patient_id=patient_id,
                date_from=date_from
            )
            
            abnormal_results = []
            for result in results:
                is_abnormal = await self._check_abnormal_value(
                    result.test_code, result.value, result.unit
                )
                
                if is_abnormal:
                    abnormal_results.append({
                        "id": result.id,
                        "test_name": result.test_name,
                        "test_code": result.test_code,
                        "value": result.value,
                        "unit": result.unit,
                        "ref_range": result.ref_range,
                        "deviation": await self._calculate_deviation(
                            result.test_code, result.value, result.unit
                        ),
                        "created_at": result.created_at,
                        "severity": await self._assess_severity(
                            result.test_code, result.value, result.unit
                        )
                    })
            
            return abnormal_results
            
        except Exception as e:
            logger.error(f"Ошибка получения аномальных результатов: {e}")
            raise

    async def generate_lab_summary_for_emr(
        self,
        db: Session,
        patient_id: int,
        emr_id: int
    ) -> Dict[str, Any]:
        """Сгенерировать сводку лабораторных данных для EMR"""
        try:
            # Получаем последние результаты (за последние 30 дней)
            date_from = datetime.utcnow() - timedelta(days=30)
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
                "latest_date": max([r["created_at"] for r in results]) if results else None,
                "grouped_results": grouped_results,
                "recommendations": await self._generate_lab_recommendations(results)
            }
            
            return {
                "success": True,
                "summary": summary,
                "message": "Сводка лабораторных данных сгенерирована"
            }
            
        except Exception as e:
            logger.error(f"Ошибка генерации сводки лабораторных данных: {e}")
            raise

    async def notify_doctor_about_lab_results(
        self,
        db: Session,
        patient_id: int,
        doctor_id: int,
        result_id: int
    ) -> Dict[str, Any]:
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
                "created_at": datetime.utcnow()
            }
            
            # Здесь будет отправка уведомления (email, push, etc.)
            logger.info(f"Уведомление врача {doctor_id} о результате {result_id}")
            
            return notification
            
        except Exception as e:
            logger.error(f"Ошибка уведомления врача: {e}")
            raise

    async def _check_abnormal_value(
        self,
        test_code: str,
        value: str,
        unit: str
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
                return numeric_value < normal_range["min"] or numeric_value > normal_range["max"]
            except (ValueError, TypeError):
                return False
            
        except Exception:
            return False

    async def _calculate_deviation(
        self,
        test_code: str,
        value: float,
        unit: str
    ) -> Dict[str, Any]:
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
                "deviation_type": deviation_type
            }
            
        except Exception:
            return {"deviation_percent": 0, "deviation_type": "error"}

    async def _assess_severity(
        self,
        test_code: str,
        value: float,
        unit: str
    ) -> str:
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
        self,
        lab_results: List[LabResult]
    ) -> Dict[str, Any]:
        """Форматировать лабораторные данные для EMR"""
        formatted_data = {}
        
        for result in lab_results:
            test_code = result.test_code or "unknown"
            if test_code not in formatted_data:
                formatted_data[test_code] = []
            
            formatted_data[test_code].append({
                "id": result.id,
                "test_name": result.test_name,
                "value": result.value,
                "unit": result.unit,
                "ref_range": result.ref_range,
                "abnormal": result.abnormal,
                "created_at": result.created_at.isoformat()
            })
        
        return formatted_data

    async def _generate_lab_recommendations(
        self,
        results: List[Dict[str, Any]]
    ) -> List[str]:
        """Генерировать рекомендации на основе лабораторных данных"""
        recommendations = []
        
        # Анализируем результаты
        abnormal_results = [r for r in results if r["is_abnormal"]]
        
        if not abnormal_results:
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
        for test_code, type_results in abnormal_by_type.items():
            if test_code == "glucose":
                recommendations.append("Рекомендуется контроль уровня глюкозы и консультация эндокринолога")
            elif test_code == "cholesterol":
                recommendations.append("Рекомендуется диета с низким содержанием холестерина и консультация кардиолога")
            elif test_code == "hemoglobin":
                recommendations.append("Рекомендуется дополнительное обследование для выявления причины анемии")
            elif test_code in ["alt", "ast"]:
                recommendations.append("Рекомендуется консультация гастроэнтеролога для оценки функции печени")
            else:
                recommendations.append(f"Рекомендуется повторное исследование {test_code} через 2-4 недели")
        
        return recommendations


# Создаем экземпляр сервиса
emr_lab_integration = EMRLabIntegrationService()
