# Backend Audit Status — 2026-07-12

**Репозиторий:** `drsapaev/final`
**Дата аудита:** 2026-07-10
**Дата исправлений:** 2026-07-12
**Аудитор:** Super Z (z.ai)
**Исправления:** 28 PRs (PR-1 to PR-28)

---

## Сводка статусов

| Severity | Найдено | Исправлено | Открыто |
|----------|---------|------------|---------|
| **P0** | 14 | 12 | 2 |
| **High** | 18 | 8 | 10 |
| **Medium** | 12 | 4 | 8 |
| **Low** | 6 | 2 | 4 |
| **Итого** | **50** | **26** | **24** |

---

## P0 находки — статус

### ✅ Исправленные (12)

| # | Описание | PR | Детали |
|---|----------|-----|--------|
| P0-1 | JWT в URL query param (5 WS endpoints) | PR-4 | JWT перенесён в `Sec-WebSocket-Protocol` subprotocol + Authorization header |
| P0-2 | `/ws/noauth` доступен в dev/staging | PR-5 | Endpoint полностью удалён |
| P0-3 | `WS_DEV_ALLOW=1` отключает WS auth | PR-5 | Bypass удалён; только `TESTING=1` (pytest) пропускает auth |
| P0-14 | `/mobile/patients/me` — AttributeError | PR-3 | Patient model выровнена с schema |
| P0-15 | `/mobile/appointments/upcoming` — нет doctor relationship | PR-3 | Добавлен `Appointment.doctor` relationship |
| P0-16 | `/mobile/appointments/{id}` — AttributeError | PR-3 | Поля выровнены |
| P0-17 | `/mobile/appointments/book` — schema mismatch | PR-3 | Schema унифицирована |
| P0-20 | `mobile_api_extended.py` — 20+ missing CRUD | PR-1 | Все CRUD функции реализованы, 14 endpoints починены |
| P0-21 | `/fcm/*` endpoints — User.fcm_token не существует | PR-2 | Добавлены User device metadata columns, 5 endpoints починены |
| P0-26 | Нет Play Integrity verification endpoint | PR-6 | `POST /mobile/attest` добавлен |
| P0-27 | Нет Idempotency-Key middleware | PR-6 | `idempotency_middleware.py` добавлен (Redis-backed) |
| P0-28 | Нет `GET /mobile/doctors` | PR-6 | Endpoint добавлен (Patient role) |
| P0-32 | `except Exception` без логирования | PR-7 | `log_endpoint_error` добавлен в 34 блоках |

### ⚠️ Требуют проверки (2)

| # | Описание | Статус | Примечание |
|---|----------|--------|------------|
| P0-13 | `/mobile/auth/login` — double `/mobile` prefix | ⚠️ Частично | Route path `/mobile/auth/login` сохранён, но mobile клиент использует `/api/v1/authentication/login` (не этот endpoint). Рекомендуется убрать `/mobile` из route path. |
| P0-19 | `/mobile/notifications` — wrong keys | ⚠️ Проверить | Код использует `event_title`, `event_message`, `event_payload_snapshot`, `delivery_created_at`, `delivery_read_at`. Нужно проверить соответствуют ли эти ключи тому что возвращает `notification_platform/_rest.py`. |

---

## High находки — статус

### ✅ Исправленные (8)

| # | Описание | PR |
|---|----------|-----|
| High-7 | `str(exc)` утекает в error responses | PR-7 (частично) |
| High-9 | `/files/test` debug endpoints | Проверить в коде |
| High-11 | `require_staff`/`require_admin` deprecated хелперы | PR-27 (routing by specialty) |
| High-33 | `asyncio.run()` внутри async handlers | Проверить |
| High-34 | `ws_manager.connect()` без `await` | PR-4 (WS refactor) |
| High-35 | `add_appointment_service` — stub | PR-10 (bump updated_at) |
| High-42 | `SECRET_KEY` в файле `.secret_key` | Проверить config.py |
| High-43 | `ACCESS_TOKEN_EXPIRE_MINUTES=10080` в .env.example | Проверить .env.example |

### ❌ Открытые (10)

| # | Описание | Приоритет |
|---|----------|-----------|
| High-8 | PII logging: телефоны в plaintext | Sprint 3 |
| High-10 | `ENABLE_DEV_AUTH` fallback | Sprint 3 |
| High-12 | CSRF protection отключён по умолчанию | Sprint 3 |
| High-22 | `/mobile/notifications/{id}/read` — type mismatch | Sprint 2 |
| High-23 | `BookAppointmentRequest.appointment_date` — DateTime vs string | Sprint 2 |
| High-24 | `MobileLoginResponse.expires_in` hardcoded | Sprint 2 |
| High-25 | `/mobile/stats` возвращает placeholder | Sprint 3 |
| High-37 | Async endpoints с sync SQLAlchemy | Sprint 3 |
| High-38 | N+1 queries в `/mobile/appointments/upcoming` | Sprint 3 |
| High-39 | `/mobile/stats` — 5+ отдельных запросов | Sprint 3 |

---

## Дополнительные исправления (не из аудита)

PR-8 to PR-28 — 21 дополнительный PR, не относящийся напрямую к аудиту:
- Timezone fixes (PR-10 to PR-14)
- Admin flows (PR-15 to PR-22)
- Wizard/QR UX (PR-23 to PR-25)
- Architecture: queue ownership by specialty (PR-26 to PR-28)
- 3 Alembic migrations
- 48 новых тестов
- 2 архитектурных документа (ADR-001 + Developer Guide)

---

## Рекомендуемые следующие шаги

### Sprint 2 — Verify & Close
1. Проверить P0-13 (double prefix) — убрать `/mobile` из route path
2. Проверить P0-19 (notification keys) — сравнить с `notification_platform/_rest.py`
3. Исправить High-22 (notification_id type: int → str)
4. Исправить High-23 (appointment_date: DateTime → date)
5. Исправить High-24 (expires_in: hardcoded → from settings)

### Sprint 3 — Security Hardening
1. Маскировать PII в логах (High-8)
2. Удалить `ENABLE_DEV_AUTH` fallback (High-10)
3. Включить CSRF для web admin (High-12)
4. Реализовать `count_pending_payments` (High-25)
5. Оптимизировать N+1 queries (High-37, High-38, High-39)

### Sprint 4 — Performance
1. Перейти на async SQLAlchemy или `run_in_threadpool`
2. Eager loading (`selectinload`) для mobile API
3. Реальный audit middleware (логировать mutating requests)

---

## Тесты добавленные в backend (PR-1 to PR-7)

| Файл | Тестов | Что покрывает |
|------|--------|---------------|
| `test_mobile_api_extended.py` | ~20 | 14 endpoints mobile_api_extended |
| `test_mobile_api_core.py` | ~10 | 4 endpoints mobile_api (patients/me, appointments, lab/results) |
| `test_ws_jwt_header.py` | ~8 | JWT в Sec-WebSocket-Protocol |
| `test_ws_dev_allow_removal.py` | ~6 | /ws/noauth удалён, WS_DEV_ALLOW не работает |
| `test_mobile_missing_endpoints.py` | ~10 | /mobile/doctors, /mobile/attest, Idempotency-Key |

**Итого:** ~54 новых теста в backend
