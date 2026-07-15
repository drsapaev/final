# Epic M4 — Backend Security & Compliance

> **Статус:** Active epic (production blockers)
> **Создано:** 2026-07-15
> **Источник:** Architecture review после Patient Panel audit (PR #2300, #2304, #2308)
> **Приоритет:** P0 — блокирует production-deployment с реальными пациентами

---

## Контекст

После завершения 6 фронтенд-аудитов (Cashier, Registrar, Admin, Doctor, Lab, Patient) фокус смещается с UI-улучшений на серверную безопасность. Технические проблемы (god classes, синхронизация, DI) решены — теперь основные риски в PHI-доступе, авторизации, аудите и эксплуатационной готовности.

**Все выводы ниже основаны на проверке backend-кода, не на предположениях.** Конкретные файлы и строки указаны для каждого пункта.

---

## P0 — Production Blockers (до deployment с реальными пациентами)

### M4-P0-1 — PHI Audit Trail для patient-endpoints ✅ DONE

**Серьёзность:** P0 (регуляторное требование)
**Статус:** ✅ Реализовано (PR pending)
**Файлы:**
- `backend/app/models/patient_access_audit.py` (новый) — `PatientAccessAuditLog` model
- `backend/app/services/patient_access_audit.py` (новый) — `log_patient_access()` wrapper
- `backend/alembic/versions/0040_patient_access_audit.py` (новый) — migration
- `backend/app/api/v1/endpoints/telegram_webhook/_clinic_bot.py` — интеграция во все patient-endpoints
- `backend/app/api/v1/endpoints/telegram_webhook/_routes.py` — `request: Request` parameter added
- `backend/tests/unit/test_patient_access_audit.py` (новый) — 11 unit tests
- `backend/app/models/__init__.py` — model registration

**Текущее состояние:**
- `EMRAuditLog` model существует с полями: `emr_id`, `patient_id`, `visit_id`, `action`, `user_id`, `user_role`, `ip_address`, `user_agent`, `extra_data`, `timestamp`
- Используется **только** для doctor/staff доступа к EMR
- Patient-access endpoints (`/cabinet/summary`, `/forms/preview`, `/reports/download`) **не пишут в audit log вообще**
- grep `EMRAuditLog` по `telegram_webhook/` → 0 совпадений

**Что нужно:**
1. Создать `PatientAccessAuditLog` model (или расширить `EMRAuditLog` с `actor_type: 'patient' | 'staff'`)
2. Поля (минимум):
   - `subject_patient_id` (чей PHI)
   - `actor_patient_id` (кто доступается — для guardian/heir отличается от subject)
   - `actor_type` (`self` | `guardian` | `heir` | `staff`)
   - `resource_type` (`lab_report` | `cabinet_summary` | `form_submission` | `appointment`)
   - `resource_id`
   - `action` (`view` | `download` | `submit` | `create`)
   - `outcome` (`success` | `denied` | `error`)
   - `ip_address`, `user_agent`
   - `session_id` / `correlation_id`
   - `timestamp` (timezone-aware)
3. Wrapper-функция `log_patient_access(db, scope, resource_type, resource_id, action, outcome, request)` — вызывается из каждого patient-endpoint
4. Endpoint для пациента: `GET /patients/audit-log` — просмотр собственной истории доступа
5. Endpoint для админа: `GET /admin/audit/patient-access` — фильтрация по patient/actor/date
6. **Immutable storage** — append-only, no UPDATE/DELETE (DB-level constraint + app-level guard)

**Сложность:** Medium (6-8 часов: model + migration + wrapper + 3 endpoint-интеграции + 2 новых endpoints)
**Блокирует:** Регуляторное соответствие (HIPAA-like, Закон РУз о персональных данных)

---

### M4-P0-2 — Переход на JWT после initData verification ✅ DONE

**Серьёзность:** P0 (security)
**Статус:** ✅ Реализовано (PR pending)
**Файлы:**
- `backend/app/services/telegram_mini_app_init_data.py:556` — `validate_telegram_mini_app_init_data` (HMAC ✅, auth_date ✅, replay ❌, JWT issuance ❌)
- `backend/app/services/telegram_mini_app_init_data.py:20` — `DEFAULT_MAX_AUTH_AGE_SECONDS = 24 * 60 * 60` (24 часа — недопустимо)
- `frontend/src/components/patient/patientUtils.js` — `readTelegramMiniAppInitData()` (отправляется с каждым запросом)

**Текущее состояние:**
```
Каждый patient-request:
  frontend → POST /telegram/mini-app/* { initData: "..." }
  backend → validate_telegram_mini_app_init_data(initData)
         → HMAC verify ✅
         → auth_date <= 24h ✅
         → resolve scope (telegram_user_id → patient_id)
         → выполнить запрос
  (initData отправляется снова при следующем запросе)
```

**Проблемы:**
1. **Replay protection отсутствует** — один initData можно переиспользовать 1000 раз за 24 часа
2. **Окно 24 часа** — недопустимо для PHI-доступа (industry standard: 15-30 минут)
3. **initData в каждом request** — если XSS утечёт initData, атакующий имеет окно 24 часа
4. **Нет JWT** — backend не выдаёт short-lived token после verification

**Что нужно (целевая схема):**
```
POST /telegram/mini-app/auth/exchange { initData }
  → validate_telegram_mini_app_init_data(initData)
  → HMAC verify + auth_date <= 5 min
  → replay check (Redis: seen initData hashes within 5 min)
  → resolve scope
  → issue JWT (15 min, httpOnly cookie или Authorization header)
  → issue refresh token (httpOnly cookie, 7 days)
  → return { access_token, expires_in }

Все последующие запросы:
  frontend → Authorization: Bearer <JWT>
  backend → verify JWT (signature + expiry)
  → выполнить запрос
  (initData больше не отправляется)
```

**Конкретные шаги:**
1. Новый endpoint: `POST /telegram/mini-app/auth/exchange` — принимает initData, выдаёт JWT + refresh
2. Сократить `DEFAULT_MAX_AUTH_AGE_SECONDS` с `24 * 60 * 60` до `5 * 60` (5 минут)
3. Replay protection: Redis SET с initData-hash, TTL=5min, reject if exists
4. JWT claims: `{ sub: patient_id, scope: "patient", telegram_user_id, exp, iat, jti }`
5. Refresh token: `UserSession` model (уже существует, `backend/app/models/authentication.py:92`)
6. Frontend: `useTelegramAuth()` hook — exchange initData → JWT → store → attach to requests
7. Frontend: убрать initData из всех patient-API-calls, заменить на JWT
8. Backward compat: в переходный период принимать и initData, и JWT (с deprecation warning)

**Сложность:** High (12-16 часов: backend endpoint + JWT infrastructure + Redis + frontend hook + migration всех patient-endpoints)
**Блокирует:** Security baseline для PHI-доступа

---

### M4-P0-3 — Session fixation protection ✅ DONE

**Серьёзность:** P0 (security)
**Статус:** ✅ Реализовано (PR pending)
**Файлы:**
- `backend/app/services/auth_svc/_tokens.py:291-314` — обычный login создаёт новую сессию, **не отзывает старые**
- `backend/app/services/auth_svc/_tokens.py:372-387` — refresh-token reuse detection существует (✅), но только для refresh, не для login
- `backend/app/api/v1/endpoints/telegram_webhook/_clinic_bot.py` — mini-app endpoints не используют `UserSession` вообще

**Текущее состояние:**
- `UserSession` model существует (`backend/app/models/authentication.py:92`) с `revoked` flag
- Refresh-token reuse detection работает: если refresh-token переиспользован → все сессии user'а revoked
- **Но:** новый login (password или Telegram) **не отзывает** существующие active sessions
- Mini-app endpoints вообще не создают `UserSession` — stateless initData-replay

**Что нужно:**
1. При успешном login (password): опционально revoke всех существующих active sessions для user_id (configurable: `revoke_on_new_login: true`)
2. При Telegram initData → JWT exchange (M4-P0-2): создать `UserSession` с `actor_type='patient'`, `telegram_user_id`, `ip`, `user_agent`
3. При повторном exchange: revoke предыдущей patient-session для того же telegram_user_id
4. Endpoint `POST /auth/revoke-all-sessions` — patient может отозвать все свои сессии (например, если телефон украден)
5. Endpoint `GET /patients/sessions` — patient видит свои активные сессии (IP, user_agent, last_activity, created_at)

**Сложность:** Medium (4-6 часов)
**Блокирует:** Защита от session fixation + "отвязать устройство" feature

---

## P1 — Architecture (после P0)

### M4-P1-1 — Единый ABAC / Policy Layer ✅ DONE

**Серьёзность:** P1 (architecture)
**Статус:** ✅ Реализовано (PR pending)
**Файлы:**
- `backend/app/api/v1/endpoints/telegram_webhook/_clinic_bot.py:1211-1219` — локальная ABAC-проверка `LabReportInstance.patient_id == scope.patient_id` (только для report-download)
- `backend/app/api/v1/endpoints/telegram_webhook/_clinic_bot.py:1152-1154` — локальная проверка для cabinet-summary
- Остальные endpoints — проверка разбросана или отсутствует

**Текущее состояние:**
- `require_telegram_mini_app_patient_scope(scope, patient_id=...)` — проверяет `scope.patient_id == patient_id` (RBAC + resource-ownership)
- Но это **точечные проверки** в каждом endpoint, а не единый policy layer
- Нет centralized authorization — правила копируются

**Что нужно:**
1. Создать `backend/app/services/authorization/` package
2. `AuthorizationService.can_access_patient PHI(scope, patient_id, action, resource_type, resource_id) → bool`
3. Policy rules в одном месте:
   - `self`: `scope.patient_id == patient_id` → allow
   - `guardian`: `scope.patient_id in guardians(patient_id)` → allow (M4-P1-3)
   - `heir`: `scope.patient_id in heirs(patient_id)` → allow with restrictions
   - `staff`: `scope.staff_role in allowed_roles` → allow
4. Dependency: `Depends(require_phi_access(patient_id, action, resource_type))` — wrapper для всех patient-endpoints
5. Тесты: для каждой policy-rule — unit test на allow/deny

**Сложность:** Medium (6-8 часов)
**Блокирует:** Systematic authorization (сейчас — точечные проверки)

---

### M4-P1-2 — Replay protection (временная мера до полного отказа от initData) ✅ DONE

**Серьёзность:** P1 (если M4-P0-2 отложен)
**Статус:** ✅ Реализовано в M4-P0-2 (PR #2331)
**Файлы:**
- `backend/app/services/telegram_mini_app_init_data.py:556-601` — `validate_telegram_mini_app_init_data`

**Текущее состояние:**
- HMAC verify ✅
- auth_date check ✅
- **Replay protection: ❌** — один initData можно использовать N раз за 24 часа

**Что нужно (если M4-P0-2 отложен):**
1. Redis SET `initData:{hash(initData)}` с TTL=5min при каждой verification
2. Если key exists → reject с `reason: "init_data_replayed"`
3. Добавить `replay_check` parameter в `validate_telegram_mini_app_init_data`
4. Тест: replay same initData → 403

**Примечание:** Если M4-P0-2 реализован (JWT после exchange), этот пункт становится не нужен — initData используется один раз при exchange, дальше работает JWT.

**Сложность:** Low (2-3 часа, при условии что Redis уже настроен)
**Блокирует:** Mitigation XSS-initData-leak window

---

### M4-P1-3 — Context Roles (guardian / heir / caregiver) ✅ DONE

**Серьёзность:** P1 (feature)
**Статус:** ✅ Реализовано (PR pending)
**Файлы:**
- `backend/app/services/telegram_mini_app_init_data.py:515-530` — `_patient_scope` всегда возвращает `scope.patient_id = telegram_user.patient_id` (только self)
- `backend/app/models/telegram_config.py:150-154` — `TelegramUser.patient_id` (один patient_id, нет guardian/heir relations)

**Текущее состояние:**
- `TelegramUser.patient_id` — 1:1 связь (один Telegram → один patient)
- Нет модели guardian/heir/caregiver
- Patient не может видеть записи ребёнка, родственника

**Что нужно:**
1. Новая model: `PatientRelationship` (parent_patient_id, child_patient_id, relationship_type: `guardian` | `heir` | `caregiver`, permissions: JSON, valid_from, valid_to)
2. Расширить `TelegramMiniAppSessionScope`: `actor_type: 'self' | 'guardian' | 'heir'`, `subject_patient_id` (отличается от actor_patient_id для guardian)
3. `_patient_scope` — возвращать список доступных subject_patient_ids (self + guardians + heirs)
4. Authorization layer (M4-P1-1) — проверять relationship для non-self access
5. Frontend: UI для переключения "Чьи записи вы просматриваете?" (self / ребёнок / родственник)
6. Admin endpoint: управление relationships (назначение guardian, отзыв)

**Сложность:** High (10-12 часов: model + migration + scope-logic + authorization + frontend + admin)
**Блокирует:** Multi-patient access (родитель → ребёнок)

---

### M4-P1-4 — WebAuthn / Passkeys (альтернативный вход)

**Серьёзность:** P1 (resilience)
**Файлы:** новый functionality

**Текущее состояние:**
- Telegram Mini App — единственный способ patient-входа
- Нет web-login fallback
- Парольной аутентификации для patients нет (только для staff)

**Что нужно:**
1. Backend: `POST /auth/webauthn/register/begin`, `POST /auth/webauthn/register/finish`, `POST /auth/webauthn/login/begin`, `POST /auth/webauthn/login/finish`
2. Model: `PasskeyCredential` (user_id, credential_id, public_key, sign_count, transports, created_at, last_used_at)
3. Frontend: registration flow (biometric prompt) + login flow
4. Связь с Patient: patient регистрирует passkey после первого Telegram-входа (bootstrap)
5. Recovery: если passkey потерян + Telegram потерян → Emergency Recovery (M4-P2-1)

**Сложность:** High (12-16 часов: WebAuthn library + backend + frontend + testing)
**Блокирует:** Альтернативный вход (resilience)

---

## P2 — Compliance & Recovery

### M4-P2-1 — Emergency Recovery Flow

**Серьёзность:** P2 (resilience)
**Файлы:** новый functionality

**Сценарий:** Patient потерял и Telegram, и passkey → нужна запись для завтрашней операции.

**Что нужно:**
1. Admin endpoint: `POST /admin/emergency-access` — принимает patient_id, verification_method (`passport` | `video_call` | `in_person`), verification_notes
2. Выдаёт emergency-token (15 min, один конкретный resource: report_id или cabinet-summary)
3. Token одноразовый (jti в Redis, delete on use)
4. Audit log: `action: 'emergency_access_granted'`, `actor: admin_id`, `subject: patient_id`, `verification_method`, `verification_notes`
5. Frontend: admin UI для выдачи emergency-token
6. Patient получает token через SMS/email/call, открывает `/emergency?token=...`

**Сложность:** Medium (6-8 часов)
**Блокирует:** Recovery при потере всех факторов

---

### M4-P2-2 — Управление сессиями (patient-facing)

**Серьёзность:** P2 (UX + security)
**Файлы:** новый functionality (зависит от M4-P0-2, M4-P0-3)

**Что нужно:**
1. `GET /patients/sessions` — список активных сессий пациента (device, ip, location, last_activity)
2. `POST /patients/sessions/{id}/revoke` — отозвать конкретную сессию
3. `POST /patients/sessions/revoke-all` — отозвать все кроме текущей
4. `POST /patients/telegram/unlink` — отвязать Telegram (требует passkey или emergency-token)
5. Frontend: "Безопасность" tab в PatientPanel с историей входов и управлением сессиями

**Сложность:** Medium (4-6 часов)
**Блокирует:** Self-service security management

---

### M4-P2-3 — Security integration tests

**Серьёзность:** P2 (verification)
**Файлы:** новый test suite

**Что нужно:**
1. Replay test: один initData → 2 запроса → второй должен быть 403
2. Authorization bypass test: patient A пытается доступ к patient B → 403
3. Audit generation test: каждый PHI-доступ → audit log entry с правильными полями
4. Session fixation test: login → login → первая сессия revoked
5. JWT expiry test: expired JWT → 401
6. Emergency token: одноразовость → 2 использования → второй 403
7. Guardian access: guardian пытается доступ к non-guardian patient → 403

**Сложность:** Medium (6-8 часов)
**Блокирует:** Confidence в security-implementation

---

## Sprint Planning

### Sprint 0 (Hotfix — до production, 1-2 дня)
- [ ] M4-P0-1: PHI Audit Trail (минимум для report-download + cabinet-summary)
- [ ] M4-P0-2: JWT после initData (сократить max_age до 5 min + replay protection)
- [ ] M4-P0-3: Session fixation (revoke on new login)

### Sprint 1 (1 неделя)
- [ ] M4-P0-1: Полный audit trail (все patient-endpoints + patient-facing audit endpoint)
- [ ] M4-P0-2: Полный JWT transition (frontend hook + migration всех endpoints)
- [ ] M4-P1-1: ABAC / Policy Layer
- [ ] M4-P1-2: Replay protection (если ещё нужен после P0-2)

### Sprint 2 (1 неделя)
- [ ] M4-P1-3: Context Roles (guardian/heir)
- [ ] M4-P1-4: WebAuthn / Passkeys
- [ ] M4-P2-2: Session management UI

### Sprint 3 (1 неделя)
- [ ] M4-P2-1: Emergency Recovery
- [ ] M4-P2-3: Security integration tests
- [ ] Hardening: rate limiting, IP-geolocation anomalies, adaptive MFA

---

## Метрики готовности

| Метрика | Сейчас | Цель после M4 |
|---------|--------|---------------|
| PHI-доступы в audit log | 0% | 100% |
| initData окно действия | 24h | 5min (одноразово) |
| Replay protection | ❌ | ✅ |
| JWT short-lived | ❌ | ✅ (15 min) |
| Session fixation protection | partial (refresh-reuse only) | ✅ (login revoke) |
| ABAC centralized | ❌ (точечные проверки) | ✅ (policy layer) |
| Context roles | ❌ (только self) | ✅ (self/guardian/heir) |
| Альтернативный вход | ❌ (только Telegram) | ✅ (WebAuthn) |
| Emergency recovery | ❌ | ✅ |
| Security integration tests | ❌ | ✅ (7 scenarios) |

---

## Связанные документы

- `docs/audit/deferred-backlog.md` — frontend deferred items (DEFER-002 до DEFER-007)
- Patient Panel audit: PRs #2300, #2304, #2308
- Lab Panel audit: PRs #2293, #2294, #2295
- Doctor Panel audit: PRs #2287-#2292

---

## Источник фактов (backend code references)

Все утверждения в этом эпике проверены по коду:

- `backend/app/services/telegram_mini_app_init_data.py:20` — `DEFAULT_MAX_AUTH_AGE_SECONDS = 24 * 60 * 60`
- `backend/app/services/telegram_mini_app_init_data.py:556-601` — `validate_telegram_mini_app_init_data` (HMAC ✅, auth_date ✅, replay ❌)
- `backend/app/services/telegram_mini_app_init_data.py:515-530` — `_patient_scope` (только self, 1:1)
- `backend/app/models/telegram_config.py:144-184` — `TelegramUser` (1:1 patient_id)
- `backend/app/models/emr_v2.py:235-291` — `EMRAuditLog` (существует, не используется для patient-access)
- `backend/app/api/v1/endpoints/telegram_webhook/_clinic_bot.py:1188-1241` — report-download (нет audit log)
- `backend/app/api/v1/endpoints/telegram_webhook/_clinic_bot.py:1211-1219` — ABAC check (локальный, не centralized)
- `backend/app/models/authentication.py:92-122` — `UserSession` (существует, mini-app не использует)
- `backend/app/services/auth_svc/_tokens.py:291-314` — login (не revoke старые сессии)
- `backend/app/services/auth_svc/_tokens.py:372-387` — refresh-token reuse detection (✅, но не для login)
