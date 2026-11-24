"""Split from qr_queue.py.
"""
from __future__ import annotations

from app.api.v1.endpoints.qr_queue._helpers import *  # noqa: F401, F403
from app.api.v1.endpoints.qr_queue._helpers import (
    _ensure_doctor_can_mutate_queue_entry,
    router,
)
from app.api.v1.endpoints.qr_queue._tokens import (
    RestoreToNextRequest,  # noqa: F401
    SetIncompleteRequest,  # noqa: F401
)
from app.services.doctor_queue_diagnostics import (
    change_diagnostic_queue_status,
    lock_active_doctor_visit,
)


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

    # QRRESTORE-BE-001 (audit #3892 group 26): the canonical
    # OnlineQueueNewService.cancel_entry cancels the entry AND its linked
    # Visit (cascade _cascade_linked_visit_cancel: visit -> "canceled")
    # and releases the pending invoice in one transaction. Restoring just
    # the queue row would leave entry.status="waiting" anchored to
    # Visit.status="canceled" — a state the irreversible visit lifecycle
    # cannot start — while the operator has already been told the ticket
    # is restored. Deny with an actionable 409: create a new appointment
    # instead. no_show tickets and cancelled tickets without a
    # cascade-cancelled visit keep restoring as before.
    if entry.status == "cancelled" and entry.visit_id:
        from app.models.visit import Visit as _Visit

        linked_visit = (
            db.query(_Visit).filter(_Visit.id == entry.visit_id).first()
        )
        if linked_visit is not None and linked_visit.status == "canceled":
            logger.warning(
                "[restore_entry_to_next] Отказано: запись %d отменена вместе "
                "с визитом (visit_id=%d), восстановление разорвало бы "
                "инвариант жизненного цикла",
                entry_id,
                entry.visit_id,
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Запись была отменена вместе с визитом — восстановление "
                    "недоступно; создайте новую запись пациента"
                ),
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

        from app.ws.queue_ws import broadcast_queue_update, queue_update_departments
        _date_str = entry.queue.day.strftime("%Y-%m-%d") if hasattr(entry.queue, "day") and entry.queue.day else _date.today().strftime("%Y-%m-%d")
        # QD-2C (Codex round-17/18 P2): комната — маршрутизирующая
        # идентичность (specialist_None не слушает никто)
        for _dept in queue_update_departments(db, getattr(entry, "queue", None)):
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

        from app.ws.queue_ws import broadcast_queue_update, queue_update_departments
        _date_str = entry.queue.day.strftime("%Y-%m-%d") if hasattr(entry.queue, "day") and entry.queue.day else _date.today().strftime("%Y-%m-%d")
        # QD-2C (Codex round-17/18 P2): комната — маршрутизирующая
        # идентичность (specialist_None не слушает никто)
        for _dept in queue_update_departments(db, getattr(entry, "queue", None)):
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

    if entry.status == "in_progress":
        linked_visit = lock_active_doctor_visit(db, entry, entry.queue)
        if linked_visit is None:
            raise HTTPException(status_code=409, detail="Нет связанного активного приёма")
        started_at = change_diagnostic_queue_status(
            db, entry, linked_visit, from_status="in_progress", to_status="diagnostics",
        )
        if started_at is None:
            raise HTTPException(status_code=409, detail="Состояние очереди уже изменилось")
    else:
        if entry.status not in {"called", "in_service"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Отправка на обследование недоступна из статуса {entry.status}",
            )
        started_at = datetime.now(UTC)
        entry.status = "diagnostics"
        entry.diagnostics_started_at = started_at
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
        "started_at": started_at.isoformat().replace("+00:00", "Z")
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

    # The legacy command closes only the queue row. With a resumable
    # clinical visit, that would leave the doctor's visit active but stranded.
    # Pause/resume locks the same Visit before changing the queue row.
    if entry.status == "diagnostics" and lock_active_doctor_visit(db, entry, entry.queue) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="У пациента активный приём. Возобновите и завершите его в карточке приёма.",
        )

    changed = (
        db.query(OnlineQueueEntry)
        .filter(
            OnlineQueueEntry.id == entry_id,
            OnlineQueueEntry.queue_id == entry.queue_id,
            OnlineQueueEntry.visit_id == entry.visit_id,
            OnlineQueueEntry.patient_id == entry.patient_id,
            OnlineQueueEntry.status == entry.status,
            OnlineQueueEntry.diagnostics_started_at == entry.diagnostics_started_at,
        )
        .update(
            {
                OnlineQueueEntry.status: "incomplete",
                OnlineQueueEntry.incomplete_reason: request.reason,
            },
            synchronize_session=False,
        )
    )
    if changed != 1:
        raise HTTPException(status_code=409, detail="Состояние очереди уже изменилось")
    db.commit()

    logger.info(
        "[mark_entry_incomplete] Запись %d отмечена как incomplete пользователем %d",
        entry_id,
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


