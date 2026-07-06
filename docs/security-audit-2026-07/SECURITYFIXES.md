# Security Fixes — Wave 1 Applied

Применённые исправления из основного аудита безопасности (Волна 1, P0+P1).

## Сводка применённых патчей

| ID  | Файл(ы)                                                                                   | Серьёзность | Статус    |
|-----|-------------------------------------------------------------------------------------------|-------------|-----------|
| F-001 | `backend/app/ws/chat_ws.py`, `frontend/src/contexts/ChatContext.jsx`                  | Critical    | ✅ Applied |
| F-002 | `backend/app/models/message.py`, `alembic/versions/0032_*.py`, `core/messaging_config.py`, `services/messages_api_service.py` | Critical | ✅ Applied |
| F-003 | `backend/app/utils/audio.py`, `services/messages_api_service.py`, `requirements.txt`  | High        | ✅ Applied |
| F-004 | `backend/app/services/messages_api_service.py`                                          | High        | ✅ Applied |
| F-005 | `backend/app/ws/chat_ws.py`, `services/messages_api_service.py`, `main.py`, `requirements.txt` | High | ✅ Applied |
| F-006 | `backend/app/ws/chat_ws.py`                                                              | High        | ✅ Applied |

## Детали изменений

### F-001: JWT out of WebSocket URL
- `chat_ws.py`: удалён параметр `token: str = Query(...)` из `chat_websocket_handler`.
  Теперь сервер принимает соединение, ждёт 5 секунд на получение первого сообщения
  вида `{"type":"auth","token":"<JWT>","contract_version":"..."}`, валидирует токен,
  и только потом продолжает цикл.
- `ChatContext.jsx`: WebSocket URL больше не содержит `?token=...`. В `ws.onopen`
  сразу отправляется auth-сообщение. При `e.code === 4001` (auth rejected)
  вызывается `tokenManager.invalidateAccessToken()` вместо слепого переподключения.

### F-002: Tenant isolation via `branch_id`
- `models/message.py`: добавлено поле `branch_id: Mapped[int | None]` с FK на
  `branches.id`. NULL для backward compat (single-clinic deployments / legacy rows).
- `alembic/versions/0032_messages_branch_id_tenant_isolation.py`: миграция
  добавляет колонку, backfill из `users.branch_id` (если существует), FK + индекс.
- `core/messaging_config.py`: добавлена `can_send_message_with_clinic()` —
  tenant-aware версия. Legacy `can_send_message()` сохранена для backward compat.
- `services/messages_api_service.py`: `validate_recipient()` теперь использует
  `can_send_message_with_clinic()` с проверкой `branch_id` отправителя и получателя.

### F-003: Audio magic bytes + attachment disposition
- `utils/audio.py`: переписана `validate_audio_file()` — добавлена проверка
  magic bytes через `_check_magic_bytes()` для каждого формата
  (mp3, wav, ogg, m4a, webm). Опциональная double-check через `python-magic`
  (если установлен).
- `messages_api_service.py`: `stream_voice_message` endpoint теперь возвращает
  `Content-Disposition: attachment` (вместо `inline`) + заголовки
  `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Content-Security-Policy: default-src 'none'`.
- `requirements.txt`: добавлены `python-magic==0.4.27` и `slowapi==0.1.9`.

### F-004: Direct message_id-based file authorization
- `messages_api_service.py`: `download_chat_file` endpoint теперь поддерживает
  два URL-паттерна:
  - `/download/{message_id}/{filename}` (новый, прямой auth через message_id)
  - `/download/{filename}` (legacy, substring search — будет удалён после
    полного перехода фронтенда)
- `upload_file_message`: формирует новый URL вида
  `/api/v1/messages/download/{message_id}/{filename}?name=...` для новых
  сообщений. Старые сообщения продолжат работать через legacy endpoint.
- Security headers (`X-Content-Type-Options`, `X-Frame-Options`) добавлены
  ко всем file-ответам.

### F-005: Rate limiting
- `chat_ws.py`: добавлен `ChatEventRateLimiter` (token bucket per user per
  event type). Лимиты: typing 5/sec, get_online_status 1/sec, ping 1/30sec.
  Также применяется `websocket_rate_limiter.check_rate_limit(ip_address)`
  при подключении (как в `/ws/queue/auth`).
- `messages_api_service.py`: добавлен `_chat_limiter` (SlowAPI) с лимитами:
  - POST `/send`: 10/minute
  - POST `/send-voice`: 5/minute
  - POST `/upload`: 5/minute
  - GET `/conversations`: 30/minute
  - GET `/conversation/{user_id}`: 30/minute
- `main.py`: регистрация SlowAPI middleware + exception handler.
- `requirements.txt`: `slowapi==0.1.9`.

### F-006: Conversation partner check
- `chat_ws.py`: добавлены хелперы `_users_have_conversation()` и
  `_get_user_conversation_partners()`.
- При подключении WS сервер отправляет клиенту init-сообщение со списком
  `conversation_partners` (user_id, с которыми есть переписка).
- `typing` event: проверяется, что между `user.id` и `recipient_id` существует
  хотя бы одно сообщение. Если нет — silent drop (без ошибки, чтобы не
  подтверждать существование пользователя).
- `get_online_status` event: фильтрует запрошенные `user_ids`, оставляя только
  тех, кто является собеседником текущего пользователя. Лимит 50 ID за запрос.

## Backward compatibility

Все изменения обратно совместимы:
- Legacy `can_send_message()` сохранена — существующие callers не сломаются.
- Legacy `/download/{filename}` endpoint работает — старые сообщения продолжат
  скачиваться.
- `branch_id` nullable — существующие строки в БД не требуют немедленного backfill.
- SlowAPI — optional dependency (если не установлен, rate limiting disabled
  с warning в логах).
- `python-magic` — optional (если не установлен, работает только magic bytes
  проверка без MIME-double-check).

## Миграция БД

Применить миграцию после merge:

```bash
cd backend
alembic upgrade head
```

Миграция `0032_messages_branch_id_tenant_isolation`:
1. Добавляет колонку `messages.branch_id` (nullable).
2. Backfill из `users.branch_id` (если колонка существует в users).
3. Добавляет FK + индекс.

## Не применено в этом PR

Следующие находки требуют отдельных PR (Волны 2 и 3):
- F-007..F-012 (Medium): audit-log, PII previews, at-rest encryption, Markdown
  sanitize, DNS rebinding, asyncio error handling.
- F-013..F-018 (Low): N+1 queries, multi-instance state, UUID filenames, CSP,
  retention, bare except.
- FA-001..FA-012 (AI-chat): применять патч F-001 к ai_chat.py + остальные
  AI-находки.

## Тестирование после применения

```bash
# Unit-тесты (существующие должны проходить без изменений)
pytest backend/tests/unit/ -v -k "chat or message or audio or messaging"

# E2E проверка:
# 1. Открыть чат в браузере → DevTools → Network → WS — URL не содержит ?token=
# 2. Скачивание файла — URL вида /download/{message_id}/{filename}
# 3. Загрузить .html с расширением .mp3 → 400 "magic bytes mismatch"
# 4. Отправить 11+ сообщений за минуту → 429 Too Many Requests
# 5. Попытка отправить typing пользователю без переписки → silent drop
```
