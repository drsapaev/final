"""
API endpoints для экспорта аналитических отчетов
"""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user
from app.services.analytics_export_service import get_analytics_export_service, AnalyticsExportService
from app.services.advanced_analytics import get_advanced_analytics_service, AdvancedAnalyticsService

router = APIRouter()


@router.get("/formats")
async def get_export_formats(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Получить список поддерживаемых форматов экспорта"""
    try:
        export_service = await get_analytics_export_service()
        formats = await export_service.get_export_formats()
        
        return {
            "formats": formats,
            "count": len(formats)
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка получения форматов экспорта: {str(e)}"
        )


@router.get("/kpi/export/{format}")
async def export_kpi_report(
    format: str,
    start_date: str = Query(..., description="Начальная дата (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Конечная дата (YYYY-MM-DD)"),
    department: Optional[str] = Query(None, description="Отделение"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Экспорт отчета KPI в указанном формате"""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты")

    if start > end:
        raise HTTPException(
            status_code=400, detail="Начальная дата должна быть раньше конечной"
        )

    # Получаем данные KPI
    analytics_service = get_advanced_analytics_service()
    kpi_data = analytics_service.get_kpi_metrics(db, start, end, department)
    
    # Экспортируем в указанном формате
    export_service = await get_analytics_export_service()
    
    if format == "json":
        result = await export_service.export_to_json(kpi_data)
    elif format == "csv":
        result = await export_service.export_to_csv(kpi_data)
    elif format == "pdf":
        result = await export_service.export_to_pdf(kpi_data)
    elif format == "excel":
        result = await export_service.export_to_excel(kpi_data)
    elif format == "zip":
        result = await export_service.export_to_zip(kpi_data)
    else:
        raise HTTPException(status_code=400, detail="Неподдерживаемый формат экспорта")
    
    return Response(
        content=result["content"],
        media_type=result["mime_type"],
        headers={
            "Content-Disposition": f"attachment; filename={result['filename']}"
        }
    )


@router.get("/comprehensive/export/{format}")
async def export_comprehensive_report(
    format: str,
    start_date: str = Query(..., description="Начальная дата (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Конечная дата (YYYY-MM-DD)"),
    department: Optional[str] = Query(None, description="Отделение"),
    include_predictive: bool = Query(True, description="Включить предиктивную аналитику"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Экспорт комплексного отчета в указанном формате"""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты")

    if start > end:
        raise HTTPException(
            status_code=400, detail="Начальная дата должна быть раньше конечной"
        )

    # Получаем комплексные данные
    analytics_service = get_advanced_analytics_service()
    
    report_data = {
        "report_period": {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "department": department or "all",
            "generated_at": datetime.utcnow().isoformat()
        },
        "kpi_metrics": analytics_service.get_kpi_metrics(db, start, end, department),
        "doctor_performance": analytics_service.get_doctor_performance(db, start, end, department),
        "patient_analytics": analytics_service.get_patient_analytics(db, start, end),
        "revenue_analytics": analytics_service.get_revenue_analytics(db, start, end, department)
    }
    
    if include_predictive:
        report_data["predictive_analytics"] = analytics_service.get_predictive_analytics(db, 30)
    
    # Экспортируем в указанном формате
    export_service = await get_analytics_export_service()
    
    if format == "json":
        result = await export_service.export_to_json(report_data)
    elif format == "csv":
        result = await export_service.export_to_csv(report_data)
    elif format == "pdf":
        result = await export_service.export_to_pdf(report_data)
    elif format == "excel":
        result = await export_service.export_to_excel(report_data)
    elif format == "zip":
        result = await export_service.export_to_zip(report_data)
    else:
        raise HTTPException(status_code=400, detail="Неподдерживаемый формат экспорта")
    
    return Response(
        content=result["content"],
        media_type=result["mime_type"],
        headers={
            "Content-Disposition": f"attachment; filename={result['filename']}"
        }
    )


@router.get("/doctors/performance/export/{format}")
async def export_doctor_performance_report(
    format: str,
    start_date: str = Query(..., description="Начальная дата (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Конечная дата (YYYY-MM-DD)"),
    department: Optional[str] = Query(None, description="Отделение"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Экспорт отчета по эффективности врачей в указанном формате"""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты")

    if start > end:
        raise HTTPException(
            status_code=400, detail="Начальная дата должна быть раньше конечной"
        )

    # Получаем данные по врачам
    analytics_service = get_advanced_analytics_service()
    doctor_data = analytics_service.get_doctor_performance(db, start, end, department)
    
    # Экспортируем в указанном формате
    export_service = await get_analytics_export_service()
    
    if format == "json":
        result = await export_service.export_to_json(doctor_data)
    elif format == "csv":
        result = await export_service.export_to_csv(doctor_data)
    elif format == "pdf":
        result = await export_service.export_to_pdf(doctor_data)
    elif format == "excel":
        result = await export_service.export_to_excel(doctor_data)
    elif format == "zip":
        result = await export_service.export_to_zip(doctor_data)
    else:
        raise HTTPException(status_code=400, detail="Неподдерживаемый формат экспорта")
    
    return Response(
        content=result["content"],
        media_type=result["mime_type"],
        headers={
            "Content-Disposition": f"attachment; filename={result['filename']}"
        }
    )


@router.get("/revenue/export/{format}")
async def export_revenue_report(
    format: str,
    start_date: str = Query(..., description="Начальная дата (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Конечная дата (YYYY-MM-DD)"),
    department: Optional[str] = Query(None, description="Отделение"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Экспорт отчета по доходам в указанном формате"""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты")

    if start > end:
        raise HTTPException(
            status_code=400, detail="Начальная дата должна быть раньше конечной"
        )

    # Получаем данные по доходам
    analytics_service = get_advanced_analytics_service()
    revenue_data = analytics_service.get_revenue_analytics(db, start, end, department)
    
    # Экспортируем в указанном формате
    export_service = await get_analytics_export_service()
    
    if format == "json":
        result = await export_service.export_to_json(revenue_data)
    elif format == "csv":
        result = await export_service.export_to_csv(revenue_data)
    elif format == "pdf":
        result = await export_service.export_to_pdf(revenue_data)
    elif format == "excel":
        result = await export_service.export_to_excel(revenue_data)
    elif format == "zip":
        result = await export_service.export_to_zip(revenue_data)
    else:
        raise HTTPException(status_code=400, detail="Неподдерживаемый формат экспорта")
    
    return Response(
        content=result["content"],
        media_type=result["mime_type"],
        headers={
            "Content-Disposition": f"attachment; filename={result['filename']}"
        }
    )


@router.get("/health")
async def export_health_check():
    """Проверка здоровья сервиса экспорта"""
    return {
        "status": "ok",
        "export_service": "active",
        "supported_formats": ["json", "csv", "pdf", "excel", "zip"],
        "features": [
            "kpi_export",
            "comprehensive_export",
            "doctor_performance_export",
            "revenue_export"
        ]
    }
