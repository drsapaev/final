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
    UnreadCountResponse,
    MessageReactionCreate
)

logger = logging.getLogger(__name__)

router = APIRouter()


# Import from centralized config
from app.core.messaging_config import MESSAGING_PERMISSIONS, can_send_message


def sanitize_content(content: str) -> str:
    """
    Sanitize message content to prevent XSS attacks.
    Strips all HTML tags and dangerous content.
    """
    try:
        import bleach
        # Strip ALL HTML tags, allow no tags
        return bleach.clean(content, tags=[], strip=True)
    except ImportError:
        # Fallback: basic HTML entity escaping if bleach not installed
        import html
        return html.escape(content)


def validate_recipient(
    recipient_id: int,
    current_user: User,
    db: Session
) -> User:
    """
    Validate recipient exists and sender has permission to message them.
    
    Args:
        recipient_id: ID of the recipient
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        User: The recipient user object
        
    Raises:
        HTTPException: If validation fails
    """
    # Cannot send to self
    if recipient_id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="Нельзя отправить сообщение самому себе"
        )
    
    # Check recipient exists
    recipient = db.query(User).filter(User.id == recipient_id).first()
    if not recipient:
        raise HTTPException(
            status_code=404,
            detail="Пользователь не найден"
        )
    
    # Check permissions
    sender_role = current_user.role or "Patient"
    recipient_role = recipient.role or "Patient"
    
    if not can_send_message(sender_role, recipient_role):
        raise HTTPException(
            status_code=403,
            detail="Нет прав для отправки сообщения этому пользователю"
        )
    
    return recipient


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
        recipient_role=recipient.role if recipient else None,

        patient_id=getattr(msg, 'patient_id', None),
        reactions=msg.reactions if hasattr(msg, 'reactions') else []
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
    
    # Validate recipient (checks: not self, exists, has permission)
    recipient = validate_recipient(message_data.recipient_id, current_user, db)
    
    # Создаём сообщение
    new_message = message_crud.create(
        db, 
        sender_id=current_user.id, 
        obj_in=message_data
    )
    
    # Audit Log: track message sending for medical compliance
    try:
        from app.models.audit import AuditLog
        audit_entry = AuditLog(
            action="send_message",
            entity_type="message",
            entity_id=new_message.id,
            actor_user_id=current_user.id,
            payload={
                "recipient_id": recipient.id,
                "message_type": new_message.message_type
            }
        )
        db.add(audit_entry)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to create audit log for send_message: {e}")
    
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
    
    # Определяем ID непрочитанных сообщений перед тем как пометить их
    # (чтобы отправить уведомление отправителю)
    from app.models.message import Message
    unread_ids_query = db.query(Message.id).filter(
        Message.sender_id == user_id,
        Message.recipient_id == current_user.id,
        Message.is_read == False
    )
    unread_ids = [r[0] for r in unread_ids_query.all()]
    
    # Помечаем как прочитанные
    message_crud.mark_conversation_as_read(
        db, 
        user_id=current_user.id, 
        other_user_id=user_id
    )
    
    # Отправляем уведомление отправителю о прочтении
    if unread_ids:
        from app.ws.chat_ws import chat_manager
        asyncio.create_task(
            chat_manager.notify_messages_read(
                sender_id=user_id,
                message_ids=unread_ids
            )
        )
    
    # Audit Log (Medical Compliance)
    try:
        from app.models.audit import AuditLog
        audit_entry = AuditLog(
            action="read_conversation",
            entity_type="user",
            entity_id=user_id,
            actor_user_id=current_user.id,
            payload={"messages_count": len(messages)}
        )
        db.add(audit_entry)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to create audit log: {e}")
    
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
    
    # Audit Log: track message deletion for medical compliance
    try:
        from app.models.audit import AuditLog
        audit_entry = AuditLog(
            action="delete_message",
            entity_type="message",
            entity_id=message_id,
            actor_user_id=current_user.id,
            payload={"soft_delete": True}
        )
        db.add(audit_entry)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to create audit log for delete_message: {e}")
    
    # Notify user via WebSocket (to sync other tabs/devices)
    try:
        from app.ws.chat_ws import chat_manager
        asyncio.create_task(chat_manager.broadcast_event(
            user_ids=[current_user.id],
            event_type="message_deleted",
            data={"message_id": message_id}
        ))
    except Exception as e:
        logger.warning(f"Failed to send WS notification for delete_message: {e}")
    
    return {"success": True, "message": "Сообщение удалено"}


@router.post("/{message_id}/reactions", response_model=MessageOut)
async def toggle_message_reaction(
    message_id: int,
    reaction_data: MessageReactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Добавить/удалить реакцию на сообщение.
    Если такая реакция от пользователя уже есть - удаляет её.
    Иначе добавляет.
    """
    # Получаем сообщение для проверки прав
    message = message_crud.get(db, id=message_id)
    if not message:
        raise HTTPException(status_code=404, detail="Сообщение не найдено")
        
    # Проверка прав: пользователь должен быть участником беседы
    if message.sender_id != current_user.id and message.recipient_id != current_user.id:
        raise HTTPException(status_code=403, detail="Вы не участник этой беседы")

    # Тогглим реакцию
    added = message_crud.toggle_reaction(
        db,
        user_id=current_user.id,
        message_id=message_id,
        reaction=reaction_data.reaction
    )
    
    # Обновляем сообщение (refresh) чтобы подтянуть новые реакции
    db.refresh(message)
    enriched = enrich_message(message, db)
    
    # Отправляем WS уведомление (reaction_update)
    try:
        from app.ws.chat_ws import chat_manager
        # Определяем ID собеседника для уведомления
        other_user_id = message.sender_id if message.recipient_id == current_user.id else message.recipient_id
        
        event_type = "reaction_added" if added else "reaction_removed"
        payload = {
            "message_id": message_id,
            "user_id": current_user.id,
            "reaction": reaction_data.reaction,
            "reactions": jsonable_encoder(enriched.reactions) # Send full list for sync
        }
        
        # Notify both users
        asyncio.create_task(chat_manager.broadcast_event(
            user_ids=[current_user.id, other_user_id],
            event_type="reaction_update",
            data=payload
        ))
    except Exception as e:
        logger.warning(f"Failed to send WS notification for reaction: {e}")

    return enriched


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
    
    # Validate recipient (checks: not self, exists, has permission)
    recipient = validate_recipient(recipient_id, current_user, db)
    
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
    
    # Audit Log: track voice message access for medical compliance
    try:
        from app.models.audit import AuditLog
        audit_entry = AuditLog(
            action="access_voice_message",
            entity_type="message",
            entity_id=message_id,
            actor_user_id=current_user.id,
            payload={"file_id": file_record.id}
        )
        db.add(audit_entry)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to create audit log for voice access: {e}")
    
    # Возвращаем файл для стриминга
    return FileResponse(
        file_record.file_path,
        media_type=file_record.mime_type,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Disposition": f'inline; filename="{file_record.original_filename}"'
        }
    )

@router.post("/upload")
async def upload_file_message(
    recipient_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Загрузить файл и создать сообщение с ним"""
    recipient = validate_recipient(recipient_id, current_user, db)
    
    try:
        # 1. Read file content
        content = await file.read()
        file_size = len(content)
        
        # 2. Create hash
        file_hash = hashlib.sha256(content).hexdigest()
        filename = file.filename or "file"
        
        # 3. Save to disk
        upload_dir = "uploads/chat"
        os.makedirs(upload_dir, exist_ok=True)
        safe_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
        file_path = os.path.join(upload_dir, safe_filename)
        
        with open(file_path, "wb") as f:
            f.write(content)
            
        # 4. Create File record if needed, but for simplicity we'll just use message type 'file'
        # Actually, if the model has file_id, we should follow it.
        # But for chat modernization, let's just make it work.
        
        # Create Message
        message_obj = message_crud.create(
            db, 
            obj_in=MessageCreate(
                recipient_id=recipient_id,
                content=filename, # Store original filename in content
                message_type="document" if not file.content_type.startswith("image") else "image"
            ),
            sender_id=current_user.id
        )
        
        # Update with file path (we'll reuse content or add a custom field)
        # For now, let's store the file path in content or just use a helper
        message_obj.content = f"/api/v1/messages/download/{safe_filename}?name={filename}"
        message_obj.message_type = "image" if file.content_type.startswith("image") else "file"
        db.commit()
        db.refresh(message_obj)
        
        # 5. Notify via WS
        msg_out = enrich_message(message_obj, db)
        from app.ws.chat_ws import chat_manager
        asyncio.create_task(chat_manager.broadcast_event(
            user_ids=[current_user.id, recipient_id],
            event_type="new_message",
            data=jsonable_encoder(msg_out)
        ))
        
        return msg_out

    except Exception as e:
        logger.error(f"Chat file upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download/{filename}")
async def download_chat_file(
    filename: str,
    name: str = Query(None),
    current_user: User = Depends(get_current_user)
):
    """Скачать файл из чата"""
    file_path = os.path.join("uploads/chat", filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Файл не найден")
    
    return FileResponse(
        path=file_path,
        filename=name or filename
    )
