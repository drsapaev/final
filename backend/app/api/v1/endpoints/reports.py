"""
API endpoints для системы отчетов
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.api.deps import get_db, get_current_user, require_roles
from app.core.roles import Roles
from app.models.user import User
from app.services.reporting_service import get_reporting_service, ReportingService

logger = logging.getLogger(__name__)

router = APIRouter()


# ===================== PYDANTIC MODELS =====================

class ReportRequest(BaseModel):
    """Базовая модель запроса отчета"""
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    format: str = Field(default="json", pattern="^(json|csv|excel|pdf)$")
    filters: Optional[Dict[str, Any]] = None


class PatientReportRequest(ReportRequest):
    """Запрос отчета по пациентам"""
    department: Optional[str] = None


class AppointmentReportRequest(ReportRequest):
    """Запрос отчета по записям"""
    doctor_id: Optional[int] = None
    department: Optional[str] = None


class FinancialReportRequest(ReportRequest):
    """Запрос финансового отчета"""
    department: Optional[str] = None


class QueueReportRequest(ReportRequest):
    """Запрос отчета по очередям"""
    doctor_id: Optional[int] = None


class DoctorPerformanceReportRequest(ReportRequest):
    """Запрос отчета по производительности врачей"""
    doctor_id: Optional[int] = None


class ScheduleReportRequest(BaseModel):
    """Запрос планирования автоматического отчета"""
    report_type: str = Field(..., pattern="^(patient_report|appointments_report|financial_report|queue_report|doctor_performance_report)$")
    schedule: str = Field(..., pattern="^(daily|weekly|monthly)$")
    recipients: List[str] = Field(..., min_length=1)
    format: str = Field(default="excel", pattern="^(json|csv|excel|pdf)$")
    filters: Optional[Dict[str, Any]] = None


class ReportResponse(BaseModel):
    """Ответ с отчетом"""
    success: bool
    report_type: str
    generated_at: str
    format: str
    data: Optional[Dict[str, Any]] = None
    filename: Optional[str] = None
    filepath: Optional[str] = None
    size: Optional[int] = None
    error: Optional[str] = None


# ===================== ОСНОВНЫЕ ОТЧЕТЫ =====================

@router.post("/patient", response_model=ReportResponse)
async def generate_patient_report(
    request: PatientReportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN, Roles.REGISTRAR, Roles.MANAGER]))
):
    """Генерирует отчет по пациентам"""
    try:
        reporting_service = get_reporting_service(db)
        
        result = reporting_service.generate_patient_report(
            start_date=request.start_date,
            end_date=request.end_date,
            department=request.department,
            format=request.format
        )
        
        if "error" in result:
            return ReportResponse(
                success=False,
                report_type="patient_report",
                generated_at=datetime.now().isoformat(),
                format=request.format,
                error=result["error"]
            )
        
        return ReportResponse(
            success=True,
            report_type="patient_report",
            generated_at=result.get("generated_at", datetime.now().isoformat()),
            format=result.get("format", request.format),
            data=result.get("data"),
            filename=result.get("filename"),
            filepath=result.get("filepath"),
            size=result.get("size")
        )
        
    except Exception as e:
        logger.error(f"Ошибка генерации отчета по пациентам: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/appointments", response_model=ReportResponse)
async def generate_appointments_report(
    request: AppointmentReportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN, Roles.REGISTRAR, Roles.MANAGER]))
):
    """Генерирует отчет по записям"""
    try:
        reporting_service = get_reporting_service(db)
        
        result = reporting_service.generate_appointments_report(
            start_date=request.start_date,
            end_date=request.end_date,
            doctor_id=request.doctor_id,
            department=request.department,
            format=request.format
        )
        
        if "error" in result:
            return ReportResponse(
                success=False,
                report_type="appointments_report",
                generated_at=datetime.now().isoformat(),
                format=request.format,
                error=result["error"]
            )
        
        return ReportResponse(
            success=True,
            report_type="appointments_report",
            generated_at=result.get("generated_at", datetime.now().isoformat()),
            format=result.get("format", request.format),
            data=result.get("data"),
            filename=result.get("filename"),
            filepath=result.get("filepath"),
            size=result.get("size")
        )
        
    except Exception as e:
        logger.error(f"Ошибка генерации отчета по записям: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/financial", response_model=ReportResponse)
async def generate_financial_report(
    request: FinancialReportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN, Roles.MANAGER]))
):
    """Генерирует финансовый отчет"""
    try:
        reporting_service = get_reporting_service(db)
        
        result = reporting_service.generate_financial_report(
            start_date=request.start_date,
            end_date=request.end_date,
            department=request.department,
            format=request.format
        )
        
        if "error" in result:
            return ReportResponse(
                success=False,
                report_type="financial_report",
                generated_at=datetime.now().isoformat(),
                format=request.format,
                error=result["error"]
            )
        
        return ReportResponse(
            success=True,
            report_type="financial_report",
            generated_at=result.get("generated_at", datetime.now().isoformat()),
            format=result.get("format", request.format),
            data=result.get("data"),
            filename=result.get("filename"),
            filepath=result.get("filepath"),
            size=result.get("size")
        )
        
    except Exception as e:
        logger.error(f"Ошибка генерации финансового отчета: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/daily-summary")
async def get_daily_summary(
    target_date: Optional[date] = Query(None, description="Дата для сводки (по умолчанию сегодня)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN, Roles.REGISTRAR, Roles.MANAGER]))
):
    """Получает ежедневную сводку"""
    try:
        reporting_service = get_reporting_service(db)
        result = reporting_service.generate_daily_summary(target_date)
        
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        
        return result
        
    except Exception as e:
        logger.error(f"Ошибка получения ежедневной сводки: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/available-reports")
async def get_available_reports(
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN, Roles.REGISTRAR, Roles.MANAGER]))
):
    """Получает список доступных типов отчетов"""
    try:
        # Создаем временный экземпляр сервиса без БД для получения метаданных
        class MockDB:
            pass
        
        reporting_service = ReportingService(MockDB())
        return {
            "success": True,
            "reports": reporting_service.get_available_reports()
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения списка отчетов: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cleanup")
async def cleanup_old_reports(
    days: int = Query(30, ge=1, le=365, description="Количество дней для хранения отчетов"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN]))
):
    """Очищает старые файлы отчетов"""
    try:
        reporting_service = get_reporting_service(db)
        deleted_count = reporting_service.cleanup_old_reports(days)
        
        return {
            "success": True,
            "message": f"Удалено {deleted_count} старых файлов отчетов",
            "deleted_count": deleted_count
        }
        
    except Exception as e:
        logger.error(f"Ошибка очистки старых отчетов: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/files")
async def list_report_files(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_roles([Roles.ADMIN, Roles.REGISTRAR, Roles.MANAGER]))
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
                    files.append({
                        "filename": filename,
                        "size": stat.st_size,
                        "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
                    })
        
        # Сортируем по дате изменения (новые первые)
        files.sort(key=lambda x: x["modified_at"], reverse=True)

        return {
            "success": True,
            "files": files,
            "total_count": len(files)
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения списка файлов отчетов: {e}")
        raise HTTPException(status_code=500, detail=str(e))