"""
API endpoints для системы сообщений между пользователями
"""

import os
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.message import (
    ConversationListResponse,
    MessageCreate,
    MessageListResponse,
    MessageOut,
    MessageReactionCreate,
    UnreadCountResponse,
)
from app.services.messages_api_service import MessagesApiService

router = APIRouter()


@router.post("/send", response_model=MessageOut)
async def send_message(
    request: Request,
    message_data: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = MessagesApiService(db)
    return await service.send_message(
        request=request,
        message_data=message_data,
        current_user=current_user,
    )


@router.get("/conversations", response_model=ConversationListResponse)
async def get_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payload = MessagesApiService(db).get_conversations(user_id=current_user.id)
    return ConversationListResponse(**payload)


@router.get("/conversation/{user_id}", response_model=MessageListResponse)
async def get_conversation(
    user_id: int,
    skip: int = Query(0, ge=0, description="Пропустить N сообщений"),
    limit: int = Query(50, ge=1, le=100, description="Лимит сообщений"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payload = await MessagesApiService(db).get_conversation(
        user_id=user_id,
        skip=skip,
        limit=limit,
        current_user=current_user,
    )
    return MessageListResponse(**payload)


@router.get("/unread", response_model=UnreadCountResponse)
async def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count = MessagesApiService(db).get_unread_count(user_id=current_user.id)
    return UnreadCountResponse(unread_count=count)


@router.patch("/{message_id}/read", response_model=MessageOut)
async def mark_message_read(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = MessagesApiService(db)
    message = service.mark_message_read(message_id=message_id, user_id=current_user.id)
    if not message:
        raise HTTPException(status_code=404, detail="Сообщение не найдено или нет доступа")
    return service.enrich_message(message)


@router.delete("/{message_id}")
async def delete_message(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await MessagesApiService(db).delete_message(
        message_id=message_id,
        user_id=current_user.id,
    )


@router.post("/{message_id}/reactions", response_model=MessageOut)
async def toggle_message_reaction(
    message_id: int,
    reaction_data: MessageReactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await MessagesApiService(db).toggle_message_reaction(
        message_id=message_id,
        reaction=reaction_data.reaction,
        current_user=current_user,
    )


@router.get("/users/available")
async def get_available_users(
    search: str = Query("", description="Поиск по имени"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return MessagesApiService(db).get_available_users(search=search, current_user=current_user)


@router.post("/send-voice", response_model=MessageOut)
async def send_voice_message(
    request: Request,
    recipient_id: int = Form(...),
    audio_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await MessagesApiService(db).send_voice_message(
        recipient_id=recipient_id,
        audio_file=audio_file,
        current_user=current_user,
    )


@router.get("/voice/{message_id}/stream")
async def stream_voice_message(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payload = MessagesApiService(db).stream_voice_message(
        message_id=message_id,
        current_user=current_user,
    )
    return FileResponse(
        payload["path"],
        media_type=payload["media_type"],
        headers={
            "Accept-Ranges": "bytes",
            "Content-Disposition": f'inline; filename="{payload["content_disposition_filename"]}"',
        },
    )


@router.post("/upload")
async def upload_file_message(
    recipient_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await MessagesApiService(db).upload_file_message(
            recipient_id=recipient_id,
            file=file,
            current_user=current_user,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/download/{filename}")
async def download_chat_file(
    filename: str,
    name: str = Query(None),
    current_user: User = Depends(get_current_user),
):
    file_path = os.path.join("uploads/chat", filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Файл не найден")
    return FileResponse(path=file_path, filename=name or filename)
