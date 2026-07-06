"""Service layer for messages endpoints."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.core.messaging_config import MESSAGING_PERMISSIONS, can_send_message, can_send_message_with_clinic
from app.core.messaging_contract import MessageEventType
from app.models.file_system import File as FileModel
from app.models.file_system import FileType
from app.models.message import Message
from app.models.user import User
from app.repositories.messages_api_repository import MessagesApiRepository
from app.schemas.message import ConversationOut, MessageCreate, MessageOut
from app.services.notifications import notification_sender_service

CHAT_UPLOAD_DIR = Path("uploads/chat")
CHAT_STORAGE_FILENAME_RE = re.compile(r"^\d{8}_\d{6}_.+$")
MAX_CHAT_UPLOAD_BYTES = 10 * 1024 * 1024
UPLOAD_READ_CHUNK_BYTES = 1024 * 1024
logger = logging.getLogger(__name__)


def _safe_chat_storage_filename(filename: str) -> str:
    if not filename or filename != filename.strip():
        raise HTTPException(status_code=400, detail="Недопустимое имя файла")
    if "/" in filename or "\\" in filename or os.path.basename(filename) != filename:
        raise HTTPException(status_code=400, detail="Недопустимое имя файла")
    if any(ord(char) < 32 for char in filename):
        raise HTTPException(status_code=400, detail="Недопустимое имя файла")
    if not CHAT_STORAGE_FILENAME_RE.fullmatch(filename):
        raise HTTPException(status_code=400, detail="Недопустимое имя файла")
    return filename


def _find_chat_upload_file(filename: str) -> Path:
    safe_filename = _safe_chat_storage_filename(filename)
    upload_root = CHAT_UPLOAD_DIR.resolve()

    if not upload_root.exists():
        raise HTTPException(status_code=404, detail="Файл не найден")

    for upload_path in upload_root.iterdir():
        resolved_path = upload_path.resolve()
        if resolved_path.parent != upload_root or not resolved_path.is_file():
            continue
        if upload_path.name == safe_filename:
            return resolved_path

    raise HTTPException(status_code=404, detail="Файл не найден")


def _build_chat_storage_filename(*, user_id: int, original_filename: str) -> str:
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return f"{timestamp}_{user_id}_{uuid.uuid4().hex}_{original_filename}"


async def _read_upload_bounded(
    upload: UploadFile,
    *,
    max_bytes: int,
) -> bytes:
    total_size = 0
    chunks: list[bytes] = []

    while True:
        chunk = await upload.read(UPLOAD_READ_CHUNK_BYTES)
        if not chunk:
            break
        total_size += len(chunk)
        if total_size > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File too large (maximum {max_bytes // 1024 // 1024} MB)",
            )
        chunks.append(chunk)

    return b"".join(chunks)


class MessagesApiService:
    """Handles chat API business logic."""

    def __init__(
        self,
        db: Session,
        repository: MessagesApiRepository | None = None,
    ):
        self.db = db
        self.repository = repository or MessagesApiRepository(db)

    @staticmethod
    def sanitize_content(content: str) -> str:
        try:
            import bleach

            return bleach.clean(content, tags=[], strip=True)
        except ImportError:
            import html

            return html.escape(content)

    @staticmethod
    def build_conversation_id(*, first_user_id: int, second_user_id: int) -> str:
        ordered_ids = sorted([int(first_user_id), int(second_user_id)])
        return f"{ordered_ids[0]}:{ordered_ids[1]}"

    def validate_recipient(self, *, recipient_id: int, current_user: User) -> User:
        if recipient_id == current_user.id:
            raise HTTPException(status_code=400, detail="Нельзя отправить сообщение самому себе")

        recipient = self.repository.get_user(recipient_id)
        if not recipient:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        sender_role = current_user.role or "Patient"
        recipient_role = recipient.role or "Patient"
        # F-002: tenant-aware check
        if not can_send_message_with_clinic(
            sender_role,
            recipient_role,
            sender_branch_id=getattr(current_user, "branch_id", None),
            recipient_branch_id=getattr(recipient, "branch_id", None),
        ):
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

        sanitized_content = self.sanitize_content(message_data.content)
        prepared_message_data = message_data.model_copy(
            update={"content": sanitized_content}
        )

        new_message = self.repository.create_message(
            sender_id=current_user.id,
            obj_in=prepared_message_data,
        )
        if message_data.patient_id is not None:
            new_message.patient_id = message_data.patient_id
            self.repository.commit()
            self.repository.refresh(new_message)

        self._audit(
            action="send_message",
            entity_type="message",
            entity_id=new_message.id,
            actor_user_id=current_user.id,
            payload={
                "recipient_id": recipient.id,
                "message_type": new_message.message_type,
                "patient_id": message_data.patient_id,
            },
        )

        from app.ws.chat_ws import chat_manager

        enriched_message = self.enrich_message(new_message)
        await notification_sender_service.send_message_received_notification(
            db=self.db,
            recipient=recipient,
            sender=current_user,
            message_id=new_message.id,
            conversation_id=self.build_conversation_id(
                first_user_id=current_user.id,
                second_user_id=recipient.id,
            ),
            message_type=new_message.message_type,
            preview=sanitized_content,
            patient_id=message_data.patient_id,
        )
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
        conversations = self.repository.get_conversations_list(user_id=user_id)
        total_unread = self.repository.get_unread_count(user_id=user_id)
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

        messages, total = self.repository.get_conversation(
            user1_id=current_user.id,
            user2_id=user_id,
            skip=skip,
            limit=limit,
        )

        unread_ids = self.repository.get_unread_message_ids(
            sender_id=user_id,
            recipient_id=current_user.id,
        )

        self.repository.mark_conversation_as_read(
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
        return self.repository.get_unread_count(user_id=user_id)

    def mark_message_read(self, *, message_id: int, user_id: int):
        existing_message = self.repository.get_message_by_id(message_id=message_id)
        should_notify_sender = bool(
            existing_message
            and existing_message.recipient_id == user_id
            and not existing_message.is_read
        )

        message = self.repository.mark_message_as_read(message_id=message_id, user_id=user_id)

        if message and should_notify_sender:
            try:
                from app.ws.chat_ws import chat_manager

                asyncio.create_task(
                    chat_manager.notify_message_read(
                        sender_id=message.sender_id,
                        message_id=message.id,
                    )
                )
            except Exception:
                pass

        return message

    async def delete_message(self, *, message_id: int, user_id: int) -> dict[str, Any]:
        success = self.repository.delete_message_for_user(message_id=message_id, user_id=user_id)
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
                    event_type=MessageEventType.MESSAGE_DELETED,
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
        message = self.repository.get_message_by_id(message_id=message_id)
        if not message:
            raise HTTPException(status_code=404, detail="Сообщение не найдено")
        if message.sender_id != current_user.id and message.recipient_id != current_user.id:
            raise HTTPException(status_code=403, detail="Вы не участник этой беседы")

        added = self.repository.toggle_reaction(
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
                    event_type=MessageEventType.REACTION_UPDATE,
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
                (User.username.ilike(search_pattern))
                | (User.email.ilike(search_pattern))
                | (User.full_name.ilike(search_pattern))
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
        from app.utils.audio import (
            MAX_AUDIO_SIZE,
            get_audio_duration,
            validate_audio_file,
        )
        from app.ws.chat_ws import chat_manager

        recipient = self.validate_recipient(recipient_id=recipient_id, current_user=current_user)
        content = await _read_upload_bounded(audio_file, max_bytes=MAX_AUDIO_SIZE)
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
        await notification_sender_service.send_message_received_notification(
            db=self.db,
            recipient=recipient,
            sender=current_user,
            message_id=new_message.id,
            conversation_id=self.build_conversation_id(
                first_user_id=current_user.id,
                second_user_id=recipient.id,
            ),
            message_type=new_message.message_type,
            preview=None,
            patient_id=getattr(new_message, "patient_id", None),
        )
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

        file_record = self.repository.get_file_by_id(message.file_id)
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
        recipient = self.validate_recipient(
            recipient_id=recipient_id,
            current_user=current_user,
        )

        content = await _read_upload_bounded(file, max_bytes=MAX_CHAT_UPLOAD_BYTES)
        original_filename = os.path.basename(file.filename or "file")
        safe_filename = _build_chat_storage_filename(
            user_id=current_user.id,
            original_filename=original_filename,
        )
        upload_dir = "uploads/chat"
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, safe_filename)

        with open(file_path, "wb") as file_obj:
            file_obj.write(content)

        message_obj = self.repository.create_message(
            obj_in=MessageCreate(
                recipient_id=recipient_id,
                content=original_filename,
                message_type="document"
                if not (file.content_type or "").startswith("image")
                else "image",
            ),
            sender_id=current_user.id,
        )
        # F-004: URL с message_id для прямой авторизации при скачивании
        message_obj.content = f"/api/v1/messages/download/{message_obj.id}/{safe_filename}?name={original_filename}"
        message_obj.message_type = (
            "image" if (file.content_type or "").startswith("image") else "file"
        )
        self.repository.commit()
        self.repository.refresh(message_obj)

        msg_out = self.enrich_message(message_obj)
        await notification_sender_service.send_message_received_notification(
            db=self.db,
            recipient=recipient,
            sender=current_user,
            message_id=message_obj.id,
            conversation_id=self.build_conversation_id(
                first_user_id=current_user.id,
                second_user_id=recipient.id,
            ),
            message_type=message_obj.message_type,
            preview=original_filename,
            patient_id=getattr(message_obj, "patient_id", None),
        )
        try:
            from app.ws.chat_ws import chat_manager

            asyncio.create_task(
                chat_manager.broadcast_event(
                    user_ids=[current_user.id, recipient.id],
                    event_type=MessageEventType.NEW_MESSAGE,
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


from fastapi import (  # noqa: E402  # manual-review: conditional import after config — intentional
    APIRouter,
    Depends,
    File,
    Form,
    Query,
    Request,
)
from fastapi.responses import (  # noqa: E402  # manual-review: conditional import after config — intentional
    FileResponse,  # noqa: E402  # manual-review: conditional import after config — intentional
)

from app.api.deps import (  # noqa: E402  # manual-review: conditional import after config — intentional
    get_current_user,
    get_db,
)
from app.schemas.message import (  # noqa: E402  # manual-review: conditional import after config — intentional
    ConversationListResponse,
    MessageListResponse,
    MessageReactionCreate,
    UnreadCountResponse,
)

# F-005: Rate limiting на REST endpoints чата
try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    _chat_limiter = Limiter(key_func=get_remote_address)
except ImportError:
    _chat_limiter = None
    logger.warning("slowapi not installed, chat REST rate limiting disabled")

router = APIRouter()


@router.post("/send", response_model=MessageOut)
@_chat_limiter.limit("10/minute") if _chat_limiter else (lambda f: f)
async def send_message(
    request: Request,
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
@_chat_limiter.limit("30/minute") if _chat_limiter else (lambda f: f)
async def get_conversations(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payload = MessagesApiService(db).get_conversations(user_id=current_user.id)
    return ConversationListResponse(**payload)


@router.get("/conversation/{user_id}", response_model=MessageListResponse)
@_chat_limiter.limit("30/minute") if _chat_limiter else (lambda f: f)
async def get_conversation(
    user_id: int,
    request: Request,
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
@_chat_limiter.limit("5/minute") if _chat_limiter else (lambda f: f)
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
    # F-003: attachment вместо inline + security headers (anti MIME-sniffing XSS)
    return FileResponse(
        payload["path"],
        media_type=payload["media_type"],
        headers={
            "Accept-Ranges": "bytes",
            "Content-Disposition": 'attachment; filename="voice_message"',
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Content-Security-Policy": "default-src 'none'",
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
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Chat file upload endpoint failed error_type=%s",
            type(exc).__name__,
        )
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.get("/download/{filename}")
@router.get("/download/{message_id}/{filename}")
async def download_chat_file(
    filename: str,
    message_id: int | None = None,
    name: str = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Скачать файловое вложение.

    F-004: при передаче message_id выполняется прямая авторизация
    (current_user должен быть отправителем или получателем message_id,
    filename должен соответствовать этому сообщению).

    Без message_id (legacy mode) сохраняется старое поведение с
    substring-поиском по Message.content — будет удалено после
    полного перехода фронтенда на новый URL.
    """
    safe_filename = _safe_chat_storage_filename(filename)

    if message_id is not None:
        # F-004: прямая авторизация через message_id
        message = db.query(Message).filter(Message.id == message_id).first()
        if not message:
            raise HTTPException(status_code=404, detail="Сообщение не найдено")

        if current_user.id != message.sender_id and current_user.id != message.recipient_id:
            logger.warning(
                "UNAUTHORIZED_FILE_ACCESS user_id=%s message_id=%s filename=%s",
                current_user.id, message_id, safe_filename,
            )
            raise HTTPException(status_code=403, detail="Нет доступа к этому файлу")

        # Проверяем, что filename соответствует этому сообщению
        if safe_filename not in (message.content or ""):
            raise HTTPException(
                status_code=400,
                detail="Файл не соответствует указанному сообщению"
            )
    else:
        # Legacy mode (без message_id) — substring-поиск, как раньше
        file_record = db.query(FileModel).filter(FileModel.filename == safe_filename).first()
        if file_record:
            candidate_messages = (
                db.query(Message).filter(Message.file_id == file_record.id).all()
            )
        else:
            candidate_messages = (
                db.query(Message)
                .filter(Message.content.contains(f"/download/{safe_filename}"))
                .all()
            )

        message = next(
            (
                item
                for item in candidate_messages
                if current_user.id == item.sender_id or current_user.id == item.recipient_id
            ),
            None,
        )

        if not message:
            raise HTTPException(status_code=403, detail="Нет доступа к этому файлу")

    file_path = _find_chat_upload_file(safe_filename)
    # F-003: security headers для file-ответов
    return FileResponse(
        path=str(file_path),
        filename=name or file_path.name,
        headers={
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
        },
    )


