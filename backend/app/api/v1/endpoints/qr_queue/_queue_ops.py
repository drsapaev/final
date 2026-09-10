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

            # QF-1 (REST/GQL audit parity): QRQueueService.call_next_patient
            # has already COMMITTED the waiting->called transition (and, since
            # QF-1, the called_by_user_id column). Mirror the GraphQL path:
            # the row-level critical audit is best-effort AFTER the committed
            # transition (Codex round-7 P1 added online_queue_entries to
            # CRITICAL_TABLES; round-15: an audit failure must not return 5xx
            # — a client retry would call a SECOND patient while the first
            # stays durably called).
            try:
                from app.core.audit import log_critical_change

                log_critical_change(
                    db=db,
                    user_id=current_user.id,
                    action="CALL_NEXT",
                    table_name="online_queue_entries",
                    row_id=entry_id,
                    old_data={"status": "waiting"},
                    new_data={
                        "status": "called",
                        "called_by_user_id": current_user.id,
                    },
                    request=None,
                    description=(
                        "Вызов следующего пациента "
                        "(REST POST /queue/{specialist_id}/call-next)"
                    ),
                )
                db.commit()
            except Exception as audit_exc:  # noqa: BLE001 — non-fatal by design
                logger.warning(
                    "REST call-next: critical audit failed after committed "
                    "call (transition preserved): %s",
                    audit_exc,
                )
                db.rollback()

            # Codex round-25 P2: entry инициализируется ДО независимых
            # side-effect-блоков — если блок уведомлений падает ДО своего
            # присваивания (импорт/get_queue_position_service/запрос), WS-
            # broadcast ловил UnboundLocalError и молча пропускал обновление,
            # включая fallback-комнату вызвавшего.
            entry = None

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
                    # QD-2C (Codex round-13 P2): resource/bridged очередь —
                    # кабинет уведомления с оси ресурса (реестр), как в
                    # QR-метаданных (round-12): queue.cabinet_number, затем
                    # default_cabinet реестра, НЕ кабинет отсутствующего
                    # специалиста
                    cabinet = None
                    if entry.queue and entry.queue.cabinet_number:
                        cabinet = entry.queue.cabinet_number
                    elif (
                        entry.queue
                        and entry.queue.queue_resource_id is not None
                        and entry.queue.queue_resource is not None
                    ):
                        cabinet = entry.queue.queue_resource.default_cabinet
                    elif (
                        entry.queue and entry.queue.specialist
                    ):  # Fallback to doctor's cabinet
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
                    # QD-2C (Codex round-13 P2): resource/bridged очередь —
                    # владелец объявления с оси ресурса (реестр), как
                    # display и legacy call пути (round-11/12); иначе табло
                    # говорит «Врач» без кабинета при живом реестровом
                    # назначении
                    queue = entry.queue
                    if queue.queue_resource_id is not None:
                        resource = queue.queue_resource
                        specialist_name = (
                            resource.display_name
                            if resource is not None
                            else "Ресурс очереди"
                        )
                        broadcast_cabinet = queue.cabinet_number or (
                            resource.default_cabinet if resource is not None else None
                        )
                    else:
                        specialist_name = (
                            queue.specialist.user.full_name
                            if queue.specialist and queue.specialist.user
                            else "Врач"
                        )
                        broadcast_cabinet = (
                            queue.cabinet_number
                        )  # Pass cabinet if available

                    await manager.broadcast_patient_call(
                        queue_entry=entry,
                        doctor_name=specialist_name,
                        cabinet=broadcast_cabinet,
                    )
            except Exception as e:
                logger.warning(f"Failed to update display for entry {entry_id}: {e}")

            # UX Audit Stage 3 (Queue WebSocket):
            # Broadcast to /ws/queue admin panel subscribers (instant update
            # instead of 30s polling). Room: specialist_{id}::{date}.
            try:
                from app.ws.queue_ws import (
                    broadcast_queue_update,
                    queue_update_departments,
                )

                # Codex round-26 P2: дата broadcast'а — день ВЫБРАННОЙ
                # очереди (entry.queue.day), а не опциональный параметр:
                # при опущенном target_date сервис резолвит clinic_today,
                # а queue_date здесь оставался None — пустая дата в
                # комнате (specialist_X:: вместо specialist_X::{дата},
                # useQueueWebSocket подписан на полную форму).
                broadcast_day = (
                    entry.queue.day
                    if entry is not None and entry.queue is not None
                    else queue_date
                )
                queue_date_str = (
                    broadcast_day.strftime("%Y-%m-%d") if broadcast_day else ""
                )
                # QD-2C (Codex round-24 P2): комната — маршрутизирующая
                # идентичность ВЫБРАННОЙ очереди: resource-очередь
                # адресуема через ЛЮБОЙ same-specialty doctor id (менеджеры
                # подписаны на свой выбранный id) — call_next достигает
                # КАЖДУЮ routing-комнату, как join/restore/no-show
                # (round-18/22). Doctor-очереди — легаси-комната
                # байт-идентично; без entry (патологический случай) — прежняя
                # комната вызвавшего.
                call_rooms = (
                    queue_update_departments(db, entry.queue)
                    if entry is not None
                    else [f"specialist_{specialist_id}"]
                )
                for _dept in call_rooms:
                    broadcast_queue_update(
                        department=_dept,
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


