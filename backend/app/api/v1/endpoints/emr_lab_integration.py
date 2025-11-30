"""
API endpoints для интеграции EMR с лабораторными данными
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.models.user import User
from app.services.emr_lab_integration import emr_lab_integration

router = APIRouter()


@router.get("/patients/{patient_id}/lab-results")
async def get_patient_lab_results(
    patient_id: int,
    date_from: Optional[str] = Query(None, description="Дата начала (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Дата окончания (YYYY-MM-DD)"),
    test_types: Optional[str] = Query(None, description="Типы тестов через запятую"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> Any:
    """Получить лабораторные результаты пациента"""
    try:
        # Парсим даты
        parsed_date_from = None
        parsed_date_to = None

        if date_from:
            parsed_date_from = datetime.fromisoformat(date_from)
        if date_to:
            parsed_date_to = datetime.fromisoformat(date_to)

        # Парсим типы тестов
        parsed_test_types = None
        if test_types:
            parsed_test_types = [t.strip() for t in test_types.split(",")]

        results = await emr_lab_integration.get_patient_lab_results(
            db=db,
            patient_id=patient_id,
            date_from=parsed_date_from,
            date_to=parsed_date_to,
            test_types=parsed_test_types,
        )

        return {
            "patient_id": patient_id,
            "results": results,
            "total_count": len(results),
            "abnormal_count": len([r for r in results if r["is_abnormal"]]),
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка получения лабораторных результатов: {str(e)}",
        )


@router.post("/emr/{emr_id}/integrate-lab-results")
async def integrate_lab_results_with_emr(
    emr_id: int,
    lab_result_ids: List[int],
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> Any:
    """Интегрировать лабораторные результаты с EMR"""
    try:
        result = await emr_lab_integration.integrate_lab_results_with_emr(
            db=db, emr_id=emr_id, lab_result_ids=lab_result_ids
        )

        return {
            "message": "Лабораторные результаты успешно интегрированы с EMR",
            "result": result,
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка интеграции лабораторных данных: {str(e)}"
        )


@router.get("/patients/{patient_id}/abnormal-lab-results")
async def get_abnormal_lab_results(
    patient_id: int,
    days: int = Query(30, ge=1, le=365, description="Количество дней для поиска"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> Any:
    """Получить аномальные лабораторные результаты пациента"""
    try:
        date_from = datetime.utcnow() - timedelta(days=days)

        abnormal_results = await emr_lab_integration.get_abnormal_lab_results(
            db=db, patient_id=patient_id, date_from=date_from
        )

        # Группируем по серьезности
        severity_groups = {}
        for result in abnormal_results:
            severity = result["severity"]
            if severity not in severity_groups:
                severity_groups[severity] = []
            severity_groups[severity].append(result)

        return {
            "patient_id": patient_id,
            "period_days": days,
            "abnormal_results": abnormal_results,
            "total_abnormal": len(abnormal_results),
            "severity_groups": severity_groups,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения аномальных результатов: {str(e)}"
        )


@router.get("/emr/{emr_id}/lab-summary")
async def get_lab_summary_for_emr(
    emr_id: int,
    patient_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> Any:
    """Получить сводку лабораторных данных для EMR"""
    try:
        summary = await emr_lab_integration.generate_lab_summary_for_emr(
            db=db, patient_id=patient_id, emr_id=emr_id
        )

        return {"emr_id": emr_id, "patient_id": patient_id, "summary": summary}

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка генерации сводки лабораторных данных: {str(e)}",
        )


@router.post("/lab-results/{result_id}/notify-doctor")
async def notify_doctor_about_lab_result(
    result_id: int,
    patient_id: int,
    doctor_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor", "Lab")),
) -> Any:
    """Уведомить врача о готовности лабораторного результата"""
    try:
        notification = await emr_lab_integration.notify_doctor_about_lab_results(
            db=db, patient_id=patient_id, doctor_id=doctor_id, result_id=result_id
        )

        return {"message": "Уведомление врача отправлено", "notification": notification}

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка уведомления врача: {str(e)}"
        )


@router.get("/lab-results/statistics")
async def get_lab_results_statistics(
    date_from: Optional[str] = Query(None, description="Дата начала (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Дата окончания (YYYY-MM-DD)"),
    test_type: Optional[str] = Query(None, description="Тип теста"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> Any:
    """Получить статистику лабораторных результатов"""
    try:
        # Парсим даты
        parsed_date_from = None
        parsed_date_to = None

        if date_from:
            parsed_date_from = datetime.fromisoformat(date_from)
        if date_to:
            parsed_date_to = datetime.fromisoformat(date_to)

        # Здесь будет реальная статистика
        # Пока возвращаем заглушку
        statistics = {
            "total_tests": 1250,
            "abnormal_tests": 180,
            "abnormal_percentage": 14.4,
            "most_common_abnormal": [
                {"test_type": "glucose", "count": 45, "percentage": 25.0},
                {"test_type": "cholesterol", "count": 38, "percentage": 21.1},
                {"test_type": "hemoglobin", "count": 32, "percentage": 17.8},
            ],
            "average_processing_time": "2.5 hours",
            "period": {
                "from": date_from or "2024-01-01",
                "to": date_to or "2024-12-31",
            },
        }

        return statistics

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения статистики: {str(e)}"
        )


@router.get("/lab-results/trends")
async def get_lab_results_trends(
    patient_id: int,
    test_type: str = Query(..., description="Тип теста"),
    period_days: int = Query(90, ge=7, le=365, description="Период в днях"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> Any:
    """Получить тренды лабораторных результатов пациента"""
    try:
        date_from = datetime.utcnow() - timedelta(days=period_days)

        # Получаем результаты за период
        results = await emr_lab_integration.get_patient_lab_results(
            db=db, patient_id=patient_id, date_from=date_from, test_types=[test_type]
        )

        # Сортируем по дате
        results.sort(key=lambda x: x["completed_at"])

        # Формируем тренд
        trend_data = []
        for result in results:
            trend_data.append(
                {
                    "date": result["completed_at"].strftime("%Y-%m-%d"),
                    "value": result["value"],
                    "unit": result["unit"],
                    "is_abnormal": result["is_abnormal"],
                    "normal_range": result["normal_range"],
                }
            )

        # Рассчитываем статистику тренда
        values = [r["value"] for r in results if r["value"] is not None]
        if values:
            trend_stats = {
                "min_value": min(values),
                "max_value": max(values),
                "avg_value": sum(values) / len(values),
                "trend_direction": (
                    "increasing"
                    if len(values) > 1 and values[-1] > values[0]
                    else "decreasing"
                ),
                "abnormal_percentage": (
                    len([r for r in results if r["is_abnormal"]]) / len(results)
                )
                * 100,
            }
        else:
            trend_stats = {}

        return {
            "patient_id": patient_id,
            "test_type": test_type,
            "period_days": period_days,
            "trend_data": trend_data,
            "trend_stats": trend_stats,
            "total_measurements": len(trend_data),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения трендов: {str(e)}"
        )
