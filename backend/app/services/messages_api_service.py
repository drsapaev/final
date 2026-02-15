"""Service layer for messages endpoints."""

from __future__ import annotations

import asyncio
import hashlib
import os
from datetime import datetime
from typing import Any

from fastapi import HTTPException, UploadFile
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.core.messaging_config import MESSAGING_PERMISSIONS, can_send_message
from app.crud.message import message as message_crud
from app.models.file_system import File as FileModel
from app.models.file_system import FileType
from app.models.message import Message
from app.models.user import User
from app.repositories.messages_api_repository import MessagesApiRepository
from app.schemas.message import ConversationOut, MessageCreate, MessageOut
from app.services.notifications import notification_sender_service


class MessagesApiService:
    """Handles chat API business logic."""

    def __init__(
        self,
        db: Session,
        repository: MessagesApiRepository | None = None,
    ):
        self.repository = repository or MessagesApiRepository(db)

    @staticmethod
    def sanitize_content(content: str) -> str:
        try:
            import bleach

            return bleach.clean(content, tags=[], strip=True)
        except ImportError:
            import html

            return html.escape(content)

    def validate_recipient(self, *, recipient_id: int, current_user: User) -> User:
        if recipient_id == current_user.id:
            raise HTTPException(status_code=400, detail="Нельзя отправить сообщение самому себе")

        recipient = self.repository.get_user(recipient_id)
        if not recipient:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        sender_role = current_user.role or "Patient"
        recipient_role = recipient.role or "Patient"
        if not can_send_message(sender_role, recipient_role):
            raise HTTPException(
                status_code=403,
                detail="Нет прав для отправки сообщения этому пользователю",
            )
        return recipient

    def enrich_message(self, msg) -> MessageOut:
        sender = self.repository.get_user(msg.sender_id)
        recipient = self.repository.get_user(msg.recipient_id)
        file_url = None
        if msg.message_type == "voice" and msg.file_id:
            file_url = f"/api/v1/messages/voice/{msg.id}/stream"

        def get_name(user):
            if not user:
                return None
            return user.full_name or user.username or user.email

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
            patient_id=getattr(msg, "patient_id", None),
            reactions=msg.reactions if hasattr(msg, "reactions") else [],
        )

    def _audit(self, *, action: str, entity_type: str, entity_id: int, actor_user_id: int, payload: dict[str, Any]) -> None:
        try:
            from app.models.audit import AuditLog

            audit_entry = AuditLog(
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                actor_user_id=actor_user_id,
                payload=payload,
            )
            self.repository.add(audit_entry)
            self.repository.commit()
        except Exception:
            # Audit errors should not fail user flow
            pass

    async def send_message(self, *, request, message_data: MessageCreate, current_user: User) -> MessageOut:
        recipient = self.validate_recipient(
            recipient_id=message_data.recipient_id,
            current_user=current_user,
        )

        new_message = message_crud.create(
            self.repository.db,
            sender_id=current_user.id,
            obj_in=message_data,
        )

        self._audit(
            action="send_message",
            entity_type="message",
            entity_id=new_message.id,
            actor_user_id=current_user.id,
            payload={"recipient_id": recipient.id, "message_type": new_message.message_type},
        )

        from app.ws.chat_ws import chat_manager

        enriched_message = self.enrich_message(new_message)
        try:
            asyncio.create_task(
                chat_manager.notify_new_message(
                    recipient_id=recipient.id,
                    message_data=enriched_message.model_dump() if hasattr(enriched_message, "model_dump") else enriched_message.dict(),
                )
            )
            asyncio.create_task(
                chat_manager.notify_new_message(
                    recipient_id=current_user.id,
                    message_data=enriched_message.model_dump() if hasattr(enriched_message, "model_dump") else enriched_message.dict(),
                )
            )
        except Exception:
            pass

        return enriched_message

    def get_conversations(self, *, user_id: int) -> dict[str, Any]:
        conversations = message_crud.get_conversations_list(self.repository.db, user_id=user_id)
        total_unread = message_crud.get_unread_count(self.repository.db, user_id=user_id)
        return {
            "conversations": [ConversationOut(**item) for item in conversations],
            "total_unread": total_unread,
        }

    async def get_conversation(
        self,
        *,
        user_id: int,
        skip: int,
        limit: int,
        current_user: User,
    ) -> dict[str, Any]:
        other_user = self.repository.get_user(user_id)
        if not other_user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        messages, total = message_crud.get_conversation(
            self.repository.db,
            user1_id=current_user.id,
            user2_id=user_id,
            skip=skip,
            limit=limit,
        )

        unread_ids_query = self.repository.query_message_ids().filter(
            Message.sender_id == user_id,
            Message.recipient_id == current_user.id,
            Message.is_read.is_(False),
        )
        unread_ids = [item[0] for item in unread_ids_query.all()]

        message_crud.mark_conversation_as_read(
            self.repository.db,
            user_id=current_user.id,
            other_user_id=user_id,
        )

        if unread_ids:
            from app.ws.chat_ws import chat_manager

            asyncio.create_task(
                chat_manager.notify_messages_read(sender_id=user_id, message_ids=unread_ids)
            )

        self._audit(
            action="read_conversation",
            entity_type="user",
            entity_id=user_id,
            actor_user_id=current_user.id,
            payload={"messages_count": len(messages)},
        )

        return {
            "messages": [self.enrich_message(message) for message in messages],
            "total": total,
            "has_more": skip + limit < total,
        }

    def get_unread_count(self, *, user_id: int) -> int:
        return message_crud.get_unread_count(self.repository.db, user_id=user_id)

    def mark_message_read(self, *, message_id: int, user_id: int):
        return message_crud.mark_as_read(self.repository.db, message_id=message_id, user_id=user_id)

    async def delete_message(self, *, message_id: int, user_id: int) -> dict[str, Any]:
        success = message_crud.delete_for_user(self.repository.db, message_id=message_id, user_id=user_id)
        if not success:
            raise HTTPException(status_code=404, detail="Сообщение не найдено или нет доступа")

        self._audit(
            action="delete_message",
            entity_type="message",
            entity_id=message_id,
            actor_user_id=user_id,
            payload={"soft_delete": True},
        )

        try:
            from app.ws.chat_ws import chat_manager

            asyncio.create_task(
                chat_manager.broadcast_event(
                    user_ids=[user_id],
                    event_type="message_deleted",
                    data={"message_id": message_id},
                )
            )
        except Exception:
            pass

        return {"success": True, "message": "Сообщение удалено"}

    async def toggle_message_reaction(
        self,
        *,
        message_id: int,
        reaction: str,
        current_user: User,
    ) -> MessageOut:
        message = message_crud.get(self.repository.db, id=message_id)
        if not message:
            raise HTTPException(status_code=404, detail="Сообщение не найдено")
        if message.sender_id != current_user.id and message.recipient_id != current_user.id:
            raise HTTPException(status_code=403, detail="Вы не участник этой беседы")

        added = message_crud.toggle_reaction(
            self.repository.db,
            user_id=current_user.id,
            message_id=message_id,
            reaction=reaction,
        )

        self.repository.refresh(message)
        enriched = self.enrich_message(message)

        try:
            from app.ws.chat_ws import chat_manager

            other_user_id = (
                message.sender_id
                if message.recipient_id == current_user.id
                else message.recipient_id
            )
            payload = {
                "message_id": message_id,
                "user_id": current_user.id,
                "reaction": reaction,
                "reactions": jsonable_encoder(enriched.reactions),
                "added": added,
            }
            asyncio.create_task(
                chat_manager.broadcast_event(
                    user_ids=[current_user.id, other_user_id],
                    event_type="reaction_update",
                    data=payload,
                )
            )
        except Exception:
            pass

        return enriched

    def get_available_users(self, *, search: str, current_user: User) -> list[dict[str, Any]]:
        sender_role = current_user.role or "Patient"
        allowed_roles = MESSAGING_PERMISSIONS.get(sender_role, [])

        query = self.repository.query_users().filter(
            User.id != current_user.id,
            User.role.in_(allowed_roles),
            User.is_active.is_(True),
        )
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                (User.username.ilike(search_pattern)) | (User.email.ilike(search_pattern))
            )
        users = query.limit(20).all()
        return [
            {
                "id": user.id,
                "name": user.full_name or user.username or user.email or f"User {user.id}",
                "role": user.role,
            }
            for user in users
        ]

    async def send_voice_message(
        self,
        *,
        recipient_id: int,
        audio_file: UploadFile,
        current_user: User,
    ) -> MessageOut:
        from app.utils.audio import get_audio_duration, validate_audio_file
        from app.ws.chat_ws import chat_manager

        recipient = self.validate_recipient(recipient_id=recipient_id, current_user=current_user)
        content = await audio_file.read()
        format_name, mime_type = await validate_audio_file(content, audio_file.filename)
        duration = await get_audio_duration(content, format_name)

        file_hash = hashlib.sha256(content).hexdigest()
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"voice_{current_user.id}_{timestamp}.{format_name}"
        upload_dir = "uploads/voice_messages"
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, safe_filename)

        with open(file_path, "wb") as file_obj:
            file_obj.write(content)

        file_record = FileModel(
            filename=safe_filename,
            original_filename=audio_file.filename,
            file_path=file_path,
            file_size=len(content),
            file_type=FileType.AUDIO,
            mime_type=mime_type,
            file_hash=file_hash,
            owner_id=current_user.id,
            status="ready",
        )
        self.repository.add(file_record)
        self.repository.flush()

        new_message = Message(
            sender_id=current_user.id,
            recipient_id=recipient_id,
            message_type="voice",
            file_id=file_record.id,
            voice_duration=duration,
            content="",
        )
        self.repository.add(new_message)
        self.repository.commit()
        self.repository.refresh(new_message)

        enriched_message = self.enrich_message(new_message)
        try:
            message_data = jsonable_encoder(
                enriched_message.model_dump()
                if hasattr(enriched_message, "model_dump")
                else enriched_message.dict()
            )
            asyncio.create_task(
                chat_manager.notify_new_message(
                    recipient_id=recipient.id,
                    message_data=message_data,
                )
            )
            asyncio.create_task(
                chat_manager.notify_new_message(
                    recipient_id=current_user.id,
                    message_data=message_data,
                )
            )
        except Exception:
            pass

        return enriched_message

    def stream_voice_message(self, *, message_id: int, current_user: User) -> dict[str, Any]:
        message = self.repository.get_message(message_id)
        if not message:
            raise HTTPException(status_code=404, detail="Сообщение не найдено")
        if message.sender_id != current_user.id and message.recipient_id != current_user.id:
            raise HTTPException(status_code=403, detail="Нет доступа к этому сообщению")
        if message.message_type != "voice" or not message.file_id:
            raise HTTPException(status_code=400, detail="Это не голосовое сообщение")

        file_record = self.repository.db.query(FileModel).filter(FileModel.id == message.file_id).first()
        if not file_record:
            raise HTTPException(status_code=404, detail="Аудио файл не найден")
        if not os.path.exists(file_record.file_path):
            raise HTTPException(status_code=404, detail="Файл не найден на диске")

        self._audit(
            action="access_voice_message",
            entity_type="message",
            entity_id=message_id,
            actor_user_id=current_user.id,
            payload={"file_id": file_record.id},
        )

        return {
            "path": file_record.file_path,
            "media_type": file_record.mime_type,
            "content_disposition_filename": file_record.original_filename,
        }

    async def upload_file_message(
        self,
        *,
        recipient_id: int,
        file: UploadFile,
        current_user: User,
    ) -> MessageOut:
        self.validate_recipient(recipient_id=recipient_id, current_user=current_user)

        content = await file.read()
        filename = file.filename or "file"
        safe_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
        upload_dir = "uploads/chat"
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, safe_filename)

        with open(file_path, "wb") as file_obj:
            file_obj.write(content)

        message_obj = message_crud.create(
            self.repository.db,
            obj_in=MessageCreate(
                recipient_id=recipient_id,
                content=filename,
                message_type="document"
                if not (file.content_type or "").startswith("image")
                else "image",
            ),
            sender_id=current_user.id,
        )
        message_obj.content = f"/api/v1/messages/download/{safe_filename}?name={filename}"
        message_obj.message_type = (
            "image" if (file.content_type or "").startswith("image") else "file"
        )
        self.repository.commit()
        self.repository.refresh(message_obj)

        msg_out = self.enrich_message(message_obj)
        try:
            from app.ws.chat_ws import chat_manager

            asyncio.create_task(
                chat_manager.broadcast_event(
                    user_ids=[current_user.id, recipient_id],
                    event_type="new_message",
                    data=jsonable_encoder(
                        msg_out.model_dump() if hasattr(msg_out, "model_dump") else msg_out.dict()
                    ),
                )
            )
        except Exception:
            pass

        return msg_out

# --- API Router moved from app/api/v1/endpoints/messages.py ---

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

