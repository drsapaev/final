"""
AI Chat Endpoints - REST и WebSocket API для AI чата.

Функции:
- REST API для управления сессиями
- WebSocket для real-time streaming
"""

import asyncio
import logging
from contextlib import suppress
from typing import Any, Literal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
)
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.v1.endpoints.ws_token import accept_echoing_subprotocol, extract_ws_token
from app.core.config import settings
from app.core.messaging_contract import CONTRACT_VERSION
from app.core.rbac import AIPermission, has_permission, require_ai_permission
from app.models.user import User
from app.services.ai.chat_service import get_chat_service
from app.services.ai_chat_api_service import AIChatApiDomainError, AIChatApiService
from app.services.ai_feature_gating import RequireAiFeature
from app.ws.chat_ws import close_revoked_websocket, monitor_websocket_authorization

logger = logging.getLogger(__name__)

router = APIRouter()


def _required_doctor_confirmation() -> dict[str, bool]:
    """Server-owned policy: AI output is a suggestion requiring a clinician."""
    return {"requires_doctor_confirmation": True}


def _build_ai_ws_payload(event_type: str, session_id: int | None = None, **data: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": event_type,
        "contract_version": CONTRACT_VERSION,
    }
    if session_id is not None:
        payload["session_id"] = session_id
    payload.update(data)
    # Medical content is streamed in multiple independently consumable frames.
    # Each frame carries the server-owned safety boundary, never caller data.
    if event_type in {"chunk", "done", "error"}:
        payload["ai_safety_meta"] = _required_doctor_confirmation()
    return payload


# =============================================================================
# Pydantic Schemas
# =============================================================================

class ChatSessionCreate(BaseModel):
    """Создание новой сессии"""
    context_type: str | None = Field(None, description="emr, lab, general, triage")
    context_id: int | None = Field(None, description="ID связанной сущности")
    specialty: str | None = Field(None, description="Специализация для персонализации")


class ChatSessionResponse(BaseModel):
    """Ответ с информацией о сессии"""
    id: int
    title: str | None
    context_type: str | None
    specialty: str | None
    is_active: bool
    message_count: int
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)


class ChatMessageCreate(BaseModel):
    """Отправка сообщения"""
    content: str = Field(..., min_length=1, max_length=10000)
    include_history: bool = Field(True, description="Включить контекст истории")


class AIChatSafetyMeta(BaseModel):
    """A strict, explicit clinical boundary for each AI chat message."""

    requires_doctor_confirmation: Literal[True]

    @field_validator("requires_doctor_confirmation", mode="before")
    @classmethod
    def require_boolean_true(cls, value: object) -> object:
        # Literal[True] alone accepts integer 1 because bool subclasses int.
        if value is not True:
            raise ValueError("AI output must require doctor confirmation")
        return value


class ChatMessageResponse(BaseModel):
    """Ответ с сообщением"""
    id: int
    role: str
    content: str
    provider: str | None
    model: str | None
    tokens_used: int | None
    latency_ms: int | None
    is_error: bool
    was_cached: bool
    created_at: str
    ai_safety_meta: AIChatSafetyMeta

    model_config = ConfigDict(from_attributes=True)


class ChatFeedbackCreate(BaseModel):
    """Feedback на сообщение AI"""
    feedback_type: str = Field(..., description="helpful, not_helpful, incorrect, inappropriate")
    comment: str | None = Field(None, max_length=1000)
    correction: str | None = Field(None, max_length=5000)


# =============================================================================
# REST API Endpoints
# =============================================================================

@router.post("/sessions", response_model=ChatSessionResponse)
async def create_session(
    request: ChatSessionCreate,
    current_user: User = Depends(require_ai_permission(AIPermission.CHAT)),
    db: Session = Depends(get_db)
):
    """
    Создать новую чат-сессию.

    Requires: CHAT permission
    """
    service = get_chat_service(db)

    session = await service.get_or_create_session(
        user_id=current_user.id,
        context_type=request.context_type,
        context_id=request.context_id,
        specialty=request.specialty
    )

    return ChatSessionResponse(
        id=session.id,
        title=session.title,
        context_type=session.context_type,
        specialty=session.specialty,
        is_active=session.is_active,
        message_count=len(session.messages),
        created_at=session.created_at.isoformat(),
        updated_at=session.updated_at.isoformat()
    )


@router.get("/sessions", response_model=list[ChatSessionResponse])
async def list_sessions(
    limit: int = Query(20, ge=1, le=100),
    include_inactive: bool = Query(False),
    current_user: User = Depends(require_ai_permission(AIPermission.CHAT)),
    db: Session = Depends(get_db)
):
    """
    Получить список чат-сессий пользователя.
    """
    service = get_chat_service(db)

    sessions = await service.get_user_sessions(
        user_id=current_user.id,
        limit=limit,
        include_inactive=include_inactive
    )

    return [
        ChatSessionResponse(
            id=s.id,
            title=s.title,
            context_type=s.context_type,
            specialty=s.specialty,
            is_active=s.is_active,
            message_count=len(s.messages),
            created_at=s.created_at.isoformat(),
            updated_at=s.updated_at.isoformat()
        )
        for s in sessions
    ]


@router.get("/sessions/{session_id}", response_model=ChatSessionResponse)
async def get_session(
    session_id: int,
    current_user: User = Depends(require_ai_permission(AIPermission.CHAT)),
    db: Session = Depends(get_db)
):
    """
    Получить информацию о сессии.
    """
    try:
        payload = AIChatApiService(db).get_session_payload(
            session_id=session_id,
            user_id=current_user.id,
        )
        return ChatSessionResponse(**payload)
    except AIChatApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.delete("/sessions/{session_id}", response_model=dict[str, Any])
async def delete_session(
    session_id: int,
    current_user: User = Depends(require_ai_permission(AIPermission.CHAT)),
    db: Session = Depends(get_db)
):
    """
    Удалить сессию и все сообщения.
    """
    service = get_chat_service(db)

    deleted = await service.delete_session(session_id, current_user.id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"message": "Session deleted", "session_id": session_id}


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageResponse])
async def get_messages(
    session_id: int,
    limit: int = Query(50, ge=1, le=200),
    before_id: int | None = Query(None, description="Pagination: get messages before this ID"),
    current_user: User = Depends(require_ai_permission(AIPermission.CHAT)),
    db: Session = Depends(get_db)
):
    """
    Получить историю сообщений сессии.
    """
    try:
        payload = await AIChatApiService(db).get_messages_payload(
            session_id=session_id,
            user_id=current_user.id,
            limit=limit,
            before_id=before_id,
        )
        # Existing persisted history predates this envelope. The added
        # marker declares the current display policy, not prior validation.
        # An explicitly supplied invalid marker is rejected rather than fixed.
        return [
            ChatMessageResponse(**{
                **item,
                "ai_safety_meta": item.get("ai_safety_meta", _required_doctor_confirmation()),
            })
            for item in payload
        ]
    except AIChatApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/sessions/{session_id}/messages", response_model=ChatMessageResponse,
             dependencies=[Depends(RequireAiFeature("ai_chat_assistant"))])
async def send_message(
    session_id: int,
    request: ChatMessageCreate,
    current_user: User = Depends(require_ai_permission(AIPermission.CHAT)),
    db: Session = Depends(get_db)
):
    """
    Отправить сообщение и получить ответ AI.

    Синхронный endpoint (ждет полного ответа).
    Для streaming используйте WebSocket.
    """
    service = get_chat_service(db)

    try:
        response = await service.send_message(
            session_id=session_id,
            user_id=current_user.id,
            content=request.content,
            include_history=request.include_history
        )

        return ChatMessageResponse(
            id=response.id,
            role=response.role,
            content=response.content,
            provider=response.provider,
            model=response.model,
            tokens_used=response.tokens_used,
            latency_ms=response.latency_ms,
            is_error=response.is_error,
            was_cached=response.was_cached,
            created_at=response.created_at.isoformat(),
            ai_safety_meta=getattr(response, "ai_safety_meta", _required_doctor_confirmation()),
        )

    except ValueError:
        raise HTTPException(status_code=404, detail="Internal server error")


@router.post("/messages/{message_id}/feedback", response_model=dict[str, Any])
async def add_feedback(
    message_id: int,
    request: ChatFeedbackCreate,
    current_user: User = Depends(require_ai_permission(AIPermission.CHAT)),
    db: Session = Depends(get_db)
):
    """
    Добавить feedback на сообщение AI.

    Используется для улучшения качества AI.
    """
    try:
        return await AIChatApiService(db).add_feedback_payload(
            message_id=message_id,
            user_id=current_user.id,
            feedback_type=request.feedback_type,
            comment=request.comment,
            correction=request.correction,
        )
    except AIChatApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


# =============================================================================
# WebSocket Endpoint for Streaming
# =============================================================================

async def authenticate_websocket(token: str, db: Session) -> User | None:
    """
    Аутентификация WebSocket по JWT token.
    """
    return await asyncio.to_thread(
        AIChatApiService(db).authenticate_websocket_user,
        token=token, secret_key=settings.SECRET_KEY, algorithm=settings.ALGORITHM,
    )


def _ai_ws_session_is_current(token: str, user_id: int) -> bool:
    """Use a fresh DB session for each periodic reauthorization."""
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        user = AIChatApiService(db).authenticate_websocket_user(
            token=token, secret_key=settings.SECRET_KEY, algorithm=settings.ALGORITHM
        )
        return bool(
            user is not None and user.id == user_id
            and has_permission(user.role, AIPermission.CHAT)
        )
    except Exception:
        return False
    finally:
        db.close()


async def _ai_ws_authorized_or_close(websocket, token: str, user_id: int, revoked, close_lock) -> bool:
    """Revalidate after potentially blocking AI/DB work before sending data."""
    try:
        allowed = await asyncio.wait_for(
            asyncio.to_thread(_ai_ws_session_is_current, token, user_id), timeout=5.0
        )
    except Exception:
        allowed = False
    if not allowed or revoked.is_set():
        await close_revoked_websocket(websocket, revoked, close_lock)
        return False
    return True


class _AIWebSocketRevoked(Exception):
    """Stop handling messages after the watchdog has revoked the socket."""


AI_WS_SEND_TIMEOUT_SECONDS = 2.0


def _ai_ws_safety_valid(payload: object) -> bool:
    """Fail closed if a medical frame lacks the exact boolean safety marker."""
    if not isinstance(payload, dict):
        return False
    event_type = payload.get("type")
    carries_text = "content" in payload or "message" in payload
    if not carries_text and event_type not in ("chunk", "done", "error"):
        return True
    metadata = payload.get("ai_safety_meta")
    return (
        isinstance(metadata, dict)
        and metadata.get("requires_doctor_confirmation") is True
    )


async def _ai_ws_close_unsafe(websocket, revoked, close_lock):
    """Close invalid output without racing a concurrent revocation close."""
    revoked.set()
    async with close_lock:
        if getattr(revoked, "_ws_close_started", False):
            return
        revoked._ws_close_started = True
        try:
            await asyncio.wait_for(
                websocket.close(code=1011, reason="Safety metadata required"),
                timeout=2.0,
            )
        except Exception:
            pass


async def _ai_ws_send(websocket, payload, revoked, close_lock):
    """Serialize each payload with revocation, including every stream chunk."""
    if not _ai_ws_safety_valid(payload):
        logger.error("AI WebSocket output missing required safety metadata")
        await _ai_ws_close_unsafe(websocket, revoked, close_lock)
        raise _AIWebSocketRevoked
    try:
        async with asyncio.timeout(AI_WS_SEND_TIMEOUT_SECONDS):
            async with close_lock:
                if revoked.is_set():
                    raise _AIWebSocketRevoked
                await websocket.send_json(payload)
    except TimeoutError:
        # Release the send lock before acquiring it again to close.
        await close_revoked_websocket(websocket, revoked, close_lock)
        raise _AIWebSocketRevoked from None


@router.websocket("/ws")
async def chat_websocket(
    websocket: WebSocket,
    db: Session = Depends(get_db)
):
    """
    WebSocket для real-time AI чата с streaming.

    PR-4: token is extracted via ``extract_ws_token`` — preferred sources
    are Sec-WebSocket-Protocol subprotocol ``bearer.<jwt>`` and
    Authorization header. Query param ``?token=`` still works but emits
    a deprecation warning (it leaks in proxy logs / Referer).

    Protocol:

    Client -> Server:
    ```json
    {
        "type": "message",
        "session_id": 123,  // Optional, creates new if not provided
        "content": "Привет!",
        "context_type": "general",  // Optional
        "specialty": "cardio"  // Optional
    }
    ```

    Server -> Client (streaming):
    ```json
    {"type": "session", "session_id": 123}
    {"type": "chunk", "content": "Здравст", "ai_safety_meta": {"requires_doctor_confirmation": true}}
    {"type": "chunk", "content": "вуйте!", "ai_safety_meta": {"requires_doctor_confirmation": true}}
    {"type": "done", "message_id": 456, "provider": "deepseek", "tokens": 42, "ai_safety_meta": {"requires_doctor_confirmation": true}}
    ```

    Server -> Client (error):
    ```json
    {"type": "error", "message": "Rate limit exceeded", "ai_safety_meta": {"requires_doctor_confirmation": true}}
    ```
    """
    await accept_echoing_subprotocol(websocket)

    # PR-4: extract JWT from secure sources (subprotocol/header preferred,
    # query string as deprecated fallback).
    token = extract_ws_token(websocket)

    if not token:
        await websocket.close(code=4001, reason="Authentication required")
        return

    # Аутентификация
    user = await authenticate_websocket(token, db)

    if not user:
        await websocket.close(code=4001, reason="Invalid token")
        return

    # Проверка permission
    if not has_permission(user.role, AIPermission.CHAT):
        await websocket.close(code=4003, reason="Permission denied")
        return

    logger.info(f"WebSocket chat connected: user={user.id}")

    current_session_id: int | None = None
    revoked = asyncio.Event()
    close_lock = asyncio.Lock()
    async def send_authorized(payload):
        await _ai_ws_send(websocket, payload, revoked, close_lock)

    owner_task = asyncio.current_task()
    watchdog = asyncio.create_task(
        monitor_websocket_authorization(
            websocket, lambda: _ai_ws_session_is_current(token, user.id), revoked, owner_task, close_lock
        )
    )

    try:
        service = get_chat_service(db)
        async for message in websocket.iter_json():
            if not await _ai_ws_authorized_or_close(websocket, token, user.id, revoked, close_lock):
                return
            msg_type = message.get("type", "message")

            if msg_type == "ping":
                await send_authorized(_build_ai_ws_payload("pong", current_session_id))
                continue

            if msg_type == "message":
                content = message.get("content", "").strip()

                if not content:
                    await send_authorized({
                        **_build_ai_ws_payload("error", current_session_id, message="Empty message")
                    })
                    continue

                # Получаем или создаем сессию
                session_id = message.get("session_id") or current_session_id

                if not session_id:
                    session = await service.get_or_create_session(
                        user_id=user.id,
                        context_type=message.get("context_type"),
                        specialty=message.get("specialty")
                    )
                    session_id = session.id
                    current_session_id = session_id

                    if not await _ai_ws_authorized_or_close(websocket, token, user.id, revoked, close_lock):
                        return
                    await send_authorized({
                        **_build_ai_ws_payload("session", session_id)
                    })

                # Отправляем сообщение
                try:
                    response = await service.send_message(
                        session_id=session_id,
                        user_id=user.id,
                        content=content,
                        include_history=True
                    )

                    if not await _ai_ws_authorized_or_close(websocket, token, user.id, revoked, close_lock):
                        return

                    # FA-008: streaming rate limit — max response length + chunk count
                    MAX_RESPONSE_LENGTH = 8000
                    MAX_CHUNKS = 400
                    chunk_size = 20
                    full_content = response.content[:MAX_RESPONSE_LENGTH]
                    chunks_sent = 0

                    for i in range(0, len(full_content), chunk_size):
                        if chunks_sent >= MAX_CHUNKS:
                            await send_authorized({
                                **_build_ai_ws_payload("truncated", session_id,
                                    reason="max_length_reached")
                            })
                            break
                        chunk = full_content[i:i + chunk_size]
                        await send_authorized({
                            **_build_ai_ws_payload("chunk", session_id, content=chunk)
                        })
                        await asyncio.sleep(0.03)
                        chunks_sent += 1

                    await send_authorized({
                        **_build_ai_ws_payload(
                            "done",
                            session_id,
                            message_id=response.id,
                            provider=response.provider,
                            model=response.model,
                            tokens=response.tokens_used,
                            latency_ms=response.latency_ms,
                            cached=response.was_cached,
                        )
                    })

                except _AIWebSocketRevoked:
                    raise
                except ValueError:
                    if not await _ai_ws_authorized_or_close(websocket, token, user.id, revoked, close_lock):
                        return
                    await send_authorized({
                        **_build_ai_ws_payload("error", session_id, message="Request failed")
                    })
                except Exception as e:
                    logger.error("Chat error: %s", type(e).__name__)
                    if not await _ai_ws_authorized_or_close(websocket, token, user.id, revoked, close_lock):
                        return
                    await send_authorized({
                        **_build_ai_ws_payload("error", session_id, message="Internal error occurred")
                    })

            elif msg_type == "close_session":
                if current_session_id:
                    await service.close_session(current_session_id, user.id)
                    if not await _ai_ws_authorized_or_close(websocket, token, user.id, revoked, close_lock):
                        return
                    await send_authorized({
                        **_build_ai_ws_payload("session_closed", current_session_id)
                    })
                    current_session_id = None

    except _AIWebSocketRevoked:
        pass
    except WebSocketDisconnect:
        logger.info(f"WebSocket chat disconnected: user={user.id}")
    except asyncio.CancelledError:
        if not revoked.is_set():
            raise
    except Exception as e:
        logger.error("WebSocket error: %s", type(e).__name__)
        try:
            # AI-REAUDIT-28 P1-11: не泄露 exception в close reason.
            await websocket.close(code=1011, reason="Internal server error")
        except Exception:
            pass
    finally:
        watchdog.cancel()
        with suppress(asyncio.CancelledError):
            await watchdog
