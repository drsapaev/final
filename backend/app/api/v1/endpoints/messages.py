"""
API endpoints для системы сообщений между пользователями
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Form, File, UploadFile
from fastapi.responses import FileResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
import logging
import asyncio
import os
import hashlib
from datetime import datetime

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.crud.message import message as message_crud
from app.schemas.message import (
    MessageCreate, 
    MessageOut, 
    ConversationOut,
    MessageListResponse,
    ConversationListResponse,
    UnreadCountResponse
)

logger = logging.getLogger(__name__)

router = APIRouter()


# Правила доступа: кто может писать кому
MESSAGING_PERMISSIONS = {
    # Админы могут писать всем
    "Admin": ["Admin", "Doctor", "Registrar", "Cashier", "Lab", "Patient", 
              "cardio", "derma", "dentist"],
    
    # Врачи могут писать пациентам и персоналу
    "Doctor": ["Admin", "Doctor", "Registrar", "Cashier", "Lab", "Patient",
               "cardio", "derma", "dentist"],
    "cardio": ["Admin", "Doctor", "Registrar", "Cashier", "Lab", "Patient",
               "cardio", "derma", "dentist"],
    "derma": ["Admin", "Doctor", "Registrar", "Cashier", "Lab", "Patient",
              "cardio", "derma", "dentist"],
    "dentist": ["Admin", "Doctor", "Registrar", "Cashier", "Lab", "Patient",
                "cardio", "derma", "dentist"],
    
    # Регистраторы могут писать персоналу и пациентам
    "Registrar": ["Admin", "Doctor", "Registrar", "Cashier", "Lab", "Patient",
                  "cardio", "derma", "dentist"],
    
    # Кассиры и лаборанты - персоналу
    "Cashier": ["Admin", "Doctor", "Registrar", "Cashier", "Lab",
                "cardio", "derma", "dentist"],
    "Lab": ["Admin", "Doctor", "Registrar", "Cashier", "Lab",
            "cardio", "derma", "dentist"],
    
    # Пациенты могут писать врачам, админам и регистраторам
    "Patient": ["Admin", "Doctor", "Registrar", "cardio", "derma", "dentist"],
}


def can_send_message(sender_role: str, recipient_role: str) -> bool:
    """Проверить, может ли отправитель писать получателю"""
    allowed_recipients = MESSAGING_PERMISSIONS.get(sender_role, [])
    return recipient_role in allowed_recipients


def enrich_message(msg, db: Session) -> MessageOut:
    """Добавить информацию об отправителе и получателе к сообщению"""
    sender = db.query(User).filter(User.id == msg.sender_id).first()
    recipient = db.query(User).filter(User.id == msg.recipient_id).first()
    
    # Для голосовых сообщений - добавить URL файла
    file_url = None
    if msg.message_type == "voice" and msg.file_id:
        file_url = f"/api/v1/messages/voice/{msg.id}/stream"
    
    # Name resolution helper
    def get_name(u):
        if not u: return None
        return u.full_name or u.username or u.email
    
    return MessageOut(
        id=msg.id,
        sender_id=msg.sender_id,
        recipient_id=msg.recipient_id,
        message_type=msg.message_type,
        content=msg.content,
        is_read=msg.is_read,
        created_at=msg.created_at,
        read_at=msg.read_at,
        file_id=msg.file_id,
        voice_duration=msg.voice_duration,
        file_url=file_url,
        sender_name=get_name(sender),
        sender_role=sender.role if sender else None,
        recipient_name=get_name(recipient),
        recipient_role=recipient.role if recipient else None
    )


@router.post("/send", response_model=MessageOut)
async def send_message(
    request: Request,
    message_data: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Отправить сообщение пользователю.
    
    Правила доступа:
    - Админы могут писать всем
    - Врачи могут писать пациентам и персоналу
    - Пациенты могут писать врачам, админам и регистраторам
    - Персонал может писать между собой
    """
    
    # Проверка: нельзя писать самому себе
    if message_data.recipient_id == current_user.id:
        raise HTTPException(
            status_code=400, 
            detail="Нельзя отправить сообщение самому себе"
        )
    
    # Проверка: получатель существует
    recipient = db.query(User).filter(User.id == message_data.recipient_id).first()
    if not recipient:
        raise HTTPException(
            status_code=404, 
            detail="Пользователь не найден"
        )
    
    # Проверка прав доступа
    sender_role = current_user.role or "Patient"
    recipient_role = recipient.role or "Patient"
    
    if not can_send_message(sender_role, recipient_role):
        raise HTTPException(
            status_code=403, 
            detail="Нет прав для отправки сообщения этому пользователю"
        )
    
    # Создаём сообщение
    new_message = message_crud.create(
        db, 
        sender_id=current_user.id, 
        obj_in=message_data
    )
    
    # Отправить уведомление через WebSocket получателю
    from app.ws.chat_ws import chat_manager
    enriched_message = enrich_message(new_message, db)
    
    # Асинхронно отправляем уведомление (если получатель онлайн)
    import asyncio
    try:
        logger.info(f"Initiating WS notification for recipient {recipient.id}")
        asyncio.create_task(
            chat_manager.notify_new_message(
                recipient_id=recipient.id,
                message_data=enriched_message.dict()
            )
        )
        
        # Также уведомляем отправителя для синхронизации других вкладок/устройств
        asyncio.create_task(
            chat_manager.notify_new_message(
                recipient_id=current_user.id,
                message_data=enriched_message.dict()
            )
        )
    except Exception as e:
        logger.warning(f"Failed to send WebSocket notification: {e}")
    
    return enriched_message


@router.get("/conversations", response_model=ConversationListResponse)
async def get_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить список всех бесед текущего пользователя"""
    conversations = message_crud.get_conversations_list(db, user_id=current_user.id)
    total_unread = message_crud.get_unread_count(db, user_id=current_user.id)
    
    return ConversationListResponse(
        conversations=[ConversationOut(**conv) for conv in conversations],
        total_unread=total_unread
    )


@router.get("/conversation/{user_id}", response_model=MessageListResponse)
async def get_conversation(
    user_id: int,
    skip: int = Query(0, ge=0, description="Пропустить N сообщений"),
    limit: int = Query(50, ge=1, le=100, description="Лимит сообщений"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить переписку с конкретным пользователем.
    
    Автоматически помечает сообщения как прочитанные.
    """
    
    # Проверка: пользователь существует
    other_user = db.query(User).filter(User.id == user_id).first()
    if not other_user:
        raise HTTPException(
            status_code=404, 
            detail="Пользователь не найден"
        )
    
    # Получаем сообщения
    messages, total = message_crud.get_conversation(
        db, 
        user1_id=current_user.id, 
        user2_id=user_id,
        skip=skip,
        limit=limit
    )
    
    # Помечаем как прочитанные
    message_crud.mark_conversation_as_read(
        db, 
        user_id=current_user.id, 
        other_user_id=user_id
    )
    
    return MessageListResponse(
        messages=[enrich_message(m, db) for m in messages],
        total=total,
        has_more=skip + limit < total
    )


@router.get("/unread", response_model=UnreadCountResponse)
async def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить количество непрочитанных сообщений"""
    count = message_crud.get_unread_count(db, user_id=current_user.id)
    return UnreadCountResponse(unread_count=count)


@router.patch("/{message_id}/read", response_model=MessageOut)
async def mark_message_read(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Пометить конкретное сообщение как прочитанное"""
    message = message_crud.mark_as_read(
        db, 
        message_id=message_id, 
        user_id=current_user.id
    )
    
    if not message:
        raise HTTPException(
            status_code=404, 
            detail="Сообщение не найдено или нет доступа"
        )
    
    return enrich_message(message, db)


@router.delete("/{message_id}")
async def delete_message(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Удалить сообщение (мягкое удаление).
    
    Сообщение удаляется только для текущего пользователя,
    у собеседника остаётся видимым.
    """
    success = message_crud.delete_for_user(
        db, 
        message_id=message_id, 
        user_id=current_user.id
    )
    
    if not success:
        raise HTTPException(
            status_code=404, 
            detail="Сообщение не найдено или нет доступа"
        )
    
    return {"success": True, "message": "Сообщение удалено"}


@router.get("/users/available")
async def get_available_users(
    search: str = Query("", description="Поиск по имени"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить список пользователей, которым можно написать.
    
    Фильтрует по правам доступа текущего пользователя.
    """
    sender_role = current_user.role or "Patient"
    allowed_roles = MESSAGING_PERMISSIONS.get(sender_role, [])
    
    query = db.query(User).filter(
        User.id != current_user.id,
        User.role.in_(allowed_roles),
        User.is_active == True
    )
    
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (User.username.ilike(search_pattern)) | 
            (User.email.ilike(search_pattern))
        )
    
    users = query.limit(20).all()
    
    return [
        {
            "id": u.id,
            "name": u.full_name or u.username or u.email or f"User {u.id}",
            "role": u.role
        }
        for u in users
    ]


# ============================================================================
# VOICE MESSAGES ENDPOINTS
# ============================================================================

@router.post("/send-voice", response_model=MessageOut)
async def send_voice_message(
    request: Request,
    recipient_id: int = Form(...),
    audio_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Отправить голосовое сообщение
    
    Поддерживаемые форматы: .mp3, .wav, .ogg, .m4a, .webm
    Максимальный размер: 10 MB
    Максимальная длительность: 5 минут
    """
    from app.utils.audio import validate_audio_file, get_audio_duration
    from app.models.file_system import File as FileModel, FileType
    from app.models.message import Message
    from app.ws.chat_ws import chat_manager
    
    # Проверка: нельзя писать самому себе
    if recipient_id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="Нельзя отправить сообщение самому себе"
        )
    
    # Проверка: получатель существует
    recipient = db.query(User).filter(User.id == recipient_id).first()
    if not recipient:
        raise HTTPException(
            status_code=404,
            detail="Пользователь не найден"
        )
    
    # Проверка прав доступа
    sender_role = current_user.role or "Patient"
    recipient_role = recipient.role or "Patient"
    
    if not can_send_message(sender_role, recipient_role):
        raise HTTPException(
            status_code=403,
            detail="Нет прав для отправки сообщения этому пользователю"
        )
    
    # Читаем содержимое файла
    content = await audio_file.read()
    
    # Валидация аудио файла
    format_name, mime_type = await validate_audio_file(content, audio_file.filename)
    
    # Получаем длительность
    duration = await get_audio_duration(content, format_name)
    
    # Сохраняем файл
    file_hash = hashlib.sha256(content).hexdigest()
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_filename = f"voice_{current_user.id}_{timestamp}.{format_name}"
    
    # Создаём директорию если не существует
    upload_dir = "uploads/voice_messages"
    os.makedirs(upload_dir, exist_ok=True)
    
    file_path = os.path.join(upload_dir, safe_filename)
    
    # Записываем файл на диск
    with open(file_path, "wb") as f:
        f.write(content)
    
    # Создаём запись в таблице files
    file_record = FileModel(
        filename=safe_filename,
        original_filename=audio_file.filename,
        file_path=file_path,
        file_size=len(content),
        file_type=FileType.AUDIO,
        mime_type=mime_type,
        file_hash=file_hash,
        owner_id=current_user.id,
        status="ready"
    )
    db.add(file_record)
    db.flush()  # Получаем ID файла
    
    # Создаём голосовое сообщение
    new_message = Message(
        sender_id=current_user.id,
        recipient_id=recipient_id,
        message_type="voice",
        file_id=file_record.id,
        voice_duration=duration,
        content=""  # Пустая строка для голосовых сообщений (поле NOT NULL в БД)
    )
    db.add(new_message)
    db.commit()
    db.refresh(new_message)
    
    # Обогащаем сообщение
    enriched_message = enrich_message(new_message, db)
    
    # Отправляем WebSocket уведомления
    # ВАЖНО: используем jsonable_encoder для сериализации datetime
    
    try:
        message_data = jsonable_encoder(enriched_message.dict())
        
        # Уведомляем получателя
        asyncio.create_task(
            chat_manager.notify_new_message(
                recipient_id=recipient.id,
                message_data=message_data
            )
        )
        
        # Уведомляем отправителя (для синхронизации других вкладок)
        asyncio.create_task(
            chat_manager.notify_new_message(
                recipient_id=current_user.id,
                message_data=message_data
            )
        )
    except Exception as e:
        logger.warning(f"Failed to send WebSocket notification: {e}")
    
    return enriched_message


@router.get("/voice/{message_id}/stream")
async def stream_voice_message(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Стриминг голосового сообщения
    
    Доступ разрешён только отправителю и получателю сообщения
    """
    from app.models.message import Message
    from app.models.file_system import File as FileModel
    
    # Получаем сообщение
    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise HTTPException(
            status_code=404,
            detail="Сообщение не найдено"
        )
    
    # Проверка доступа: только отправитель или получатель
    if message.sender_id != current_user.id and message.recipient_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Нет доступа к этому сообщению"
        )
    
    # Проверяем что это голосовое сообщение
    if message.message_type != "voice" or not message.file_id:
        raise HTTPException(
            status_code=400,
            detail="Это не голосовое сообщение"
        )
    
    # Получаем файл
    file_record = db.query(FileModel).filter(FileModel.id == message.file_id).first()
    if not file_record:
        raise HTTPException(
            status_code=404,
            detail="Аудио файл не найден"
        )
    
    # Проверяем что файл существует на диске
    if not os.path.exists(file_record.file_path):
        raise HTTPException(
            status_code=404,
            detail="Файл не найден на диске"
        )
    
    # Возвращаем файл для стриминга
    return FileResponse(
        file_record.file_path,
        media_type=file_record.mime_type,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Disposition": f'inline; filename="{file_record.original_filename}"'
        }
    )

