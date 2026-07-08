"""Split from qr_queue.py.
"""
from __future__ import annotations

from app.api.v1.endpoints.qr_queue._helpers import *  # noqa: F401, F403
from app.api.v1.endpoints.qr_queue._helpers import router


@router.post("/entry/{entry_id}/restore-next", response_model=dict[str, Any])
async def restore_entry_to_next(
    entry_id: int,
    request: RestoreToNextRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar")),
):
    """
    Восстанавливает пациента no_show как следующего в очереди
    Устанавливает priority=1 для приоритетной обработки
    """
    from app.models.online_queue import OnlineQueueEntry

    entry = db.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Запись в очереди не найдена"
        )

    _ensure_doctor_can_mutate_queue_entry(
        db,
        entry=entry,
        current_user=current_user,
    )

    if entry.status not in ["no_show", "cancelled"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Можно восстановить только записи со статусом no_show или cancelled, текущий: {entry.status}"
        )

    # Восстанавливаем с приоритетом "следующий"
    entry.status = "waiting"
    entry.priority = 1  # Следующий в очереди
    db.commit()

    logger.info(
        "[restore_entry_to_next] Запись %d восстановлена следующей по запросу пользователя %d",
        entry_id,
        current_user.id
    )

    # --- Display Notification ---
    try:
        from app.services.display_websocket import get_display_manager
        manager = get_display_manager()
        await manager.broadcast_queue_update(queue_entry=entry, event_type="queue.restored")
    except Exception as e:
        logger.warning(f"Failed to update display for entry {entry_id}: {e}")

    # UX Audit Stage 3 (Queue WebSocket): broadcast to /ws/queue admin panel.
    try:
        from datetime import date as _date

        from app.ws.queue_ws import broadcast_queue_update
        _date_str = entry.queue.day.strftime("%Y-%m-%d") if hasattr(entry.queue, "day") and entry.queue.day else _date.today().strftime("%Y-%m-%d")
        _dept = f"specialist_{entry.queue.specialist_id}" if entry.queue else "unknown"
        broadcast_queue_update(
            department=_dept,
            date=_date_str,
            event_type="queue_update",
            data={"action": "restore_next", "entry_id": entry_id},
        )
    except Exception as e:
        logger.warning(f"Failed to broadcast queue WS update for entry {entry_id}: {e}")
    # ----------------------------

    return {
        "success": True,
        "message": "Пациент восстановлен как следующий в очереди",
        "entry_id": entry_id,
        "new_status": "waiting",
        "priority": 1
    }


@router.post("/entry/{entry_id}/no-show", response_model=dict[str, Any])
async def mark_entry_no_show(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar")),
):
    """
    Отмечает пациента как неявившегося (no_show)
    """
    from app.models.online_queue import OnlineQueueEntry

    entry = db.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Запись в очереди не найдена"
        )

    _ensure_doctor_can_mutate_queue_entry(
        db,
        entry=entry,
        current_user=current_user,
    )

    if entry.status not in ["waiting", "called"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Неявку можно отметить только для waiting или called, текущий: {entry.status}"
        )

    entry.status = "no_show"
    db.commit()

    logger.info(
        "[mark_entry_no_show] Запись %d отмечена как no_show пользователем %d",
        entry_id,
        current_user.id
    )

    # --- Display Notification ---
    try:
        from app.services.display_websocket import get_display_manager
        manager = get_display_manager()
        await manager.broadcast_queue_update(queue_entry=entry, event_type="queue.updated")
        # Also clean up from "Called" section if it was there
    except Exception as e:
        logger.warning(f"Failed to update display for entry {entry_id}: {e}")

    # UX Audit Stage 3 (Queue WebSocket): broadcast to /ws/queue admin panel.
    try:
        from datetime import date as _date

        from app.ws.queue_ws import broadcast_queue_update
        _date_str = entry.queue.day.strftime("%Y-%m-%d") if hasattr(entry.queue, "day") and entry.queue.day else _date.today().strftime("%Y-%m-%d")
        _dept = f"specialist_{entry.queue.specialist_id}" if entry.queue else "unknown"
        broadcast_queue_update(
            department=_dept,
            date=_date_str,
            event_type="queue_update",
            data={"action": "no_show", "entry_id": entry_id},
        )
    except Exception as e:
        logger.warning(f"Failed to broadcast queue WS update for entry {entry_id}: {e}")
    # ----------------------------

    return {
        "success": True,
        "message": "Пациент отмечен как неявившийся",
        "entry_id": entry_id,
        "new_status": "no_show"
    }


@router.post("/entry/{entry_id}/diagnostics", response_model=dict[str, Any])
def send_entry_to_diagnostics(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar")),
):
    """
    Отправляет пациента на обследование (diagnostics)
    Запускает таймер ожидания
    """
    from app.models.online_queue import OnlineQueueEntry

    entry = db.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Запись в очереди не найдена"
        )

    _ensure_doctor_can_mutate_queue_entry(
        db,
        entry=entry,
        current_user=current_user,
    )

    if entry.status not in ["called", "in_service"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"На обследование можно отправить только called или in_service, текущий: {entry.status}"
        )

    entry.status = "diagnostics"
    entry.diagnostics_started_at = datetime.now(UTC)
    db.commit()

    logger.info(
        "[send_entry_to_diagnostics] Запись %d отправлена на диагностику пользователем %d",
        entry_id,
        current_user.id
    )

    return {
        "success": True,
        "message": "Пациент отправлен на обследование",
        "entry_id": entry_id,
        "new_status": "diagnostics",
        "started_at": entry.diagnostics_started_at.isoformat() + "Z"
    }


@router.post("/entry/{entry_id}/incomplete", response_model=dict[str, Any])
def mark_entry_incomplete(
    entry_id: int,
    request: SetIncompleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar")),
):
    """
    Завершает приём с указанием причины незавершённости (incomplete)
    """
    from app.models.online_queue import OnlineQueueEntry

    entry = db.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Запись в очереди не найдена"
        )

    _ensure_doctor_can_mutate_queue_entry(
        db,
        entry=entry,
        current_user=current_user,
    )

    if entry.status not in ["called", "in_service", "diagnostics"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Incomplete можно установить только для called/in_service/diagnostics, текущий: {entry.status}"
        )

    entry.status = "incomplete"
    entry.incomplete_reason = request.reason
    db.commit()

    logger.info(
        "[mark_entry_incomplete] Запись %d отмечена как incomplete (причина: %s) пользователем %d",
        entry_id,
        request.reason,
        current_user.id
    )

    return {
        "success": True,
        "message": "Приём отмечен как незавершённый",
        "entry_id": entry_id,
        "new_status": "incomplete",
        "reason": request.reason
    }


# ===================== СТАТИСТИКА И АНАЛИТИКА =====================


