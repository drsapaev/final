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
from app.services.morning_assignment import (
    get_assignment_stats,
    MorningAssignmentService,
    run_morning_assignment,
)

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
        # Парсим дату
        if target_date:
            try:
                parsed_date = datetime.strptime(target_date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Неверный формат даты. Используйте YYYY-MM-DD",
                )
        else:
            parsed_date = date.today()

        # Запускаем утреннюю сборку
        result = run_morning_assignment(parsed_date)

        return MorningAssignmentResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка запуска утренней сборки: {str(e)}",
        )


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
        # Парсим дату
        if target_date:
            try:
                parsed_date = datetime.strptime(target_date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Неверный формат даты. Используйте YYYY-MM-DD",
                )
        else:
            parsed_date = date.today()

        # Получаем статистику
        stats = get_assignment_stats(parsed_date)

        return AssignmentStatsResponse(**stats)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения статистики: {str(e)}",
        )


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
    try:
        with MorningAssignmentService() as service:
            service.db = db

            results = []

            for visit_id in request.visit_ids:
                # Получаем визит
                from app.models.visit import Visit

                visit = db.query(Visit).filter(Visit.id == visit_id).first()

                if not visit:
                    results.append(
                        {
                            "visit_id": visit_id,
                            "success": False,
                            "message": "Визит не найден",
                        }
                    )
                    continue

                if visit.status not in ["confirmed", "open"] and not request.force:
                    results.append(
                        {
                            "visit_id": visit_id,
                            "success": False,
                            "message": f"Визит имеет статус {visit.status}, используйте force=true для принудительной обработки",
                        }
                    )
                    continue

                try:
                    # Присваиваем номера для визита
                    queue_assignments = service._assign_queues_for_visit(
                        visit, visit.visit_date
                    )

                    if queue_assignments:
                        visit.status = "open"
                        results.append(
                            {
                                "visit_id": visit_id,
                                "success": True,
                                "message": f"Присвоено {len(queue_assignments)} номеров",
                                "queue_assignments": queue_assignments,
                            }
                        )
                    else:
                        results.append(
                            {
                                "visit_id": visit_id,
                                "success": False,
                                "message": "Не удалось присвоить номера",
                            }
                        )

                except Exception as e:
                    results.append(
                        {
                            "visit_id": visit_id,
                            "success": False,
                            "message": f"Ошибка: {str(e)}",
                        }
                    )

            db.commit()

            return {
                "success": True,
                "message": f"Обработано {len(request.visit_ids)} визитов",
                "results": results,
            }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка ручного присвоения: {str(e)}",
        )


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
        # Парсим дату
        if target_date:
            try:
                parsed_date = datetime.strptime(target_date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Неверный формат даты. Используйте YYYY-MM-DD",
                )
        else:
            parsed_date = date.today()

        with MorningAssignmentService() as service:
            service.db = db
            pending_visits = service._get_confirmed_visits_without_queues(parsed_date)

            visits_info = []
            for visit in pending_visits:
                from app.models.patient import Patient

                patient = (
                    db.query(Patient).filter(Patient.id == visit.patient_id).first()
                )

                queue_tags = service._get_visit_queue_tags(visit)

                visits_info.append(
                    {
                        "visit_id": visit.id,
                        "patient_id": visit.patient_id,
                        "patient_name": (
                            patient.short_name() if patient else "Неизвестный"
                        ),
                        "visit_date": visit.visit_date.isoformat(),
                        "visit_time": visit.visit_time,
                        "status": visit.status,
                        "confirmed_at": (
                            visit.confirmed_at.isoformat()
                            if visit.confirmed_at
                            else None
                        ),
                        "queue_tags": list(queue_tags),
                        "department": visit.department,
                    }
                )

            return {
                "success": True,
                "date": parsed_date.isoformat(),
                "pending_visits_count": len(pending_visits),
                "pending_visits": visits_info,
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения ожидающих визитов: {str(e)}",
        )


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
        # Парсим дату
        if target_date:
            try:
                parsed_date = datetime.strptime(target_date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Неверный формат даты. Используйте YYYY-MM-DD",
                )
        else:
            parsed_date = date.today()

        from app.models.clinic import Doctor
        from app.models.online_queue import DailyQueue, OnlineQueueEntry

        # Получаем все очереди на дату
        queues = db.query(DailyQueue).filter(DailyQueue.day == parsed_date).all()

        queue_summary = []
        for queue in queues:
            # Подсчитываем записи в очереди
            entries_count = (
                db.query(OnlineQueueEntry)
                .filter(OnlineQueueEntry.queue_id == queue.id)
                .count()
            )

            # Получаем информацию о враче
            doctor = db.query(Doctor).filter(Doctor.id == queue.specialist_id).first()
            doctor_name = (
                doctor.user.full_name
                if doctor and doctor.user
                else f"ID:{queue.specialist_id}"
            )

            queue_summary.append(
                {
                    "queue_id": queue.id,
                    "queue_tag": queue.queue_tag or "general",
                    "doctor_name": doctor_name,
                    "doctor_id": queue.specialist_id,
                    "entries_count": entries_count,
                    "active": queue.active,
                    "opened_at": (
                        queue.opened_at.isoformat() if queue.opened_at else None
                    ),
                }
            )

        return {
            "success": True,
            "date": parsed_date.isoformat(),
            "queues_count": len(queues),
            "total_entries": sum(q["entries_count"] for q in queue_summary),
            "queues": queue_summary,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения сводки очередей: {str(e)}",
        )
