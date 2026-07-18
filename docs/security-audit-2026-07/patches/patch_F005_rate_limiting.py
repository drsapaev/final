"""
PATCH F-005: Rate-limiting для WebSocket-событий и REST чата
============================================================

Файлы:
  1. backend/app/ws/chat_ws.py — применить websocket_rate_limiter + per-event bucket
  2. backend/app/services/messages_api_service.py — SlowAPI на REST endpoints
  3. backend/app/main.py — зарегистрировать SlowAPI middleware

Зависимости:
  pip install slowapi
"""


# === 1. backend/app/ws/chat_ws.py ===
WS_PATCH = '''
# Добавить в начало файла (после imports):
import time
from collections import defaultdict
from app.middleware.websocket_rate_limit import websocket_rate_limiter

# НОВОЕ: per-user, per-event-type rate limiter (token bucket в памяти)
class ChatEventRateLimiter:
    """
    Token-bucket rate limiter для WS-событий от конкретного user_id.

    Лимиты:
    - typing: 5 в секунду (200ms между событиями)
    - get_online_status: 1 в секунду
    - ping: 1 в 30 секунд
    """

    LIMITS = {
        "typing": (5, 1.0),           # 5 events per 1 second
        "get_online_status": (1, 1.0),  # 1 event per 1 second
        "ping": (1, 30.0),             # 1 event per 30 seconds
    }

    def __init__(self):
        # {user_id: {event_type: [last_refill_ts, tokens]}}
        self._buckets: dict[int, dict[str, list]] = defaultdict(lambda: defaultdict(list))

    def check(self, user_id: int, event_type: str) -> bool:
        if event_type not in self.LIMITS:
            return True  # Без лимита для неизвестных типов

        capacity, refill_period = self.LIMITS[event_type]
        now = time.monotonic()
        bucket = self._buckets[user_id][event_type]

        if not bucket:
            # Первый запрос — инициализируем
            bucket.extend([now, capacity - 1])
            return True

        last_refill, tokens = bucket
        # Сколько токенов добавить с прошлого раза
        elapsed = now - last_refill
        refill_rate = capacity / refill_period
        new_tokens = min(capacity, tokens + elapsed * refill_rate)

        if new_tokens < 1:
            return False  # Превышен лимит

        bucket[0] = now
        bucket[1] = new_tokens - 1
        return True


_chat_event_limiter = ChatEventRateLimiter()


# Изменения в chat_websocket_handler — основной цикл:
# (после успешной аутентификации)

# === Добавить ПЕРЕД циклом while True: ===
ip_address = websocket.client.host if websocket.client else "unknown"

# Глобальный rate limit по IP (как в queue_ws.py)
allowed, reason = websocket_rate_limiter.check_rate_limit(ip_address)
if not allowed:
    await websocket.close(
        code=4008,  # Policy Violation (custom)
        reason=f"Rate limit exceeded: {reason}",
    )
    return
websocket_rate_limiter.record_connection(ip_address)

try:
    while True:
        data = await websocket.receive_text()
        try:
            message = json.loads(data)
            msg_type = message.get("type")

            # НОВОЕ: per-event rate limiting
            if not _chat_event_limiter.check(user.id, msg_type):
                await websocket.send_json(
                    build_ws_event_payload(
                        "error",
                        {"message": f"Rate limit for {msg_type}"},
                    )
                )
                continue

            # Дальше — обработка как раньше
            if msg_type == MessageEventType.TYPING.value:
                # ...
            elif msg_type == MessageEventType.PING.value:
                # ...
            elif msg_type == MessageEventType.GET_ONLINE_STATUS.value:
                # ...

        except json.JSONDecodeError:
            await websocket.send_json(
                build_ws_event_payload("error", {"message": "Invalid JSON"})
            )
finally:
    websocket_rate_limiter.remove_connection(ip_address)
'''


# === 2. backend/app/main.py — регистрация SlowAPI ===
MAIN_PATCH = '''
# backend/app/main.py

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
'''


# === 3. backend/app/services/messages_api_service.py — rate limit на endpoints ===
REST_PATCH = '''
# Добавить к endpoints в messages_api_service.py (строки 668-857):

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

limiter = Limiter(key_func=get_remote_address)


# Каждому endpoint добавить decorator @limiter.limit(...):

@router.post("/send", response_model=MessageOut)
@limiter.limit("10/minute")  # НОВОЕ: 10 сообщений в минуту на IP
async def send_message(
    request: Request,  # НОВОЕ: обязательно для slowapi
    message_data: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = MessagesApiService(db)
    return await service.send_message(
        request=request, message_data=message_data, current_user=current_user,
    )


@router.post("/send-voice", response_model=MessageOut)
@limiter.limit("5/minute")  # НОВОЕ: 5 голосовых в минуту
async def send_voice_message(
    request: Request,
    recipient_id: int = Form(...),
    audio_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await MessagesApiService(db).send_voice_message(
        recipient_id=recipient_id, audio_file=audio_file, current_user=current_user,
    )


@router.post("/upload")
@limiter.limit("5/minute")  # НОВОЕ: 5 файлов в минуту
async def upload_file_message(
    request: Request,
    recipient_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await MessagesApiService(db).upload_file_message(
            recipient_id=recipient_id, file=file, current_user=current_user,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Chat file upload endpoint failed error_type=%s", type(exc).__name__)
        raise HTTPException(status_code=500, detail="Internal server error") from exc


# Read endpoints — менее строгий лимит:

@router.get("/conversations", response_model=ConversationListResponse)
@limiter.limit("30/minute")  # НОВОЕ: 30 чтений списка в минуту
async def get_conversations(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payload = MessagesApiService(db).get_conversations(user_id=current_user.id)
    return ConversationListResponse(**payload)


@router.get("/conversation/{user_id}", response_model=MessageListResponse)
@limiter.limit("30/minute")
async def get_conversation(
    request: Request,
    user_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payload = await MessagesApiService(db).get_conversation(
        user_id=user_id, skip=skip, limit=limit, current_user=current_user,
    )
    return MessageListResponse(**payload)
'''

if __name__ == "__main__":
    print("F-005 PATCH — Rate limiting for chat WS + REST")
    print("=" * 60)
    for name, content in [
        ("WS_PATCH", WS_PATCH),
        ("MAIN_PATCH", MAIN_PATCH),
        ("REST_PATCH", REST_PATCH),
    ]:
        print(f"\n--- {name} ---")
        print(content[:400] + "...")
