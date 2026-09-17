# Migration 0069 Production Application Runbook (Sentinel Pair Retirement)

## Purpose

- Apply `0069_sentinel_pair_retirement` to the production database exactly once, safely, and with recorded proof.
- Authority: merging PR #3315 does **NOT** authorize this application. The owner (operator) decides when to run this runbook. Merge of #3315 is a code gate, not a deployment gate.
- Scope: the production clinic host (Windows, `deploy_restart.ps1` toolchain) and every persistent staging contour. CI databases are ephemeral and do not count.

## Preconditions

- PR #3315 is merged into `main` with required CI green on the merge commit.
- A maintenance window is scheduled (the canonical deploy stops the backend runtime).
- The operator has access to the production host, the PostgreSQL superuser credentials, and the repository at the merge commit.

## Step 0 — Confirm no database has 0069 applied (mandatory gate)

For EVERY persistent staging/production database:

```sql
SELECT version_num FROM alembic_version;
```

- The result MUST NOT contain `0069_sentinel_pair_retirement` anywhere.
- Expected production state: `0067_daily_queue_start_number_snapshot` (the 2026-09-16 deploy applied 0064-0067) or `0068_direction_public_address` if that migration was already deployed separately. Anything else — STOP and investigate before proceeding.
- Record the output per environment. If ANY persistent database already reports 0069 — STOP, escalate to the owner with the inventory, do not proceed.

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

## Step 6 — Close out

- Record the application in `.ai-factory/plans/registrar-queue-remediation/PROGRESS.md` (E-062 follow-up): date, outputs of Steps 0/2/4, deploy commit, smoke results.
- Declare **QD-2 / RQ-15 = FROZEN / DONE**.
- Freeze rule (owner decision, 2026-09-18): no new QD-2 hardening PRs without a production incident or a proven P0/P1.
- Idempotency note: a re-run of 0069 on an already-retired database is a clean no-op only when the terminal state is provable — this is by design and safe.
