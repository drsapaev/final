"""
API endpoints для интеграции EMR с лабораторными данными
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.models.appointment import Appointment
from app.models.clinic import Doctor
from app.models.emr import EMR
from app.models.lab import LabOrder, LabResult
from app.models.user import User
from app.models.visit import Visit
from app.services.emr_lab_integration import emr_lab_integration

router = APIRouter()


def _doctor_allowed_doctor_ids(db: Session, current_user: User) -> set[int]:
    doctor = (
        db.query(Doctor)
        .filter(Doctor.user_id == current_user.id, Doctor.active.is_(True))
        .first()
    )
    if not doctor:
        raise HTTPException(status_code=403, detail="Access denied")

    allowed_doctor_ids = {doctor.id}
    assigned_doctor = db.query(Doctor).filter(Doctor.id == current_user.id).first()
    # Some legacy visit writers stored User.id in doctor_id. Allow that only
    # when the value does not target another real Doctor row.
    if not assigned_doctor:
        allowed_doctor_ids.add(current_user.id)
    return allowed_doctor_ids


def _doctor_allowed_patient_ids(db: Session, current_user: User) -> set[int]:
    allowed_doctor_ids = _doctor_allowed_doctor_ids(db, current_user)
    rows = (
        db.query(Visit.patient_id)
        .filter(
            Visit.doctor_id.in_(allowed_doctor_ids),
            Visit.patient_id.isnot(None),
        )
        .all()
    )
    return {row[0] for row in rows if row[0] is not None}


def _ensure_doctor_can_read_patient_lab_data(
    db: Session,
    patient_id: int,
    current_user: User,
) -> None:
    if current_user.role != "Doctor":
        return
    if current_user.is_superuser:
        return
    if patient_id not in _doctor_allowed_patient_ids(db, current_user):
        raise HTTPException(status_code=403, detail="Access denied")


def _ensure_doctor_can_integrate_lab_results(
    db: Session,
    emr_id: int,
    lab_result_ids: list[int],
    current_user: User,
) -> None:
    if current_user.role != "Doctor":
        return
    if current_user.is_superuser:
        return

    emr_record = db.query(EMR).filter(EMR.id == emr_id).first()
    if not emr_record:
        raise HTTPException(status_code=404, detail="EMR not found")

    allowed_doctor_ids = _doctor_allowed_doctor_ids(db, current_user)
    appointment = (
        db.query(Appointment)
        .filter(
            Appointment.id == emr_record.appointment_id,
            Appointment.doctor_id.in_(allowed_doctor_ids),
        )
        .first()
    )
    if not appointment:
        raise HTTPException(status_code=403, detail="Access denied")

    result_rows = (
        db.query(LabResult.id, LabOrder.patient_id)
        .join(LabOrder, LabResult.order_id == LabOrder.id)
        .filter(LabResult.id.in_(lab_result_ids))
        .all()
    )
    if any(
        patient_id != appointment.patient_id
        for _result_id, patient_id in result_rows
    ):
        raise HTTPException(status_code=403, detail="Access denied")


def _ensure_lab_result_notification_scope(
    db: Session,
    *,
    result_id: int,
    patient_id: int,
    doctor_id: int,
    current_user: User,
) -> None:
    result_owner = (
        db.query(LabOrder.patient_id)
        .join(LabResult, LabResult.order_id == LabOrder.id)
        .filter(LabResult.id == result_id)
        .scalar()
    )
    if result_owner is None:
        raise HTTPException(status_code=404, detail="Lab result not found")
    if int(result_owner) != int(patient_id):
        raise HTTPException(status_code=403, detail="Access denied")

    if current_user.role != "Doctor":
        return
    if current_user.is_superuser:
        return

    allowed_doctor_ids = _doctor_allowed_doctor_ids(db, current_user)
    if int(doctor_id) not in allowed_doctor_ids:
        raise HTTPException(status_code=403, detail="Access denied")
    if int(patient_id) not in _doctor_allowed_patient_ids(db, current_user):
        raise HTTPException(status_code=403, detail="Access denied")


@router.get("/patients/{patient_id}/lab-results", response_model=Any)
async def get_patient_lab_results(
    patient_id: int,
    date_from: str | None = Query(None, description="Дата начала (YYYY-MM-DD)"),
    date_to: str | None = Query(None, description="Дата окончания (YYYY-MM-DD)"),
    test_types: str | None = Query(None, description="Типы тестов через запятую"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> Any:
    """Получить лабораторные результаты пациента"""
    _ensure_doctor_can_read_patient_lab_data(db, patient_id, current_user)
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

    except ValueError:
        raise HTTPException(status_code=400, detail="Internal server error")
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        )


@router.post("/emr/{emr_id}/integrate-lab-results", response_model=Any)
async def integrate_lab_results_with_emr(
    emr_id: int,
    lab_result_ids: list[int],
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> Any:
    """Интегрировать лабораторные результаты с EMR"""
    _ensure_doctor_can_integrate_lab_results(
        db, emr_id, lab_result_ids, current_user
    )
    try:
        result = await emr_lab_integration.integrate_lab_results_with_emr(
            db=db, emr_id=emr_id, lab_result_ids=lab_result_ids
        )

        return {
            "message": "Лабораторные результаты успешно интегрированы с EMR",
            "result": result,
        }

    except ValueError:
        raise HTTPException(status_code=404, detail="Internal server error")
    except Exception:
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )


@router.get("/patients/{patient_id}/abnormal-lab-results", response_model=Any)
async def get_abnormal_lab_results(
    patient_id: int,
    days: int = Query(30, ge=1, le=365, description="Количество дней для поиска"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> Any:
    """Получить аномальные лабораторные результаты пациента"""
    _ensure_doctor_can_read_patient_lab_data(db, patient_id, current_user)
    try:
        date_from = datetime.now(UTC) - timedelta(days=days)

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

    except Exception:
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )


@router.get("/emr/{emr_id}/lab-summary", response_model=Any)
async def get_lab_summary_for_emr(
    emr_id: int,
    patient_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> Any:
    """Получить сводку лабораторных данных для EMR"""
    _ensure_doctor_can_read_patient_lab_data(db, patient_id, current_user)
    try:
        summary = await emr_lab_integration.generate_lab_summary_for_emr(
            db=db, patient_id=patient_id, emr_id=emr_id
        )

        return {"emr_id": emr_id, "patient_id": patient_id, "summary": summary}

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        )


@router.post("/lab-results/{result_id}/notify-doctor", response_model=Any)
async def notify_doctor_about_lab_result(
    result_id: int,
    patient_id: int,
    doctor_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor", "Lab")),
) -> Any:
    """Уведомить врача о готовности лабораторного результата"""
    _ensure_lab_result_notification_scope(
        db,
        result_id=result_id,
        patient_id=patient_id,
        doctor_id=doctor_id,
        current_user=current_user,
    )
    try:
        notification = await emr_lab_integration.notify_doctor_about_lab_results(
            db=db, patient_id=patient_id, doctor_id=doctor_id, result_id=result_id
        )

        return {"message": "Уведомление врача отправлено", "notification": notification}

    except ValueError:
        raise HTTPException(status_code=404, detail="Internal server error")
    except Exception:
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )


@router.get("/lab-results/statistics", deprecated=True, response_model=Any)
async def get_lab_results_statistics(
    date_from: str | None = Query(None, description="Дата начала (YYYY-MM-DD)"),
    date_to: str | None = Query(None, description="Дата окончания (YYYY-MM-DD)"),
    test_type: str | None = Query(None, description="Тип теста"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> Any:
    """
    Deprecated: returns hardcoded stub data. Use /lab/report-instances for real data.
    P2 fix: this endpoint previously returned fake statistics (total_tests: 1250, etc.)
    which was misleading. Now returns a 410 Gone deprecation notice.
    """
    raise HTTPException(
        status_code=410,
        detail="This endpoint is deprecated. Use GET /lab/report-instances for real lab data.",
    )

@router.get("/lab-results/trends", response_model=Any)
async def get_lab_results_trends(
    patient_id: int,
    test_type: str = Query(..., description="Тип теста"),
    period_days: int = Query(90, ge=7, le=365, description="Период в днях"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> Any:
    """Получить тренды лабораторных результатов пациента"""
    _ensure_doctor_can_read_patient_lab_data(db, patient_id, current_user)
    try:
        date_from = datetime.now(UTC) - timedelta(days=period_days)

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

    except Exception:
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )
