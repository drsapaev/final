from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from app.api.v1.endpoints.websocket_auth import authenticate_websocket_token
from app.db.session import SessionLocal
from app.services.notification_platform_service import get_notification_platform_service
from app.services.notification_websocket import get_notification_ws_manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/notifications/connect")
async def websocket_notifications(
    websocket: WebSocket,
    # P1-6: accept token from query param OR Sec-WebSocket-Protocol subprotocol
    token: str | None = Query(None, description="JWT token (legacy, use subprotocol)"),
):
    """Realtime notification channel with server-owned inbox sync."""
    db = SessionLocal()
    manager = get_notification_ws_manager()
    authenticated_user = None

    try:
        authenticated_user = await authenticate_websocket_token(token, db)
        if not authenticated_user:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token"
            )
            return

        await manager.connect(websocket, authenticated_user.id)

        platform_service = get_notification_platform_service(db)
        unread_counts = platform_service.get_unread_counts(current_user=authenticated_user)
        panel_role = platform_service.resolve_panel_role_for_user(authenticated_user)

        await websocket.send_json(
            {
                "type": "connection_established",
                "message": f"Connected as {authenticated_user.username}",
                "user_id": authenticated_user.id,
                "role": panel_role,
                "unread_count": unread_counts["total"],
                "cursor": None,
            }
        )

        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                logger.warning(
                    "[NotificationWS] ignored non-JSON client message",
                    extra={"user_id": authenticated_user.id},
                )
                continue

            message_type = str(payload.get("type") or "").lower()
            delivery_id = payload.get("delivery_id")

            if message_type == "notification_seen" and delivery_id:
                try:
                    delivery = await platform_service.mark_seen(
                        current_user=authenticated_user, delivery_id=delivery_id
                    )
                    unread_counts = platform_service.get_unread_counts(
                        current_user=authenticated_user
                    )
                    await websocket.send_json(
                        {
                            "type": "notification_seen_ack",
                            "delivery_id": delivery.delivery_id,
                            "delivery_status": delivery.delivery_status,
                            "unread_count": unread_counts["total"],
                        }
                    )
                except PermissionError:
                    await websocket.send_json(
                        {
                            "type": "notification_error",
                            "delivery_id": delivery_id,
                            "message": "Уведомление не найдено",
                        }
                    )
                continue

            if message_type == "notification_read" and delivery_id:
                try:
                    delivery = await platform_service.mark_read(
                        current_user=authenticated_user, delivery_id=delivery_id
                    )
                    unread_counts = platform_service.get_unread_counts(
                        current_user=authenticated_user
                    )
                    await websocket.send_json(
                        {
                            "type": "notification_read_ack",
                            "delivery_id": delivery.delivery_id,
                            "delivery_status": delivery.delivery_status,
                            "unread_count": unread_counts["total"],
                        }
                    )
                except PermissionError:
                    await websocket.send_json(
                        {
                            "type": "notification_error",
                            "delivery_id": delivery_id,
                            "message": "Уведомление не найдено",
                        }
                    )
                continue

            if message_type == "notification_archive" and delivery_id:
                try:
                    delivery = await platform_service.archive(
                        current_user=authenticated_user, delivery_id=delivery_id
                    )
                    unread_counts = platform_service.get_unread_counts(
                        current_user=authenticated_user
                    )
                    await websocket.send_json(
                        {
                            "type": "notification_archive_ack",
                            "delivery_id": delivery.delivery_id,
                            "delivery_status": delivery.delivery_status,
                            "unread_count": unread_counts["total"],
                        }
                    )
                except PermissionError:
                    await websocket.send_json(
                        {
                            "type": "notification_error",
                            "delivery_id": delivery_id,
                            "message": "Уведомление не найдено",
                        }
                    )
                continue

            if message_type == "notification_mark_all_read":
                count = await platform_service.mark_all_read(
                    current_user=authenticated_user,
                    role=payload.get("role"),
                    department_key=payload.get("department_key"),
                )
                unread_counts = platform_service.get_unread_counts(
                    current_user=authenticated_user
                )
                await websocket.send_json(
                    {
                        "type": "notification_mark_all_read_ack",
                        "count": count,
                        "unread_count": unread_counts["total"],
                    }
                )
                continue

            if message_type == "notification_sync":
                cursor_value = payload.get("cursor")
                try:
                    cursor_value = int(cursor_value) if cursor_value is not None else None
                except (TypeError, ValueError):
                    cursor_value = None
                sync_payload = platform_service.get_inbox(
                    current_user=authenticated_user,
                    role=payload.get("role"),
                    status=payload.get("status", "all"),
                    event_type=payload.get("event_type"),
                    severity=payload.get("severity"),
                    department_key=payload.get("department_key"),
                    search=payload.get("search"),
                    cursor=cursor_value,
                    limit=int(payload.get("limit") or 50),
                )
                await websocket.send_json(
                    {
                        "type": "notification_sync_response",
                        **sync_payload,
                    }
                )
                continue

    except WebSocketDisconnect:
        if authenticated_user:
            manager.disconnect(websocket, authenticated_user.id)
    except Exception as exc:
        logger.error("WebSocket notification error: %s", exc)
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except Exception:
            pass
    finally:
        db.close()
