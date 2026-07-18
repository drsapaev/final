"""
PATCH F-006: Проверка собеседника в typing / get_online_status
==============================================================

Файлы:
  backend/app/ws/chat_ws.py — валидация recipient_id / user_ids

Проблема: любой пользователь может отправить typing-индикатор ЛЮБОМУ user_id,
а через get_online_status — проверить online-статус любого пользователя.

Решение: проверяем, что между current_user и recipient_id существует хотя бы
одна запись в таблице messages (т.е. они реальные собеседники).
"""


# === backend/app/ws/chat_ws.py — изменения в основном цикле ===
WS_PATCH = '''
# Добавить в начало файла:
from app.crud.message import message as crud_message
from sqlalchemy.orm import Session
from app.db.session import SessionLocal


# НОВОЕ: helper для проверки существующей переписки
def _users_have_conversation(db: Session, user1_id: int, user2_id: int) -> bool:
    """Проверить, что между двумя пользователями существует хотя бы одно сообщение."""
    from app.models.message import Message
    from sqlalchemy import or_, and_

    exists = db.query(Message.id).filter(
        or_(
            and_(Message.sender_id == user1_id, Message.recipient_id == user2_id),
            and_(Message.sender_id == user2_id, Message.recipient_id == user1_id),
        )
    ).first()
    return exists is not None


def _get_user_conversation_partners(db: Session, user_id: int) -> set[int]:
    """Получить множество user_id, с которыми у user_id есть переписка."""
    from app.models.message import Message
    from sqlalchemy import or_

    rows = db.query(
        Message.sender_id, Message.recipient_id
    ).filter(
        or_(Message.sender_id == user_id, Message.recipient_id == user_id)
    ).all()

    partners = set()
    for sender_id, recipient_id in rows:
        if sender_id == user_id:
            partners.add(recipient_id)
        else:
            partners.add(sender_id)
    return partners


# Изменения в обработке typing (строки 243-251 оригинала):

# === До ===
# if msg_type == MessageEventType.TYPING.value:
#     recipient_id = message.get("recipient_id")
#     is_typing = message.get("is_typing", False)
#     if recipient_id:
#         await chat_manager.broadcast_typing(
#             sender_id=user.id,
#             recipient_id=recipient_id,
#             is_typing=is_typing
#         )

# === После ===
if msg_type == MessageEventType.TYPING.value:
    recipient_id = message.get("recipient_id")
    is_typing = message.get("is_typing", False)
    if not recipient_id:
        continue

    # НОВОЕ: проверяем, что recipient_id — реальный собеседник
    check_db = SessionLocal()
    try:
        if not _users_have_conversation(check_db, user.id, int(recipient_id)):
            # Silent drop — не выдаём ошибку, чтобы не подтверждать существование
            # пользователя в системе
            logger.info(
                "Typing rejected: user_id=%s -> recipient_id=%s (no conversation)",
                user.id, recipient_id,
            )
            continue
    finally:
        check_db.close()

    await chat_manager.broadcast_typing(
        sender_id=user.id,
        recipient_id=int(recipient_id),
        is_typing=is_typing,
    )


# Изменения в обработке get_online_status (строки 258-269 оригинала):

# === До ===
# elif msg_type == MessageEventType.GET_ONLINE_STATUS.value:
#     user_ids = message.get("user_ids", [])
#     online_status = {uid: chat_manager.is_online(uid) for uid in user_ids}
#     await websocket.send_json(...)

# === После ===
elif msg_type == MessageEventType.GET_ONLINE_STATUS.value:
    requested_ids = message.get("user_ids", [])
    if not isinstance(requested_ids, list) or len(requested_ids) > 50:
        # НОВОЕ: лимит на количество запрашиваемых ID
        await websocket.send_json(
            build_ws_event_payload(
                "error",
                {"message": "Invalid user_ids (max 50)"},
            )
        )
        continue

    # НОВОЕ: только собеседники текущего пользователя
    check_db = SessionLocal()
    try:
        allowed_partners = _get_user_conversation_partners(check_db, user.id)
    finally:
        check_db.close()

    safe_ids = []
    for uid in requested_ids:
        try:
            uid_int = int(uid)
        except (TypeError, ValueError):
            continue
        if uid_int in allowed_partners:
            safe_ids.append(uid_int)

    online_status = {uid: chat_manager.is_online(uid) for uid in safe_ids}
    await websocket.send_json(
        build_ws_event_payload(
            MessageEventType.ONLINE_STATUS,
            {"users": online_status},
        )
    )


# Дополнительно: при подключении WS отправляем пользователю список его
# собеседников, чтобы фронтенд не запрашивал статусы произвольных user_id.

# Сразу после успешной авторизации (перед основным циклом):
init_db = SessionLocal()
try:
    partner_ids = _get_user_conversation_partners(init_db, user.id)
finally:
    init_db.close()

await websocket.send_json(
    build_ws_event_payload(
        "init",
        {"conversation_partners": list(partner_ids)},
    )
)
'''

if __name__ == "__main__":
    print("F-006 PATCH — Conversation partner check for typing / online status")
    print("=" * 60)
    print(WS_PATCH[:600] + "...")
