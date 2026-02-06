"""
AI Chat Endpoints - REST и WebSocket API для AI чата.

Функции:
- REST API для управления сессиями
- WebSocket для real-time streaming
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.core.rbac import AIPermission, require_ai_permission, has_permission
from app.models.user import User
from app.models.ai_chat import AIChatSession, AIChatMessage
from app.services.ai.chat_service import get_chat_service

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# Pydantic Schemas
# =============================================================================

class ChatSessionCreate(BaseModel):
    """Создание новой сессии"""
    context_type: Optional[str] = Field(None, description="emr, lab, general, triage")
    context_id: Optional[int] = Field(None, description="ID связанной сущности")
    specialty: Optional[str] = Field(None, description="Специализация для персонализации")


class ChatSessionResponse(BaseModel):
    """Ответ с информацией о сессии"""
    id: int
    title: Optional[str]
    context_type: Optional[str]
    specialty: Optional[str]
    is_active: bool
    message_count: int
    created_at: str
    updated_at: str
    
    class Config:
        from_attributes = True


class ChatMessageCreate(BaseModel):
    """Отправка сообщения"""
    content: str = Field(..., min_length=1, max_length=10000)
    include_history: bool = Field(True, description="Включить контекст истории")


class ChatMessageResponse(BaseModel):
    """Ответ с сообщением"""
    id: int
    role: str
    content: str
    provider: Optional[str]
    model: Optional[str]
    tokens_used: Optional[int]
    latency_ms: Optional[int]
    is_error: bool
    was_cached: bool
    created_at: str
    
    class Config:
        from_attributes = True


class ChatFeedbackCreate(BaseModel):
    """Feedback на сообщение AI"""
    feedback_type: str = Field(..., description="helpful, not_helpful, incorrect, inappropriate")
    comment: Optional[str] = Field(None, max_length=1000)
    correction: Optional[str] = Field(None, max_length=5000)


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


@router.get("/sessions", response_model=List[ChatSessionResponse])
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
    session = db.query(AIChatSession).filter(
        AIChatSession.id == session_id,
        AIChatSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
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


@router.delete("/sessions/{session_id}")
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


@router.get("/sessions/{session_id}/messages", response_model=List[ChatMessageResponse])
async def get_messages(
    session_id: int,
    limit: int = Query(50, ge=1, le=200),
    before_id: Optional[int] = Query(None, description="Pagination: get messages before this ID"),
    current_user: User = Depends(require_ai_permission(AIPermission.CHAT)),
    db: Session = Depends(get_db)
):
    """
    Получить историю сообщений сессии.
    """
    # Проверяем доступ
    session = db.query(AIChatSession).filter(
        AIChatSession.id == session_id,
        AIChatSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    service = get_chat_service(db)
    messages = await service.get_history(session_id, limit=limit, before_id=before_id)
    
    return [
        ChatMessageResponse(
            id=m.id,
            role=m.role,
            content=m.content,
            provider=m.provider,
            model=m.model,
            tokens_used=m.tokens_used,
            latency_ms=m.latency_ms,
            is_error=m.is_error,
            was_cached=m.was_cached,
            created_at=m.created_at.isoformat()
        )
        for m in messages
    ]


@router.post("/sessions/{session_id}/messages", response_model=ChatMessageResponse)
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
            created_at=response.created_at.isoformat()
        )
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/messages/{message_id}/feedback")
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
    # Проверяем что сообщение принадлежит пользователю
    message = db.query(AIChatMessage).join(AIChatSession).filter(
        AIChatMessage.id == message_id,
        AIChatSession.user_id == current_user.id
    ).first()
    
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    service = get_chat_service(db)
    
    try:
        feedback = await service.add_feedback(
            message_id=message_id,
            user_id=current_user.id,
            feedback_type=request.feedback_type,
            comment=request.comment,
            correction=request.correction
        )
        
        return {
            "message": "Feedback recorded",
            "feedback_id": feedback.id,
            "feedback_type": feedback.feedback_type
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# WebSocket Endpoint for Streaming
# =============================================================================

async def authenticate_websocket(token: str, db: Session) -> Optional[User]:
    """
    Аутентификация WebSocket по JWT token.
    """
    from jose import JWTError, jwt
    from app.core.config import settings
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: int = payload.get("sub")
        
        if user_id is None:
            return None
        
        user = db.query(User).filter(User.id == user_id).first()
        return user
        
    except JWTError:
        return None


@router.websocket("/ws")
async def chat_websocket(
    websocket: WebSocket,
    token: str = Query(..., description="JWT token for authentication"),
    db: Session = Depends(get_db)
):
    """
    WebSocket для real-time AI чата с streaming.
    
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
    {"type": "chunk", "content": "Здравст"}
    {"type": "chunk", "content": "вуйте!"}
    {"type": "done", "message_id": 456, "provider": "deepseek", "tokens": 42}
    ```
    
    Server -> Client (error):
    ```json
    {"type": "error", "message": "Rate limit exceeded"}
    ```
    """
    await websocket.accept()
    
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
    
    service = get_chat_service(db)
    current_session_id: Optional[int] = None
    
    try:
        async for message in websocket.iter_json():
            msg_type = message.get("type", "message")
            
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue
            
            if msg_type == "message":
                content = message.get("content", "").strip()
                
                if not content:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Empty message"
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
                    
                    await websocket.send_json({
                        "type": "session",
                        "session_id": session_id
                    })
                
                # Отправляем сообщение
                try:
                    response = await service.send_message(
                        session_id=session_id,
                        user_id=user.id,
                        content=content,
                        include_history=True
                    )
                    
                    # Симулируем streaming (отправляем по частям)
                    # TODO: Реализовать настоящий streaming когда провайдеры поддержат
                    chunk_size = 20
                    full_content = response.content
                    
                    for i in range(0, len(full_content), chunk_size):
                        chunk = full_content[i:i + chunk_size]
                        await websocket.send_json({
                            "type": "chunk",
                            "content": chunk
                        })
                        await asyncio.sleep(0.03)  # Небольшая задержка для эффекта typing
                    
                    await websocket.send_json({
                        "type": "done",
                        "message_id": response.id,
                        "provider": response.provider,
                        "model": response.model,
                        "tokens": response.tokens_used,
                        "latency_ms": response.latency_ms,
                        "cached": response.was_cached
                    })
                    
                except ValueError as e:
                    await websocket.send_json({
                        "type": "error",
                        "message": str(e)
                    })
                except Exception as e:
                    logger.exception(f"Chat error: {e}")
                    await websocket.send_json({
                        "type": "error",
                        "message": "Internal error occurred"
                    })
            
            elif msg_type == "close_session":
                if current_session_id:
                    await service.close_session(current_session_id, user.id)
                    await websocket.send_json({
                        "type": "session_closed",
                        "session_id": current_session_id
                    })
                    current_session_id = None
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket chat disconnected: user={user.id}")
    except Exception as e:
        logger.exception(f"WebSocket error: {e}")
        try:
            await websocket.close(code=1011, reason=str(e))
        except:
            pass
