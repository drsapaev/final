"""
API endpoints для утренней сборки и управления присвоением номеров
"""

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.user import User
from app.services.morning_assignment_api_service import MorningAssignmentApiService

router = APIRouter()

# ===================== МОДЕЛИ ДАННЫХ =====================


class MorningAssignmentResponse(BaseModel):
    success: bool
    message: str
    processed_visits: int
    assigned_queues: int
    errors: list
    date: str


class AssignmentStatsResponse(BaseModel):
    date: str
    confirmed_visits: int
    processed_visits: int
    queue_entries: int
    pending_processing: int


class ManualAssignmentRequest(BaseModel):
    visit_ids: list[int] = Field(..., description="Список ID визитов для обработки")
    force: bool = Field(
        default=False, description="Принудительная обработка даже если уже есть номера"
    )


# ===================== УТРЕННЯЯ СБОРКА =====================


@router.post("/admin/morning-assignment/run", response_model=MorningAssignmentResponse)
def run_morning_assignment_manual(
    target_date: Optional[str] = Query(
        None, description="Дата в формате YYYY-MM-DD, по умолчанию сегодня"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Ручной запуск утренней сборки для присвоения номеров в очередях
    Обрабатывает все подтвержденные визиты на указанную дату
    """
    try:
        api_service = MorningAssignmentApiService(db)
        parsed_date = api_service.parse_target_date(target_date)
        result = api_service.run_assignment_for_date(target_date=parsed_date)

        return MorningAssignmentResponse(**result)

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный формат даты. Используйте YYYY-MM-DD",
        ) from exc
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка запуска утренней сборки: {str(e)}",
        ) from e


@router.get("/admin/morning-assignment/stats", response_model=AssignmentStatsResponse)
def get_morning_assignment_stats(
    target_date: Optional[str] = Query(
        None, description="Дата в формате YYYY-MM-DD, по умолчанию сегодня"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor")),
):
    """
    Получение статистики утренней сборки
    Показывает количество обработанных визитов и записей в очередях
    """
    try:
        api_service = MorningAssignmentApiService(db)
        parsed_date = api_service.parse_target_date(target_date)
        stats = api_service.get_stats_for_date(target_date=parsed_date)

        return AssignmentStatsResponse(**stats)

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный формат даты. Используйте YYYY-MM-DD",
        ) from exc
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения статистики: {str(e)}",
        ) from e


@router.post("/admin/morning-assignment/manual")
def manual_assignment_for_visits(
    request: ManualAssignmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Ручное присвоение номеров для конкретных визитов
    Полезно для исправления ошибок или обработки отдельных случаев
    """
    api_service = MorningAssignmentApiService(db)
    try:
        return api_service.manual_assignment_for_visits(
            visit_ids=request.visit_ids,
            force=request.force,
        )
    except HTTPException:
        raise
    except Exception as e:
        api_service.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка ручного присвоения: {str(e)}",
        ) from e


# ===================== ИНФОРМАЦИОННЫЕ ЭНДПОИНТЫ =====================


@router.get("/admin/morning-assignment/pending-visits")
def get_pending_visits(
    target_date: Optional[str] = Query(
        None, description="Дата в формате YYYY-MM-DD, по умолчанию сегодня"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor")),
):
    """
    Получение списка визитов, ожидающих присвоения номеров
    """
    try:
        api_service = MorningAssignmentApiService(db)
        parsed_date = api_service.parse_target_date(target_date)
        return api_service.get_pending_visits_payload(target_date=parsed_date)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный формат даты. Используйте YYYY-MM-DD",
        ) from exc
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения ожидающих визитов: {str(e)}",
        ) from e


@router.get("/admin/morning-assignment/queue-summary")
def get_queue_summary(
    target_date: Optional[str] = Query(
        None, description="Дата в формате YYYY-MM-DD, по умолчанию сегодня"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor")),
):
    """
    Получение сводки по очередям на указанную дату
    """
    try:
        api_service = MorningAssignmentApiService(db)
        parsed_date = api_service.parse_target_date(target_date)
        return api_service.get_queue_summary_payload(target_date=parsed_date)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный формат даты. Используйте YYYY-MM-DD",
        ) from exc
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения сводки очередей: {str(e)}",
        ) from e
