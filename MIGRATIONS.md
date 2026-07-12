# MIGRATIONS — стратегия без потери данных

## Baseline (2026-02-11)
- Clean baseline migration is `backend/alembic/versions/0001_baseline.py`.
- Legacy migrations moved to `archives/alembic_versions_legacy` for reference only.
- Fresh Postgres bootstrap: `alembic upgrade head`.
- Existing DB that already matches schema: verify, then `alembic stamp 0001_baseline`.

## B.1 (2025-08-17): Индексы производительности
...

## B.2 (2025-08-17): Аудит и подготовка к ограничениям
...

## B.3 (2025-08-17..18): Ужесточение ограничений
### B.3.1 (2025-08-17): FOREIGN KEY с `ON DELETE SET NULL`
...

### B.3.2 (2025-08-18): NOT NULL hardening
...

### B.3.2a (2025-08-18): Выравнивание целей
Цель: согласовать фактическую схему с целями B.3.2.
- `activations.active` → **актуально** `activations.status` (NOT NULL).
- `schedules.*` — таблицы нет, шаг пропущен.

Миграция: `backend/alembic/versions/20250818_0005_not_null_alignment.py`  
Команды:
```bash
cd backend
alembic upgrade head
Откат:
alembic downgrade 20250818_0004
```

## 2026-07-10 — Audit Remediation Migrations (PR-1 to PR-22)

Three new migrations added during the audit remediation sprint:

### 0037_patient_medical_fields (PR-1)
- Adds `emergency_contact` (String(64)), `allergies` (Text), `chronic_conditions` (Text) to `patients` table
- Backs the mobile_api_extended.py profile endpoints

### 0038_user_fcm_fields (PR-2)
- Adds `device_type` (String(20)), `device_info` (JSON), `push_notifications_enabled` (Boolean default false) to `users` table
- Backs the FCM token registration endpoints

### 0039_feature_flags (PR-8 fixup)
- Creates `feature_flags` table (id, key, name, description, enabled, config JSONB, category, environment)
- Creates `feature_flag_history` table (id, flag_key, action, old_value, new_value, changed_by, changed_at)
- The `FeatureFlag` and `FeatureFlagHistory` models existed in `app/models/feature_flags.py` but were never registered in `app/models/__init__.py`, so Alembic never created the tables. This blocked the AI safety CI job.

```bash
cd backend
alembic upgrade head   # applies 0037, 0038, 0039
alembic current        # should show 0039_feature_flags
```

Откат:
```bash
alembic downgrade 0036_chat_encryption
```
