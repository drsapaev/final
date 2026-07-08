"""
API endpoints для системы отчетов
"""

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.core.roles import Roles
from app.models.user import User
from app.services.reporting_service import ReportingService, get_reporting_service

logger = logging.getLogger(__name__)

router = APIRouter()


def raise_report_internal_error(
    action: str, public_detail: str, exc: Exception
) -> NoReturn:
    logger.warning(
        "Report endpoint failed action=%s error_type=%s",
        action,
        type(exc).__name__,
    )
    raise HTTPException(status_code=500, detail=public_detail)


def log_report_service_error(report_type: str) -> None:
    logger.warning("Report service returned error report_type=%s", report_type)


# ===================== PYDANTIC MODELS =====================


class ReportRequest(BaseModel):
    """Базовая модель запроса отчета"""

    start_date: date | None = None
    end_date: date | None = None
    format: str = Field(default="json", pattern="^(json|csv|excel|pdf)$")
    filters: dict[str, Any] | None = None


class PatientReportRequest(ReportRequest):
    """Запрос отчета по пациентам"""

    department: str | None = None


class AppointmentReportRequest(ReportRequest):
    """Запрос отчета по записям"""

    doctor_id: int | None = None
    department: str | None = None


class FinancialReportRequest(ReportRequest):
    """Запрос финансового отчета"""

    department: str | None = None


class QueueReportRequest(ReportRequest):
    """Запрос отчета по очередям"""

    doctor_id: int | None = None


class DoctorPerformanceReportRequest(ReportRequest):
    """Запрос отчета по производительности врачей"""

    doctor_id: int | None = None


class ScheduleReportRequest(BaseModel):
    """Запрос планирования автоматического отчета"""

    report_type: str = Field(
        ...,
        pattern="^(patient_report|appointments_report|financial_report|queue_report|doctor_performance_report)$",
    )
    schedule: str = Field(..., pattern="^(daily|weekly|monthly)$")
    recipients: list[str] = Field(..., min_length=1)
    format: str = Field(default="excel", pattern="^(json|csv|excel|pdf)$")
    filters: dict[str, Any] | None = None


class ReportResponse(BaseModel):
    """Ответ с отчетом"""

    success: bool
    report_type: str
    generated_at: str
    format: str
    data: dict[str, Any] | None = None
    filename: str | None = None
    filepath: str | None = None
    size: int | None = None
    error: str | None = None


# ===================== ОСНОВНЫЕ ОТЧЕТЫ =====================


@router.post("/patient", response_model=ReportResponse)
async def generate_patient_report(
    request: PatientReportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN, Roles.REGISTRAR, Roles.MANAGER])),
):
    """Генерирует отчет по пациентам"""
    try:
        reporting_service = get_reporting_service(db)

        result = reporting_service.generate_patient_report(
            start_date=request.start_date,
            end_date=request.end_date,
            department=request.department,
            format=request.format,
        )

        if "error" in result:
            log_report_service_error("patient_report")
            return ReportResponse(
                success=False,
                report_type="patient_report",
                generated_at=datetime.now().isoformat(),
                format=request.format,
                error="Ошибка генерации отчета по пациентам",
            )

        return ReportResponse(
            success=True,
            report_type="patient_report",
            generated_at=result.get("generated_at", datetime.now().isoformat()),
            format=result.get("format", request.format),
            data=result.get("data"),
            filename=result.get("filename"),
            filepath=result.get("filepath"),
            size=result.get("size"),
        )

    except Exception as e:
        raise_report_internal_error(
            "patient-report", "Ошибка генерации отчета по пациентам", e
        )


@router.post("/appointments", response_model=ReportResponse)
async def generate_appointments_report(
    request: AppointmentReportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN, Roles.REGISTRAR, Roles.MANAGER])),
):
    """Генерирует отчет по записям"""
    try:
        reporting_service = get_reporting_service(db)

        result = reporting_service.generate_appointments_report(
            start_date=request.start_date,
            end_date=request.end_date,
            doctor_id=request.doctor_id,
            department=request.department,
            format=request.format,
        )

        if "error" in result:
            log_report_service_error("appointments_report")
            return ReportResponse(
                success=False,
                report_type="appointments_report",
                generated_at=datetime.now().isoformat(),
                format=request.format,
                error="Ошибка генерации отчета по записям",
            )

        return ReportResponse(
            success=True,
            report_type="appointments_report",
            generated_at=result.get("generated_at", datetime.now().isoformat()),
            format=result.get("format", request.format),
            data=result.get("data"),
            filename=result.get("filename"),
            filepath=result.get("filepath"),
            size=result.get("size"),
        )

    except Exception as e:
        raise_report_internal_error(
            "appointments-report", "Ошибка генерации отчета по записям", e
        )


@router.post("/financial", response_model=ReportResponse)
async def generate_financial_report(
    request: FinancialReportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN, Roles.MANAGER])),
):
    """Генерирует финансовый отчет"""
    try:
        reporting_service = get_reporting_service(db)

        result = reporting_service.generate_financial_report(
            start_date=request.start_date,
            end_date=request.end_date,
            department=request.department,
            format=request.format,
        )

        if "error" in result:
            log_report_service_error("financial_report")
            return ReportResponse(
                success=False,
                report_type="financial_report",
                generated_at=datetime.now().isoformat(),
                format=request.format,
                error="Ошибка генерации финансового отчета",
            )

        return ReportResponse(
            success=True,
            report_type="financial_report",
            generated_at=result.get("generated_at", datetime.now().isoformat()),
            format=result.get("format", request.format),
            data=result.get("data"),
            filename=result.get("filename"),
            filepath=result.get("filepath"),
            size=result.get("size"),
        )

    except Exception as e:
        raise_report_internal_error(
            "financial-report", "Ошибка генерации финансового отчета", e
        )


@router.post("/queue", response_model=ReportResponse)
async def generate_queue_report(
    request: QueueReportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN, Roles.REGISTRAR, Roles.MANAGER])),
):
    """Generate a queue report."""
    try:
        reporting_service = get_reporting_service(db)

        result = reporting_service.generate_queue_report(
            start_date=request.start_date,
            end_date=request.end_date,
            doctor_id=request.doctor_id,
            format=request.format,
        )

        if "error" in result:
            log_report_service_error("queue_report")
            return ReportResponse(
                success=False,
                report_type="queue_report",
                generated_at=datetime.now().isoformat(),
                format=request.format,
                error="Queue report generation failed",
            )

        return ReportResponse(
            success=True,
            report_type="queue_report",
            generated_at=result.get("generated_at", datetime.now().isoformat()),
            format=result.get("format", request.format),
            data=result.get("data"),
            filename=result.get("filename"),
            filepath=result.get("filepath"),
            size=result.get("size"),
        )

    except Exception as e:
        raise_report_internal_error(
            "queue-report", "Queue report generation failed", e
        )


@router.post("/doctor-performance", response_model=ReportResponse)
async def generate_doctor_performance_report(
    request: DoctorPerformanceReportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN, Roles.MANAGER])),
):
    """Generate a doctor performance report."""
    try:
        reporting_service = get_reporting_service(db)

        result = reporting_service.generate_doctor_performance_report(
            start_date=request.start_date,
            end_date=request.end_date,
            doctor_id=request.doctor_id,
            format=request.format,
        )

        if "error" in result:
            log_report_service_error("doctor_performance_report")
            return ReportResponse(
                success=False,
                report_type="doctor_performance_report",
                generated_at=datetime.now().isoformat(),
                format=request.format,
                error="Doctor performance report generation failed",
            )

        return ReportResponse(
            success=True,
            report_type="doctor_performance_report",
            generated_at=result.get("generated_at", datetime.now().isoformat()),
            format=result.get("format", request.format),
            data=result.get("data"),
            filename=result.get("filename"),
            filepath=result.get("filepath"),
            size=result.get("size"),
        )

    except Exception as e:
        raise_report_internal_error(
            "doctor-performance-report",
            "Doctor performance report generation failed",
            e,
        )


@router.get("/daily-summary", response_model=dict[str, Any])
async def get_daily_summary(
    target_date: date | None = Query(
        None, description="Дата для сводки (по умолчанию сегодня)"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN, Roles.REGISTRAR, Roles.MANAGER])),
):
    """Получает ежедневную сводку"""
    try:
        reporting_service = get_reporting_service(db)
        result = reporting_service.generate_daily_summary(target_date)

        if "error" in result:
            log_report_service_error("daily_summary")
            raise HTTPException(
                status_code=500, detail="Ошибка получения ежедневной сводки"
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise_report_internal_error(
            "daily-summary", "Ошибка получения ежедневной сводки", e
        )


@router.get("/available-reports", response_model=dict[str, Any])
async def get_available_reports(    limit: int = Query(default=100, ge=1, le=500, description="Количество записей"),
    offset: int = Query(default=0, ge=0, description="Смещение"),
current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN, Roles.REGISTRAR, Roles.MANAGER])),
):
    """Получает список доступных типов отчетов"""
    try:
        # Создаем временный экземпляр сервиса без БД для получения метаданных
        class MockDB:
            pass

        reporting_service = ReportingService(MockDB())
        return {"success": True, "reports": reporting_service.get_available_reports()}

    except Exception as e:
        raise_report_internal_error(
            "available-reports", "Ошибка получения списка отчетов", e
        )


@router.post("/cleanup", response_model=dict[str, Any])
async def cleanup_old_reports(
    days: int = Query(
        30, ge=1, le=365, description="Количество дней для хранения отчетов"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN])),
):
    """Очищает старые файлы отчетов"""
    try:
        reporting_service = get_reporting_service(db)
        deleted_count = reporting_service.cleanup_old_reports(days)

        return {
            "success": True,
            "message": f"Удалено {deleted_count} старых файлов отчетов",
            "deleted_count": deleted_count,
        }

    except Exception as e:
        raise_report_internal_error("cleanup", "Ошибка очистки старых отчетов", e)


@router.get("/files", response_model=dict[str, Any])
async def list_report_files(    limit: int = Query(default=100, ge=1, le=500, description="Количество записей"),
    offset: int = Query(default=0, ge=0, description="Смещение"),
db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN, Roles.REGISTRAR, Roles.MANAGER])),
):
    """Получает список файлов отчетов"""
    try:
        import os

        reporting_service = get_reporting_service(db)
        files = []

        if os.path.exists(reporting_service.reports_dir):
            for filename in os.listdir(reporting_service.reports_dir):
                filepath = os.path.join(reporting_service.reports_dir, filename)
                if os.path.isfile(filepath):
                    stat = os.stat(filepath)
                    files.append(
                        {
                            "filename": filename,
                            "size": stat.st_size,
                            "created_at": datetime.fromtimestamp(
                                stat.st_ctime
                            ).isoformat(),
                            "modified_at": datetime.fromtimestamp(
                                stat.st_mtime
                            ).isoformat(),
                        }
                    )

        # Сортируем по дате изменения (новые первые)
        files.sort(key=lambda x: x["modified_at"], reverse=True)

        return {"success": True, "files": files, "total_count": len(files)}

    except Exception as e:
        raise_report_internal_error(
            "report-files", "Ошибка получения списка файлов отчетов", e
        )


@router.get("/download/{filename}", response_model=dict[str, Any])
async def download_report_file(
    filename: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN, Roles.REGISTRAR, Roles.MANAGER])),
):
    """Download a generated report file."""
    try:
        reporting_service = get_reporting_service(db)
        reports_dir = Path(reporting_service.reports_dir).resolve()
        if not reports_dir.is_dir():
            raise HTTPException(status_code=404, detail="Report file not found")

        report_path = next(
            (
                candidate.resolve()
                for candidate in reports_dir.iterdir()
                if candidate.is_file() and candidate.name == filename
            ),
            None,
        )

        if report_path is None or report_path.parent != reports_dir:
            raise HTTPException(status_code=404, detail="Report file not found")

        return FileResponse(
            path=str(report_path),
            filename=report_path.name,
            media_type="application/octet-stream",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise_report_internal_error(
            "download-report", "Report file download failed", e
        )
