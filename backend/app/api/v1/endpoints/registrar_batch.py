"""
API endpoints для batch-операций с записями пациента.

Решает проблему UI Row ↔ API Entry mismatch:
- UI показывает пациента как одну строку
- API оперирует множеством entries

Этот endpoint обеспечивает атомарные операции над всеми записями.
"""

from __future__ import annotations

from datetime import date as date_type, datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.user import User
from app.services.batch_patient_service import (
    BatchPatientService,
    BatchUpdateRequest,
    BatchUpdateResponse,
    get_batch_patient_service,
)

router = APIRouter(prefix="/batch", tags=["registrar-batch"])


# ============================================================================
# SCHEMAS
# ============================================================================

class PatientEntriesResponse(BaseModel):
    """Ответ с записями пациента за день"""
    patient_id: int
    date: str
    online_queue_entries: List[Dict[str, Any]]
    visits: List[Dict[str, Any]]
    aggregated: Dict[str, Any]


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get(
    "/patients/{patient_id}/entries/{date}",
    response_model=PatientEntriesResponse,
    summary="Получить все записи пациента за день"
)
async def get_patient_entries(
    patient_id: int = Path(..., description="ID пациента"),
    date: str = Path(..., description="Дата в формате YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor")),
):
    """
    Получить все записи пациента на указанную дату.
    
    Возвращает:
    - online_queue_entries: записи OnlineQueueEntry
    - visits: записи Visit
    - aggregated: агрегированные данные (как показывается в UI)
    
    Доступно: Admin, Registrar, Doctor
    """
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Use YYYY-MM-DD"
        )
    
    service = get_batch_patient_service(db)
    result = service.get_patient_entries_for_date(patient_id, target_date)
    
    # Конвертируем ORM объекты в dict
    response = {
        "patient_id": result["patient_id"],
        "date": result["date"],
        "online_queue_entries": [
            {
                "id": e.id,
                "number": e.number,
                "status": e.status,
                "queue_tag": e.queue_tag,
                "service_code": e.service_code,
                "service_id": e.service_id,
                "queue_time": e.queue_time.isoformat() if e.queue_time else None
            }
            for e in result["online_queue_entries"]
        ],
        "visits": [
            {
                "id": v.id,
                "status": v.status,
                "doctor_id": v.doctor_id,
                "visit_date": str(v.visit_date) if v.visit_date else None,
                "cost": float(v.cost) if hasattr(v, 'cost') and v.cost else 0
            }
            for v in result["visits"]
        ],
        "aggregated": result["aggregated"]
    }
    
    return PatientEntriesResponse(**response)


@router.patch(
    "/patients/{patient_id}/entries/{date}",
    response_model=BatchUpdateResponse,
    summary="Batch-обновление записей пациента"
)
async def batch_update_patient_entries(
    patient_id: int = Path(..., description="ID пациента"),
    date: str = Path(..., description="Дата в формате YYYY-MM-DD"),
    request: BatchUpdateRequest = ...,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    ⭐ Атомарное batch-обновление всех записей пациента за день.
    
    Поддерживаемые действия для каждой записи:
    - update: обновить поля записи
    - cancel: отменить запись
    - create: создать новую запись
    
    Также можно применить common_updates ко всем записям:
    - payment_type
    - discount_mode
    - notes
    
    Атомарность: если хотя бы одна операция не удалась,
    все изменения откатываются.
    
    Доступно: Admin, Registrar
    
    Example Request:
    ```json
    {
      "entries": [
        {"id": 123, "action": "update", "status": "called"},
        {"id": 124, "action": "cancel", "reason": "Patient request"},
        {"id": null, "action": "create", "specialty": "cardiology"}
      ],
      "common_updates": {
        "payment_type": "card",
        "discount_mode": "percent_10"
      }
    }
    ```
    """
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Use YYYY-MM-DD"
        )
    
    service = get_batch_patient_service(db)
    result = service.batch_update(patient_id, target_date, request)
    
    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error or "Batch update failed"
        )
    
    return result


@router.delete(
    "/patients/{patient_id}/entries/{date}",
    summary="Отменить все записи пациента за день"
)
async def cancel_all_patient_entries(
    patient_id: int = Path(..., description="ID пациента"),
    date: str = Path(..., description="Дата в формате YYYY-MM-DD"),
    reason: str = Query("bulk_cancel", description="Причина отмены"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Отменить ВСЕ записи пациента на указанную дату.
    
    Это эквивалент вызова batch_update с action="cancel" для всех записей.
    Используется для полной отмены визита пациента.
    
    Доступно: Admin, Registrar
    """
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Use YYYY-MM-DD"
        )
    
    service = get_batch_patient_service(db)
    
    # Получаем все записи
    entries_data = service.get_patient_entries_for_date(patient_id, target_date)
    
    # Формируем запрос на отмену всех
    cancel_actions = []
    
    for entry in entries_data["online_queue_entries"]:
        cancel_actions.append({
            "id": entry.id,
            "action": "cancel",
            "reason": reason
        })
    
    for visit in entries_data["visits"]:
        cancel_actions.append({
            "id": visit.id,
            "action": "cancel",
            "reason": reason
        })
    
    if not cancel_actions:
        return {
            "success": True,
            "message": "No entries to cancel",
            "cancelled_count": 0
        }
    
    # Выполняем batch-отмену
    from app.services.batch_patient_service import EntryAction
    request = BatchUpdateRequest(
        entries=[EntryAction(**a) for a in cancel_actions]
    )
    
    result = service.batch_update(patient_id, target_date, request)
    
    return {
        "success": result.success,
        "message": f"Cancelled {len(cancel_actions)} entries",
        "cancelled_count": len(cancel_actions),
        "details": result.updated_entries
    }
