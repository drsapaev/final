from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy import and_

from app.api.deps import get_db, require_roles
from app.services.analytics import analytics_service

router = APIRouter()

@router.get("/visits")
async def get_visit_analytics(
    start_date: str = Query(..., description="Начальная дата (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Конечная дата (YYYY-MM-DD)"),
    department: Optional[str] = Query(None, description="Отделение"),
    current_user = Depends(require_roles(["admin", "doctor", "nurse"])),
    db: Session = Depends(get_db)
):
    """Получение аналитики визитов"""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты")
    
    if start > end:
        raise HTTPException(status_code=400, detail="Начальная дата должна быть раньше конечной")
    
    return analytics_service.get_visit_statistics(db, start, end, department)

@router.get("/patients")
async def get_patient_analytics(
    start_date: str = Query(..., description="Начальная дата (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Конечная дата (YYYY-MM-DD)"),
    current_user = Depends(require_roles(["admin", "doctor", "nurse"])),
    db: Session = Depends(get_db)
):
    """Получение аналитики пациентов"""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты")
    
    if start > end:
        raise HTTPException(status_code=400, detail="Начальная дата должна быть раньше конечной")
    
    return analytics_service.get_patient_statistics(db, start, end)

@router.get("/revenue")
async def get_revenue_analytics(
    start_date: str = Query(..., description="Начальная дата (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Конечная дата (YYYY-MM-DD)"),
    department: Optional[str] = Query(None, description="Отделение"),
    current_user = Depends(require_roles(["admin", "doctor"])),
    db: Session = Depends(get_db)
):
    """Получение аналитики доходов"""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты")
    
    if start > end:
        raise HTTPException(status_code=400, detail="Начальная дата должна быть раньше конечной")
    
    return analytics_service.get_revenue_statistics(db, start, end, department)

@router.get("/services")
async def get_service_analytics(
    start_date: str = Query(..., description="Начальная дата (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Конечная дата (YYYY-MM-DD)"),
    current_user = Depends(require_roles(["admin", "doctor", "nurse"])),
    db: Session = Depends(get_db)
):
    """Получение аналитики услуг"""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты")
    
    if start > end:
        raise HTTPException(status_code=400, detail="Начальная дата должна быть раньше конечной")
    
    return analytics_service.get_service_statistics(db, start, end)

@router.get("/queues")
async def get_queue_analytics(
    start_date: str = Query(..., description="Начальная дата (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Конечная дата (YYYY-MM-DD)"),
    department: Optional[str] = Query(None, description="Отделение"),
    current_user = Depends(require_roles(["admin", "doctor", "nurse"])),
    db: Session = Depends(get_db)
):
    """Получение аналитики очередей"""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты")
    
    if start > end:
        raise HTTPException(status_code=400, detail="Начальная дата должна быть раньше конечной")
    
    return analytics_service.get_queue_statistics(db, start, end, department)

@router.get("/comprehensive")
async def get_comprehensive_analytics(
    start_date: str = Query(..., description="Начальная дата (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Конечная дата (YYYY-MM-DD)"),
    department: Optional[str] = Query(None, description="Отделение"),
    current_user = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db)
):
    """Получение комплексного аналитического отчёта"""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты")
    
    if start > end:
        raise HTTPException(status_code=400, detail="Начальная дата должна быть раньше конечной")
    
    return analytics_service.get_comprehensive_report(db, start, end, department)

@router.get("/trends")
async def get_trends_analytics(
    days: int = Query(30, ge=1, le=365, description="Количество дней для анализа"),
    current_user = Depends(require_roles(["admin", "doctor", "nurse"])),
    db: Session = Depends(get_db)
):
    """Получение трендов за последние N дней"""
    return analytics_service.get_trends(db, days)

@router.get("/dashboard")
async def get_dashboard_data(
    current_user = Depends(require_roles(["admin", "doctor", "nurse"])),
    db: Session = Depends(get_db)
):
    """Получение данных для дашборда"""
    # Данные за сегодня
    today = datetime.now().date()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())
    
    # Данные за неделю
    week_start = today_start - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    
    # Данные за месяц
    month_start = today_start.replace(day=1)
    if today.month == 12:
        month_end = today_start.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        month_end = today_start.replace(month=today.month + 1, day=1) - timedelta(days=1)
    
    dashboard_data = {
        "today": {
            "visits": analytics_service.get_visit_statistics(db, today_start, today_end),
            "revenue": analytics_service.get_revenue_statistics(db, today_start, today_end),
            "queues": analytics_service.get_queue_statistics(db, today_start, today_end)
        },
        "week": {
            "visits": analytics_service.get_visit_statistics(db, week_start, week_end),
            "revenue": analytics_service.get_revenue_statistics(db, week_start, week_end),
            "queues": analytics_service.get_queue_statistics(db, week_start, week_end)
        },
        "month": {
            "visits": analytics_service.get_visit_statistics(db, month_start, month_end),
            "revenue": analytics_service.get_revenue_statistics(db, month_start, month_end),
            "queues": analytics_service.get_queue_statistics(db, month_start, month_end),
            "patients": analytics_service.get_patient_statistics(db, month_start, month_end),
            "services": analytics_service.get_service_statistics(db, month_start, month_end)
        },
        "trends": analytics_service.get_trends(db, 7),  # Тренды за неделю
        "generated_at": datetime.utcnow().isoformat()
    }
    
    return dashboard_data

@router.get("/quick-stats")
async def get_quick_stats(
    current_user = Depends(require_roles(["admin", "doctor", "nurse"])),
    db: Session = Depends(get_db)
):
    """Получение быстрой статистики"""
    today = datetime.now().date()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())
    
    # Импортируем здесь, чтобы избежать циклических импортов
    from app.models.visit import Visit
    from app.models.patient import Patient
    from app.models.payment_webhook import PaymentWebhook
    
    # Быстрые подсчёты
    today_visits = db.query(Visit).filter(
        Visit.date >= today_start,
        Visit.date <= today_end
    ).count()
    
    today_patients = db.query(Patient).filter(
        Patient.created_at >= today_start,
        Patient.created_at <= today_end
    ).count()
    
    today_revenue = db.query(PaymentWebhook).filter(
        and_(
            PaymentWebhook.status == "success",
            PaymentWebhook.created_at >= today_start,
            PaymentWebhook.created_at <= today_end
        )
    ).all()
    
    total_revenue = sum(float(p.amount) / 100 for p in today_revenue)
    
    return {
        "today": {
            "visits": today_visits,
            "new_patients": today_patients,
            "revenue": total_revenue,
            "transactions": len(today_revenue)
        },
        "generated_at": datetime.utcnow().isoformat()
    }

