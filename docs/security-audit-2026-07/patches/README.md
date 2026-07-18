# Патчи для аудита безопасности — АРХИВ (уже применены)

> ⚠️ **ВНИМАНИЕ:** Эти патчи уже применены к исходному коду в PR #1939.
> Файлы сохранены как архив. Не применяйте их повторно — используйте
> как reference для понимания что было изменено.

# Патчи для аудита безопасности чата (Волна 1)

## Обзор

Этот каталог содержит готовые код-патчи для устранения критических и высокоприоритетных
находок аудита безопасности чата медицинской клиники `github.com/drsapaev/final`.

**Аудит-отчёт:** `/home/z/my-project/download/audit_chat_security.pdf`

## Список патчей

| ID  | Файл                                         | Серьёзность | Описание                                                |
|-----|----------------------------------------------|-------------|---------------------------------------------------------|
| F-001 | `patch_F001_jwt_in_url.py`                 | Critical    | JWT перенесён из URL Query String в первое WS-сообщение |
| F-002 | `patch_F002_tenant_isolation.py`           | Critical    | Добавлен `clinic_id` в таблицу messages + tenant-проверка |
| F-003 | `patch_F003_audio_magic_bytes.py`          | High        | Проверка magic bytes + `Content-Disposition: attachment` |
| F-004 | `patch_F004_file_auth.py`                  | High        | Прямая авторизация файлов через `message_id` |
| F-005 | `patch_F005_rate_limiting.py`              | High        | Rate limiting для WS-событий и REST-эндпоинтов чата |
| F-006 | `patch_F006_typing_online_auth.py`         | High        | Проверка собеседника в `typing` / `get_online_status` |

## Порядок применения

### 1. Подготовка

```bash
# Клонировать репозиторий (если ещё не сделано)
git clone https://github.com/drsapaev/final.git
cd final

# Создать ветку для security-фиксов
git checkout -b security/audit-wave-1
```

### 2. Установка новых зависимостей

```bash
# Backend
cd backend
pip install python-magic slowapi
# Системная зависимость для python-magic:
sudo apt-get install libmagic1  # Ubuntu/Debian
# или brew install libmagic     # macOS

# Добавить в requirements.txt:
echo "python-magic==0.4.27" >> requirements.txt
echo "slowapi==0.1.9" >> requirements.txt
```

### 3. Применение патчей по порядку

Каждый `.py` файл содержит:
- Описание затронутых файлов
- Полный код новой версии изменяемых функций/классов
- Комментарии `# НОВОЕ:` и `# ИЗМЕНЕНО:` для понимания изменений

**Рекомендуемый порядок применения:**

1. **F-002 (tenant isolation)** — самая масштабная, требует миграции БД
   - Добавить `clinic_id` в `models/message.py`
   - Создать Alembic миграцию `0030_add_clinic_id_to_messages.py`
   - Обновить `messaging_config.py` (новая сигнатура `can_send_message`)
   - Обновить `crud/message.py` (фильтр по clinic_id во всех запросах)
   - Применить миграцию: `alembic upgrade head`

2. **F-001 (JWT в URL)** — backend + frontend изменения
   - Заменить обработчик в `chat_ws.py`
   - Обновить `ChatContext.jsx` — отправка auth-сообщения в `onopen`
   - Прогнать тесты: `pytest backend/tests/unit/test_chat_ws_manager.py`

3. **F-003 (audio magic bytes)** — backend only
   - Обновить `utils/audio.py`
   - Обновить `stream_voice_message` в `messages_api_service.py`
   - Прогнать тесты: `pytest backend/tests/unit/test_audio_*.py`

4. **F-004 (file auth)** — backend + frontend
   - Заменить `download_chat_file` endpoint
   - Обновить формирование `content` в `upload_file_message`
   - Фронтенд: добавить проверку `isInternalUrl()` перед рендером `<a href>`

5. **F-005 (rate limiting)** — backend only
   - Зарегистрировать SlowAPI в `main.py`
   - Добавить `@limiter.limit(...)` к REST endpoints
   - Добавить `_chat_event_limiter` в `chat_ws.py` для per-event bucket
   - Применить `websocket_rate_limiter` (как в `websocket_auth.py`)

6. **F-006 (typing/online auth)** — backend only
   - Добавить helper-функции `_users_have_conversation` / `_get_user_conversation_partners`
   - Обновить обработку `typing` и `get_online_status` в `chat_ws.py`

### 4. Тестирование

```bash
# Unit-тесты
pytest backend/tests/unit/ -v -k "chat or message or audio"

# Integration-тесты
pytest backend/tests/integration/ -v -k "chat"

# E2E (Playwright)
cd frontend && npx playwright test chat

# Ручная проверка:
# 1. Открыть чат в браузере, в DevTools → Network → WS — убедиться, что в URL нет ?token=
# 2. Попробовать скачать файл без авторизации — должен быть 403
# 3. Загрузить .html с расширением .mp3 — должен быть 400 "magic bytes mismatch"
# 4. Отправить 20 сообщений за минуту — 11-й должен получить 429
# 5. Попробовать отправить typing несуществующему user_id — silent drop
```

### 5. Миграция БД

```bash
# Создать миграцию (если используете alembic autogenerate)
cd backend
alembic revision --autogenerate -m "add clinic_id to messages"

# Применить
alembic upgrade head

# Проверить
psql -c "\\d messages"  # должна появиться колонка clinic_id
```

### 6. Commit и PR

```bash
git add -A
git commit -m "security(audit-wave-1): fix F-001..F-006

- F-001: Move JWT out of WebSocket URL to first message
- F-002: Add clinic_id to messages for tenant isolation
- F-003: Validate audio magic bytes + Content-Disposition: attachment
- F-004: Direct message_id-based file authorization (no substring search)
- F-005: Rate limiting for WS events + REST endpoints (slowapi)
- F-006: Verify conversation exists before typing/online-status

Refs: security audit report audit_chat_security.pdf"

git push origin security/audit-wave-1
# Создать PR, добавить ревьюеров
```

## Зависимости и совместимость

- **Python:** 3.11+ (использует `match` синтаксис в некоторых местах)
- **FastAPI:** 0.100+
- **Pydantic:** v2
- **SQLAlchemy:** 2.0+
- **PostgreSQL:** 17+
- **Alembic:** 1.12+

## Известные риски применения

1. **F-001 (JWT в URL)** — breaking change для существующих WS-клиентов. Нужно
   одновременно выкатить frontend и backend. На период миграции можно
   поддерживать оба режима (token в URL как fallback, с warning в логах).

2. **F-002 (clinic_id)** — требует backfill существующих сообщений. В
   single-clinic развёртывании все сообщения получат `clinic_id = 1`.
   В multi-clinic — нужно вручную проверить правильность backfill.

3. **F-005 (rate limiting)** — может заблокировать легитимных активных
   пользователей. Начать с мягких лимитов (20/min для /send) и мониторить
   429-ответы. Поднять лимиты для ролей Admin/Doctor если нужно.

## Что НЕ включает Волна 1

Эти патчи не покрывают Medium-находки (F-007..F-012) и Low (F-013..F-018).
Они должны быть устранены в Волне 2 (1 месяц) и Волне 3 (1 квартал) согласно
плану remediation в основном отчёте.

Особенно важно спланировать отдельно:
- **F-009** (шифрование content at-rest) — требует миграции всех существующих
  данных, выбор KMS, обновление всех CRUD-операций
- **F-014** (Redis Pub/Sub для multi-instance) — требует инфраструктурных
  изменений (Redis deployment)

## Контакты

По вопросам применения патчей — обращаться к автору аудита.
Полный отчёт со всеми находками: `audit_chat_security.pdf`
Дополнительное приложение по AI-чату: `audit_ai_chat_appendix.pdf`
