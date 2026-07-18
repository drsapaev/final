"""Split from qr_queue.py.
"""
from __future__ import annotations

from app.api.v1.endpoints.qr_queue._helpers import *  # noqa: F401, F403
from app.api.v1.endpoints.qr_queue._helpers import (
    _ensure_doctor_can_mutate_specialist_queue,
    router,
)


@router.get("/status/{specialist_id}", response_model=QueueStatusResponse)
def get_queue_status(
    specialist_id: int,
    target_date: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar")),
):
    """
    Получает статус очереди специалиста
    Доступно администраторам, врачам и регистраторам
    """
    service = QRQueueService(db)

    # Парсим дату если указана
    parsed_date = None
    if target_date:
        try:
            parsed_date = datetime.strptime(target_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неверный формат даты. Используйте YYYY-MM-DD",
            )

    result = service.get_queue_status(specialist_id, parsed_date)

    return QueueStatusResponse(**result)


@router.post("/{specialist_id}/call-next", response_model=CallNextPatientResponse)
async def call_next_patient(
    specialist_id: int,
    target_date: str | None = Query(
        None, description="Дата очереди (YYYY-MM-DD), по умолчанию сегодня"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar")),
):
    """
    Вызывает следующего пациента в очереди
    Доступно администраторам, врачам и регистраторам
    """
    service = QRQueueService(db)

    try:
        # Парсим дату, если передана
        _ensure_doctor_can_mutate_specialist_queue(
            db,
            specialist_id=specialist_id,
            current_user=current_user,
        )
        queue_date = None
        if target_date:
            from datetime import datetime

            queue_date = datetime.strptime(target_date, "%Y-%m-%d").date()

        # Вызываем пациента (синхронно, так как QRQueueService работает с синхронной сессией)
        from fastapi.concurrency import run_in_threadpool
        result = await run_in_threadpool(
            service.call_next_patient, specialist_id, current_user.id, queue_date
        )

        # --- Notification Logic ---
        if result.get("success") and result.get("patient") and result["patient"].get("id"):
            entry_id = result["patient"]["id"]

            # 1. User Notification (Mobile/PWA)
            try:
                from app.models.online_queue import OnlineQueueEntry
                from app.services.queue_position_notifications import (
                    get_queue_position_service,
                )

                # Re-fetch entry to ensure attached to session if needed, or use ID
                # Actually notify_patient_called needs entry object
                notify_service = get_queue_position_service(db)
                entry = db.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).first()

                if entry:
                    # Determine cabinet (optional)
                    cabinet = None
                    if entry.queue and entry.queue.cabinet_number:
                        cabinet = entry.queue.cabinet_number
                    elif entry.queue and entry.queue.specialist: # Fallback to doctor's cabinet
                        cabinet = entry.queue.specialist.cabinet

                    await notify_service.notify_patient_called(entry, cabinet_number=cabinet)
            except Exception as e:
                logger.warning(f"Failed to send user notification for entry {entry_id}: {e}")

            # 2. Display Board Notification (TV)
            try:
                from app.services.display_websocket import get_display_manager

                manager = get_display_manager()

                # Fetch fresh entry or use existing
                if not entry: # Should have been fetched above
                     entry = db.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).first()

                if entry:
                    specialist_name = (
                        entry.queue.specialist.user.full_name
                        if entry.queue.specialist and entry.queue.specialist.user
                        else "Врач"
                    )

                    await manager.broadcast_patient_call(
                        queue_entry=entry,
                        doctor_name=specialist_name,
                        cabinet=entry.queue.cabinet_number  # Pass cabinet if available
                    )
            except Exception as e:
                logger.warning(f"Failed to update display for entry {entry_id}: {e}")

            # UX Audit Stage 3 (Queue WebSocket):
            # Broadcast to /ws/queue admin panel subscribers (instant update
            # instead of 30s polling). Room: specialist_{id}::{date}.
            try:
                from app.ws.queue_ws import broadcast_queue_update

                queue_date_str = queue_date.strftime("%Y-%m-%d") if queue_date else ""
                broadcast_queue_update(
                    department=f"specialist_{specialist_id}",
                    date=queue_date_str,
                    event_type="queue_update",
                    data={"action": "call_next", "entry_id": entry_id},
                )
            except Exception as e:
                logger.warning(f"Failed to broadcast queue WS update for entry {entry_id}: {e}")
        # --------------------------

        return CallNextPatientResponse(**result)

    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Internal server error")
    except Exception as e:
        logger.error(
            "Error calling next patient",
            extra={"error_class": e.__class__.__name__},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка вызова пациента",
        )


