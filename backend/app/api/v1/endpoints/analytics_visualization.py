"""
API endpoints для визуализации аналитических данных
"""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user
from app.services.analytics_visualization_service import get_analytics_visualization_service, AnalyticsVisualizationService
from app.services.analytics import AnalyticsService
from app.services.advanced_analytics import get_advanced_analytics_service, AdvancedAnalyticsService

router = APIRouter()


@router.get("/dashboard")
async def get_dashboard_visualization(
    start_date: str = Query(..., description="Начальная дата (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Конечная дата (YYYY-MM-DD)"),
    department: Optional[str] = Query(None, description="Отделение"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Получить визуализацию для дашборда"""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты")

    if start > end:
        raise HTTPException(
            status_code=400, detail="Начальная дата должна быть раньше конечной"
        )

    # Получаем данные дашборда
    analytics_service = get_advanced_analytics_service()
    dashboard_data = {
        "today": {
            "visits": analytics_service.get_visit_statistics(db, start, end, department),
            "revenue": analytics_service.get_revenue_statistics(db, start, end, department),
            "queues": analytics_service.get_queue_statistics(db, start, end, department)
        }
    }
    
    # Создаем визуализацию
    viz_service = get_analytics_visualization_service()
    charts = viz_service.create_dashboard_charts(dashboard_data)
    
    # Конвертируем в конфигурации Chart.js
    chart_configs = {}
    for chart_name, chart_data in charts.items():
        chart_configs[chart_name] = viz_service.get_chart_config(chart_data)
    
    return {
        "period": {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "department": department or "all"
        },
        "charts": chart_configs,
        "summary": {
            "total_charts": len(chart_configs),
            "chart_types": list(set(config["type"] for config in chart_configs.values())),
            "generated_at": datetime.utcnow().isoformat()
        }
    }


@router.get("/kpi")
async def get_kpi_visualization(
    start_date: str = Query(..., description="Начальная дата (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Конечная дата (YYYY-MM-DD)"),
    department: Optional[str] = Query(None, description="Отделение"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Получить визуализацию KPI метрик"""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты")

    if start > end:
        raise HTTPException(
            status_code=400, detail="Начальная дата должна быть раньше конечной"
        )

    # Получаем KPI данные через SSOT
    kpi_data = AnalyticsService.calculate_statistics(db, start, end, department)
    
    # Создаем визуализацию
    viz_service = get_analytics_visualization_service()
    charts = viz_service.create_kpi_charts(kpi_data)
    
    # Конвертируем в конфигурации Chart.js
    chart_configs = {}
    for chart_name, chart_data in charts.items():
        chart_configs[chart_name] = viz_service.get_chart_config(chart_data)
    
    return {
        "period": {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "department": department or "all"
        },
        "kpi_data": kpi_data,
        "charts": chart_configs,
        "summary": {
            "total_charts": len(chart_configs),
            "chart_types": list(set(config["type"] for config in chart_configs.values())),
            "generated_at": datetime.utcnow().isoformat()
        }
    }


@router.get("/doctors/performance")
async def get_doctor_performance_visualization(
    start_date: str = Query(..., description="Начальная дата (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Конечная дата (YYYY-MM-DD)"),
    department: Optional[str] = Query(None, description="Отделение"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Получить визуализацию эффективности врачей"""
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
    
    # Создаем визуализацию
    viz_service = get_analytics_visualization_service()
    charts = viz_service.create_doctor_performance_charts(doctor_data)
    
    # Конвертируем в конфигурации Chart.js
    chart_configs = {}
    for chart_name, chart_data in charts.items():
        chart_configs[chart_name] = viz_service.get_chart_config(chart_data)
    
    return {
        "period": {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "department": department or "all"
        },
        "doctor_data": doctor_data,
        "charts": chart_configs,
        "summary": {
            "total_charts": len(chart_configs),
            "chart_types": list(set(config["type"] for config in chart_configs.values())),
            "generated_at": datetime.utcnow().isoformat()
        }
    }


@router.get("/patients")
async def get_patient_analytics_visualization(
    start_date: str = Query(..., description="Начальная дата (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Конечная дата (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Получить визуализацию аналитики пациентов"""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты")

    if start > end:
        raise HTTPException(
            status_code=400, detail="Начальная дата должна быть раньше конечной"
        )

    # Получаем данные по пациентам
    analytics_service = get_advanced_analytics_service()
    patient_data = analytics_service.get_patient_analytics(db, start, end)
    
    # Создаем визуализацию
    viz_service = get_analytics_visualization_service()
    charts = viz_service.create_patient_analytics_charts(patient_data)
    
    # Конвертируем в конфигурации Chart.js
    chart_configs = {}
    for chart_name, chart_data in charts.items():
        chart_configs[chart_name] = viz_service.get_chart_config(chart_data)
    
    return {
        "period": {
            "start_date": start.isoformat(),
            "end_date": end.isoformat()
        },
        "patient_data": patient_data,
        "charts": chart_configs,
        "summary": {
            "total_charts": len(chart_configs),
            "chart_types": list(set(config["type"] for config in chart_configs.values())),
            "generated_at": datetime.utcnow().isoformat()
        }
    }


@router.get("/revenue")
async def get_revenue_analytics_visualization(
    start_date: str = Query(..., description="Начальная дата (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Конечная дата (YYYY-MM-DD)"),
    department: Optional[str] = Query(None, description="Отделение"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Получить визуализацию аналитики доходов"""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты")

    if start > end:
        raise HTTPException(
            status_code=400, detail="Начальная дата должна быть раньше конечной"
        )

    # Получаем данные по доходам через SSOT
    revenue_data = AnalyticsService.calculate_revenue(db, start, end, department)
    
    # Создаем визуализацию
    viz_service = get_analytics_visualization_service()
    charts = viz_service.create_revenue_charts(revenue_data)
    
    # Конвертируем в конфигурации Chart.js
    chart_configs = {}
    for chart_name, chart_data in charts.items():
        chart_configs[chart_name] = viz_service.get_chart_config(chart_data)
    
    return {
        "period": {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "department": department or "all"
        },
        "revenue_data": revenue_data,
        "charts": chart_configs,
        "summary": {
            "total_charts": len(chart_configs),
            "chart_types": list(set(config["type"] for config in chart_configs.values())),
            "generated_at": datetime.utcnow().isoformat()
        }
    }


@router.get("/comprehensive")
async def get_comprehensive_visualization(
    start_date: str = Query(..., description="Начальная дата (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Конечная дата (YYYY-MM-DD)"),
    department: Optional[str] = Query(None, description="Отделение"),
    include_predictive: bool = Query(True, description="Включить предиктивную аналитику"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Получить полную визуализацию для комплексного отчета"""
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
    
    comprehensive_data = {
        "report_period": {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "department": department or "all",
            "generated_at": datetime.utcnow().isoformat()
        },
        "kpi_metrics": AnalyticsService.calculate_statistics(db, start, end, department),
        "doctor_performance": analytics_service.get_doctor_performance(db, start, end, department),
        "patient_analytics": analytics_service.get_patient_analytics(db, start, end),
        "revenue_analytics": AnalyticsService.calculate_revenue(db, start, end, department)
    }
    
    if include_predictive:
        comprehensive_data["predictive_analytics"] = analytics_service.get_predictive_analytics(db, 30)
    
    # Создаем полную визуализацию
    viz_service = get_analytics_visualization_service()
    visualization = viz_service.create_comprehensive_visualization(comprehensive_data)
    
    # Конвертируем все графики в конфигурации Chart.js
    for category, charts in visualization["charts"].items():
        for chart_name, chart_data in charts.items():
            charts[chart_name] = viz_service.get_chart_config(chart_data)
    
    return {
        "period": {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "department": department or "all"
        },
        "data": comprehensive_data,
        "visualization": visualization,
        "generated_at": datetime.utcnow().isoformat()
    }


@router.get("/chart-types")
async def get_supported_chart_types(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Получить список поддерживаемых типов графиков"""
    return {
        "supported_chart_types": [
            {
                "type": "line",
                "name": "Линейный график",
                "description": "Для отображения трендов и изменений во времени",
                "use_cases": ["Тренды визитов", "Динамика доходов", "Эффективность по времени"]
            },
            {
                "type": "bar",
                "name": "Столбчатая диаграмма",
                "description": "Для сравнения категорий и значений",
                "use_cases": ["Сравнение отделений", "Топ врачей", "Возрастные группы"]
            },
            {
                "type": "doughnut",
                "name": "Круговая диаграмма",
                "description": "Для отображения пропорций и распределений",
                "use_cases": ["Распределение по полу", "Методы оплаты", "Доли категорий"]
            },
            {
                "type": "radar",
                "name": "Радиальная диаграмма",
                "description": "Для отображения многомерных данных и KPI",
                "use_cases": ["KPI показатели", "Профили эффективности", "Сравнение метрик"]
            }
        ],
        "total_types": 4,
        "chart_library": "Chart.js",
        "features": [
            "Responsive design",
            "Interactive tooltips",
            "Custom colors",
            "Multiple datasets",
            "Animation support"
        ]
    }


@router.get("/health")
async def visualization_health_check():
    """Проверка здоровья сервиса визуализации"""
    return {
        "status": "ok",
        "visualization_service": "active",
        "supported_chart_types": ["line", "bar", "doughnut", "radar"],
        "chart_library": "Chart.js",
        "features": [
            "dashboard_visualization",
            "kpi_visualization", 
            "doctor_performance_visualization",
            "patient_analytics_visualization",
            "revenue_analytics_visualization",
            "comprehensive_visualization"
        ]
    }
