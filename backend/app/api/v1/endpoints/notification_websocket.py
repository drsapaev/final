
import logging
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, status
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.api.v1.endpoints.websocket_auth import authenticate_websocket_token
from app.services.notification_websocket import get_notification_ws_manager

logger = logging.getLogger(__name__)

router = APIRouter()

@router.websocket("/ws/notifications/connect")
async def websocket_notifications(
    websocket: WebSocket,
    token: str = Query(..., description="JWT Token"),
):
    """
    WebSocket endpoint for real-time user notifications.
    Clients connect here to receive updates about:
    - Queue position changes
    - Appointment reminders
    - Payment confirmations
    - System alerts
    """
    db = SessionLocal()
    manager = get_notification_ws_manager()
    authenticated_user = None

    try:
        # Authenticate
        authenticated_user = await authenticate_websocket_token(token, db)
        if not authenticated_user:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
            return

        # Connect
        await manager.connect(websocket, authenticated_user.id)
        
        # Send welcome/initial state if needed
        await websocket.send_json({
            "type": "connection_established",
            "message": f"Connected as {authenticated_user.username}",
            "user_id": authenticated_user.id
        })

        # Keep connection alive
        try:
            while True:
                # We can handle client messages here if needed (e.g. read receipts)
                # For now, we just receive to keep the loop open and detect disconnects
                data = await websocket.receive_text()
                # If we implement interactive notifications, handle 'data' here
                
        except WebSocketDisconnect:
            if authenticated_user:
                manager.disconnect(websocket, authenticated_user.id)
                
    except Exception as e:
        logger.error(f"WebSocket notification error: {e}")
        try:
             await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except:
             pass
    finally:
        db.close()
