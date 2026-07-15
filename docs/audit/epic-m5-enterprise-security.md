# Epic M5 — Enterprise Security

> **Статус:** Active epic (cross-cutting security for all roles)
> **Создано:** 2026-07-15
> **Источник:** Architecture review после завершения Epic M4 (Patient Portal Security)
> **Приоритет:** P1 — систематизация безопасности для production-ready

---

## Контекст

Epic M4 (Patient Portal Security) завершил security-улучшения для patient-facing
подсистемы. Однако внутренняя клиническая система (Cashier, Registrar, Admin,
Doctor, Lab) использует scattered authorization checks и фрагментированный
audit trail.

Epic M5 фокусируется на **сквозных механизмах**, которые работают одинаково
для всех ролей и всех эндпоинтов. В отличие от M4, здесь нет patient-specific
функций (guardian/heir, WebAuthn, emergency recovery) — эти остаются в
Patient Portal track.

**Принцип:** Threat model для staff (внутренние пользователи, trusted network,
admin oversight) отличается от threat model для patients (внешние пользователи,
untrusted network, self-service). Решения не должны копироваться механически.

---

## Архитектурные решения

### 1. Единый AuditLog (вместо EMRAuditLog + PatientAccessAuditLog)

**Проблема:** Сейчас два audit log'а:
- `EMRAuditLog` — doctor/staff доступ к EMR
- `PatientAccessAuditLog` — patient доступ к собственному PHI (M4-P0-1)

Аудиторы хотят видеть единый журнал. Две таблицы = сложно собрать картину.

**Решение:** Единый `AuditLog` с `event_type` enum:
```
PATIENT_LOGIN | PATIENT_REPORT_DOWNLOAD | PATIENT_FORM_SUBMIT
DOCTOR_OPEN_EMR | DOCTOR_EDIT_DIAGNOSIS | DOCTOR_PRESCRIBE
REGISTRAR_EDIT_PATIENT | REGISTRAR_CREATE_APPOINTMENT
ADMIN_EXPORT | ADMIN_CREATE_USER | ADMIN_CHANGE_ROLE
LAB_RESULT_VIEW | LAB_REPORT_FINALIZE
CASHIER_PAYMENT_EDIT | CASHIER_REFUND
SESSION_REVOKE | EMERGENCY_TOKEN_ISSUED
```

**Миграция:**
- Создать `audit_logs` таблицу (универсальная)
- Мигрировать данные из `emr_audit_logs` и `patient_access_audit_logs`
- Deprecate старые таблицы (keep for backward compat, stop writing)

### 2. Единый AuthorizationService для всех эндпоинтов

**Проблема:** `AuthorizationService` (M4-P1-1) создан, но интегрирован только
в 2 patient-endpoint'а. Staff-эндпоинты используют:
```python
if user.role == "doctor":  # ❌ inline RBAC
if appointment.doctor_id != current_user.id:  # ❌ inline ownership check
```

**Решение:** Все эндпоинты используют:
```python
authorization_service.can_access_phi(scope, ...)
authorization_service.can_edit_emr(scope, ...)
authorization_service.can_download_report(scope, ...)
```

### 3. Sensitive Action Logging

Не каждый PHI-view логируется, а только **чувствительные действия**:
- Изменение диагноза
- Изменение назначения
- Удаление анализа
- Выдача рецепта
- Смена роли пользователя
- Создание/удаление пользователя
- Экспорт данных
- Массовые операции

### 4. Reason Codes

Каждая audit-запись содержит `reason_code` — почему было выполнено действие:
```
doctor opened patient EMR because consultation #5832
registrar edited patient because appointment #4471
admin exported data because monthly_report_july_2026
```

---

## Задачи

### M5.1 — Unified AuditLog

**Серьёзность:** P1
**Сложность:** Medium (8-10h)

- Создать `AuditLog` model (универсальная, с `event_type` enum)
- Migration: создать `audit_logs` + мигрировать данные из `emr_audit_logs` + `patient_access_audit_logs`
- Wrapper: `log_audit_event(db, event_type, actor, subject, resource, action, outcome, reason_code, request)`
- Deprecate `EMRAuditLog` и `PatientAccessAuditLog` (keep for read-only backward compat)
- Интегрировать во все sensitive endpoints

### M5.2 — Central Authorization для всех эндпоинтов

**Серьёзность:** P1 (★★★★★ приоритет)
**Сложность:** Medium (6-8h)

- Расширить `AuthorizationService` с methods:
  - `can_read_patient(scope, patient_id)`
  - `can_edit_patient(scope, patient_id)`
  - `can_edit_emr(scope, emr_id)`
  - `can_download_report(scope, report_id)`
  - `can_manage_users(scope)`
  - `can_export_data(scope)`
- Заменить все inline `if user.role ==` проверки на `AuthorizationService` calls
- Интегрировать во все staff-эндпоинты (Cashier, Registrar, Admin, Doctor, Lab)
- Тесты: для каждой role × action → allow/deny

### M5.3 — Sensitive Action Logging

**Серьёзность:** P1
**Сложность:** Medium (6-8h)

- Определить список sensitive actions:
  - `DIAGNOSIS_CHANGE`, `PRESCRIPTION_ISSUE`, `PRESCRIPTION_CANCEL`
  - `LAB_RESULT_DELETE`, `LAB_REPORT_FINALIZE`
  - `USER_CREATE`, `USER_DELETE`, `USER_ROLE_CHANGE`
  - `DATA_EXPORT`, `BULK_OPERATION`
  - `PAYMENT_EDIT`, `REFUND_ISSUE`
- Интегрировать `log_audit_event()` во все endpoints, выполняющие эти действия
- Каждый log entry содержит `reason_code` (consultation_id, appointment_id, etc.)

### M5.4 — Reason Codes

**Серьёзность:** P2
**Сложность:** Low (3-4h)

- Добавить `reason_code` field в `AuditLog` (optional, nullable)
- Формат: `{ "context": "consultation", "id": 5832 }` или `{ "context": "appointment", "id": 4471 }`
- Интегрировать в все sensitive action endpoints
- Endpoint: `GET /admin/audit/reasons` — справочник reason contexts

### M5.5 — Immutable Audit

**Серьёзность:** P1 (compliance)
**Сложность:** Low (2-3h)

- DB-level: `REVOKE UPDATE, DELETE ON audit_logs FROM app_user`
- App-level: guard в model — raise на attempt to update/delete
- Trigger: `BEFORE UPDATE OR DELETE ON audit_logs → RAISE EXCEPTION`
- Migration: add trigger
- Test: attempt to UPDATE/DELETE → error

### M5.6 — Security Dashboard

**Серьёзность:** P2
**Сложность:** Medium (6-8h)

- `GET /admin/security/dashboard` — агрегированный view:
  - Последние 20 входов (staff + patient)
  - Последние 20 скачиваний PDF
  - Последние 20 экспортов
  - Неудачные логины (за 24h)
  - Заблокированные попытки
  - Подозрительные IP (multiple failed logins)
  - Массовые операции (bulk exports, bulk deletes)
- Frontend: AdminPanel → "Безопасность" tab
- Фильтры: по дате, по роли, по action type

### M5.7 — Rate Limiting

**Серьёзность:** P2
**Сложность:** Medium (4-6h)

- FastAPI middleware: `slowapi` или custom
- Лимиты для sensitive endpoints:
  - Login: 5 attempts / 5 min per IP
  - Report download: 10 / min per user
  - Data export: 3 / hour per user
  - Password reset: 3 / hour per IP
- 429 Too Many Requests response
- Audit log: rate-limited requests logged with `event_type=RATE_LIMITED`

### M5.8 — Secrets Rotation

**Серьёзность:** P2
**Сложность:** Medium (4-6h)

- `SECRET_KEY` rotation: support multiple valid keys (current + previous)
- `JWT_SECRET` rotation: same pattern
- Telegram bot token rotation: endpoint to update without restart
- API keys rotation: per-service key management
- Documentation: rotation schedule (quarterly)
- Audit log: `event_type=SECRET_ROTATED`

### M5.9 — Backup Audit

**Серьёзность:** P2
**Сложность:** Low (2-3h)

- Endpoint: `POST /admin/backup/verify` — verify latest backup is restorable
- Endpoint: `GET /admin/backup/status` — last backup timestamp, size, status
- Scheduled job: weekly backup restore test (restore to temp DB, verify schema)
- Audit log: `event_type=BACKUP_VERIFIED` or `BACKUP_FAILED`
- Alert: if last backup > 24h old → admin notification

### M5.10 — Compliance Report

**Серьёзность:** P2
**Сложность:** Low (3-4h)

- `GET /admin/compliance/report` — automated checklist:
  - Audit logging enabled ✅/❌
  - HTTPS enabled ✅/❌
  - Encryption at rest ✅/❌
  - Backups OK ✅/❌
  - Migrations up to date ✅/❌
  - 2FA enforced for critical roles ✅/❌
  - Rate limiting active ✅/❌
  - Secrets rotated within 90 days ✅/❌
- Frontend: AdminPanel → "Compliance" tab
- Export: PDF report for auditors

---

## Sprint Planning

### Sprint 1 (1 неделя)
- [ ] M5.1: Unified AuditLog (model + migration + wrapper)
- [ ] M5.2: Central Authorization (★★★★★ — highest priority)
- [ ] M5.5: Immutable Audit (trigger + guard)

### Sprint 2 (1 неделя)
- [ ] M5.3: Sensitive Action Logging
- [ ] M5.4: Reason Codes
- [ ] M5.7: Rate Limiting

### Sprint 3 (1 неделя)
- [ ] M5.6: Security Dashboard
- [ ] M5.8: Secrets Rotation
- [ ] M5.9: Backup Audit
- [ ] M5.10: Compliance Report

---

## Что НЕ входит в Epic M5

Следующие задачи остаются в Patient Portal track (Epic M4, завершён):
- WebAuthn для staff — не нужен (password + 2FA достаточно)
- Emergency recovery для staff — не нужен (admin reset)
- Guardian/heir/caregiver — patient-only concept
- Patient session management UI — patient-only
- Telegram initData JWT exchange — patient-only auth method

---

## Метрики готовности

| Метрика | Сейчас | Цель после M5 |
|---------|--------|---------------|
| Единый audit log | 2 таблицы (fragmented) | 1 таблица (unified) |
| Authorization centralized | 2/20+ endpoints | 100% endpoints |
| Sensitive actions logged | ~30% | 100% |
| Reason codes | ❌ | ✅ (all sensitive actions) |
| Immutable audit | app-level only | DB trigger + app guard |
| Security dashboard | ❌ | ✅ (admin-facing) |
| Rate limiting | ❌ | ✅ (sensitive endpoints) |
| Secrets rotation | manual | documented + automated |
| Backup verification | manual | automated weekly |
| Compliance report | manual checklist | automated endpoint |

---

## Связанные документы

- `docs/audit/epic-m4-backend-security.md` — Patient Portal Security (завершён)
- `docs/audit/deferred-backlog.md` — frontend deferred items
