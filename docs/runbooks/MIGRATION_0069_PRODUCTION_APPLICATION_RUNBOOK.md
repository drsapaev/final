# Migration 0069 Production Application Runbook (Sentinel Pair Retirement)

## Status: COMPLETED / VERIFIED — 2026-09-18

```text
Status: COMPLETED / VERIFIED — 2026-09-18

Applied implementation: PR #3324 (merged)
Merge SHA: 6d35eb0c675fb7e2020acf3c37fbf4df43f6e797
PR #3315: closed as superseded; hardening incorporated into #3324
Production version: 0069_sentinel_pair_retirement

Backup artifact (review fix 2026-09-18: verified-факты отделены от
operator-confirmed/required-policy; автоматические BackupService
retention/R2 guarantees этому .dump НЕ приписываются):

  Verified (repo code + owner-confirmed record):
  - file:     backup_pre_0069_fixed_20260918_162405.dump
  - SHA256:   F53B479D2607C4836B7E8B9DA6DAC5D376FC86E5547D3DF1FE34281D83C90DAF
  - результат применения к production — postchecks ниже в этом блоке
  - артефакт НЕ управляется автоматическим retention/R2-pipeline репо:
    ops/vps/scripts/backup_db.py (pg_dump -F c → *.dump в BACKUP_DIR) не
    выполняет retention-cleanup и не вызывает r2_uploader; BackupService
    (BACKUP_RETENTION_DAYS=30 / MAX_BACKUPS=100) чистит только
    backup_*.db* (glob этот .dump не покрывает — подстроки .db в имени
    нет) и загружает в R2 только собственные create_backup()-артефакты
    (backup_<type>_<ts>.db[.gz])
  - r2_uploader выполняет только PutObject + HeadObject с sha256-верификацией;
    Delete/List-операций в коде uploader'а НЕТ — это факт о коде, а не
    доказательство неспособности R2-токена к Delete/List

  Operator-confirmed / must verify separately (этой записью не подтверждено):
  - точный локальный путь (канонические BACKUP_DIR: /opt/clinic/output/backups
    — ops/vps/clinic_lifecycle.env.sample; <app-root>/output/backups —
    default backup_db.py)
  - фактические filesystem ACL (ожидание: только владелец/оператор,
    суперпользователь production-хоста)
  - скопирован ли именно этот .dump в R2 — автоматически этого не произошло
  - R2 object key + совпадающий SHA256, если offsite-копия существует
  - явная дата удаления/retention именно для этого .dump

  Required policy (явное решение/действие, автоматикой не покрывается):
  - подтверждённое удаление из BACKUP_DIR (и из R2, если копия есть) после
    закрытия rollback-окна — решение владельца; дамп содержит PII
    users/doctors, бессрочное хранение запрещено

Postchecks (2026-09-18):
  alembic_version = 0069
  sentinel users = 0
  sentinel-linked doctors = 0
  ACTIVE userless bridge doctors = 0

QD-2 / RQ-15 = FROZEN / DONE с 2026-09-18
```

Всё ниже статус-блока — **историческая / переиспользуемая процедурная запись** (review fix, 2026-09-18). Не выполнять повторно против уже migrated production. Процедура применима только к средам из списка: production — migrated (VERIFIED, эта запись); остальные persistent-контуры — сверка Step 0 перед любым применением; CI-базы эфемерны и средами для этой процедуры не являются. Если все persistent-среды на 0069 — процедура нигде не применима.

## Purpose

- Зафиксировать применение `0069_sentinel_pair_retirement` к production-БД: ровно один раз, безопасно, с записанным пруфом (завершено 2026-09-18 — см. статус-блок).
- Authority: merge PR **НЕ** авторизует применение. Исходный кандидат #3315 закрыт как superseded; в main вошла unified 0069 через #3324. Применение — отдельное операторское решение владельца: merge — код-гейт, не deployment-гейт.
- Scope: production-хост клиники (Windows, `deploy_restart.ps1` toolchain) и каждый persistent staging-контур. CI-базы эфемерны и не считаются.

## Preconditions

- Unified `0069` в `main`: #3315 закрыт как superseded → unified 0069 вошла через #3324 (squash `6d35eb0c6`), обязательный CI зелёный на merge-коммите.
- A maintenance window is scheduled (the canonical deploy stops the backend runtime).
- The operator has access to the production host, the PostgreSQL superuser credentials, and the repository at the merge commit.

## Step 0 — Per-target environment gate (mandatory)

The gate is evaluated **per target environment**, not "ANY persistent DB
anywhere" (review fix, 2026-09-18): production already reports 0069 (this
record), and that fact must not block the procedure for a lagging
persistent contour.

Inventory every persistent environment (production, every persistent
staging contour; CI bases are ephemeral and do not count) and record the
version per environment:

```sql
SELECT version_num FROM alembic_version;
```

Classification and the required action per environment:

- `0069_sentinel_pair_retirement` → **COMPLETED / SKIP** for that
  environment — do not re-run the procedure against it.
- `0067_daily_queue_start_number_snapshot` or
  `0068_direction_public_address` → eligible **TARGET** — the procedure
  (Steps 1–5) may proceed against exactly this environment. These are the
  expected pre-0069 states: `0067` (the 2026-09-16 deploy applied
  0064-0067) or `0068` if that migration was already deployed separately.
- Anything else → **STOP**, investigate, escalate to the owner with the
  full inventory before proceeding.

The procedure runs against exactly one TARGET per pass; environments
classified COMPLETED / SKIP are recorded in the inventory and are not
touched. Steps 1–5 below read "production" from the historical 2026-09-18
pass — when running against another eligible TARGET, substitute that target
environment throughout. If ALL persistent environments report `0069`, the
procedure is applicable nowhere (Steps 0–5 are archival-only).

## Step 1 — Backup (mandatory, before touching anything)

- Take a full backup / VM snapshot per [CLINIC_BACKUP_RESTORE_REHEARSAL_RUNBOOK.md](CLINIC_BACKUP_RESTORE_REHEARSAL_RUNBOOK.md).
- Verify restorability (a backup that was never restored is not a backup): run the restore rehearsal against an isolated target.

## Step 2 — Preflight (read-only, record outputs)

Run on the production database (all queries are read-only; the runtime may stay up):

```sql
-- (a) alembic head
SELECT version_num FROM alembic_version;

-- (b) the three 0055 sentinel pairs — standard production pre-state is 3 users / 3 linked doctors
SELECT u.username, u.id AS user_id, u.role, u.is_active, u.is_superuser,
       d.id AS doctor_id, d.specialty, d.active
FROM users u LEFT JOIN doctors d ON d.user_id = u.id
WHERE u.username IN ('ecg_resource','lab_resource','general_resource');

-- (c) ACTIVE userless bridge-specialty doctors — expected 0
--     (historical INACTIVE userless rows are legitimate clinical history and pass by design)
SELECT id, specialty, active
FROM doctors
WHERE user_id IS NULL AND active AND specialty IN ('ecg','lab','general');
```

- Record all three outputs — they are the baseline for the postcheck in Step 4.
- If (c) returns any rows — STOP: the migration will abort by design (Decision #13 violation — an ACTIVE userless doctor). Resolve per the abort inventory the migration prints, then re-run the preflight.
- Note: `login_attempts` rows referencing the sentinel users are anonymized (SET NULL) by design — the only allowed side surface.

## Step 3 — Canonical deploy (the only supported path)

From the repository root on the production host:

```powershell
scripts/deploy_restart.ps1 -Deploy
```

- The script stops and verifies the uvicorn listener ABSENT **before** any migration runs (commit d5e585861). This closes the migration's verification windows by deploy discipline — no concurrent runtime writers exist while 0069 holds its verdict; defense-in-depth: on PostgreSQL the migration itself takes `LOCK TABLE users, doctors IN SHARE ROW EXCLUSIVE MODE` for the whole verdict.
- `alembic upgrade head` applies `0068_direction_public_address` (if still pending) and then `0069_sentinel_pair_retirement`.
- A failed migration leaves the listener stopped — do not restart the runtime manually until the failure is resolved and understood.

## Step 4 — Postchecks (immediately after the deploy)

```sql
-- (a) version stamped
SELECT version_num FROM alembic_version;
-- expect exactly: 0069_sentinel_pair_retirement

-- (b) sentinel pairs gone
SELECT count(*) FROM users
WHERE username IN ('ecg_resource','lab_resource','general_resource');  -- expect 0
SELECT count(*) FROM doctors d JOIN users u ON d.user_id = u.id
WHERE u.username IN ('ecg_resource','lab_resource','general_resource');  -- expect 0

-- (c) no ACTIVE userless bridge doctors
SELECT count(*) FROM doctors
WHERE user_id IS NULL AND active AND specialty IN ('ecg','lab','general');  -- expect 0
```

- Runtime health: backend process up, admin login works, display board renders, call-next smoke passes.
- Functional smoke: the lab / ecg / procedures queue surfaces still route and serve (QueueResource rows themselves are untouched — only the synthetic User+Doctor pairs are deleted).
- The migration log lines with the per-pair inventory are the audit trail — save them with the record.

## Step 5 — Rollback (only on failure, owner decision)

- Preferred: restore the pre-deploy backup / snapshot per [CLINIC_BACKUP_RESTORE_REHEARSAL_RUNBOOK.md](CLINIC_BACKUP_RESTORE_REHEARSAL_RUNBOOK.md).
- Alternative: the 0069 downgrade is a TRUE inverse (restores the exact 0055+0057 shape, field-verified with a final postcondition) — valid for operator-verified states, but backup-restore remains the default.

## Step 6 — Close out (completed 2026-09-18)

- Применение зафиксировано в PROGRESS.md (E-063, PR #3326) и подтверждением владельца на PR #3323 (2026-09-18): postchecks — версия 0069, пары удалены, ноль ACTIVE userless bridge doctors (статус-блок выше); инцидент первого прогона (откат без изменений БД) и цепочка fix — в записи E-063.
- **QD-2 / RQ-15 = FROZEN / DONE с 2026-09-18.**
- Freeze rule (решение владельца, 2026-09-18): никаких новых QD-2 hardening PR без production-инцидента или доказанного P0/P1.
- Idempotency note: повторный прогон 0069 на уже-retired БД — чистый no-op при доказуемом терминальном состоянии — это by design и безопасно.
