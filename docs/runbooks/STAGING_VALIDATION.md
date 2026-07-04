# Staging Validation Runbook

> **MANDATORY READING** for any agent or human claiming "the system works".
>
> **Status**: Active. Last updated: 2026-07-04.
> **Owner**: clinic dev team.
> **Trigger**: Before every production deploy, after major refactors, or when
> anyone asks "is the system working?".

---

## Why this runbook exists

Code passing CI ≠ system working. CI proves the code compiles and unit tests
pass. It does NOT prove:

- AI endpoints actually return safety metadata
- Feature flag toggles actually block endpoints
- Backup files actually restore
- Sentry actually receives events
- Telegram bot actually delivers messages
- arq worker actually processes jobs

This runbook closes that gap with **concrete commands and expected outputs**.
Run them. If any fails, the system is NOT working — fix it before claiming
otherwise.

**AI agents**: do not write "the system is working" or "deployment complete"
in any commit message, PR description, or chat response unless you have
executed the checks in this runbook AND they all passed. Hallucinating
"it works" is worse than admitting "I haven't verified".

---

## Prerequisites

Before running any check below:

1. **Staging is up** — `docker compose -f ops/compose.staging.yml up -d`
2. **Migrations applied** — `cd backend && alembic upgrade head`
3. **Env vars set** — at minimum `DATABASE_URL`, `SENTRY_DSN`, `SECRET_KEY`
4. **Test users seeded** — `python -m app.scripts.dev_seed --confirm-dev-seed`
   (creates admin/doctor/registrar with known passwords)

If any prerequisite fails, stop and fix it. The checks below assume a
running staging environment.

---

## Check 1 — Sentry smoke test (frontend + backend)

**Purpose**: prove Sentry is receiving events from both frontend and backend.

**Why it matters**: without Sentry, you have zero visibility into production
errors. Patients see white screens, you see nothing.

### Backend

```bash
cd backend
python -c "
import os
os.environ['SENTRY_DSN'] = 'https://65b5195082de2f0522c27dd6695536b7@o4511673323749376.ingest.us.sentry.io/4511673347670016'
os.environ['SENTRY_ENV'] = 'staging-validation-test'
from app.core.sentry import init_sentry, capture_exception
init_sentry()
try:
    raise RuntimeError('staging validation smoke test - backend')
except RuntimeError as e:
    capture_exception(e)
print('Sent. Check Sentry dashboard in 10 seconds.')
"
```

**Expected**: console prints `Sent. Check Sentry dashboard in 10 seconds.`
Within 10 seconds, Sentry dashboard (https://sentry.io) → Issues should
show a new `RuntimeError: staging validation smoke test - backend`.

### Frontend

After deploying to Vercel with `VITE_SENTRY_DSN` env var set:

1. Open production URL in browser
2. Open DevTools Console (F12)
3. Run: `setTimeout(() => { throw new Error("staging validation smoke test - frontend") }, 1000)`
4. Within 10 seconds, Sentry dashboard should show the new error

### If it fails

- **No event in Sentry**: check `SENTRY_DSN` env var is set correctly
- **Backend "sentry-sdk not installed"**: `pip install -r backend/requirements-monitoring.txt`
- **Frontend "VITE_SENTRY_DSN is undefined"**: env var not set in Vercel
- **Network error**: Sentry ingest URL blocked by firewall

See `docs/runbooks/SENTRY_SETUP.md` section 9 for full troubleshooting.

---

## Check 2 — DR drill (backup restore)

**Purpose**: prove backups actually restore. A backup you've never restored
is a wish, not a backup.

**Why it matters**: if staging burns tonight, you need to restore from
backup. If restore doesn't work, you lose all patient data.

### Run

```bash
cd backend

# Create a backup first (if none exists)
python -c "
from app.services.backup_service import BackupService
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import os
db = Session(create_engine(os.environ['DATABASE_URL']))
BackupService(db).create_backup(backup_type='validation_test')
print('Backup created.')
"

# Run the DR drill
python -m app.scripts.dr_drill

# Or with explicit backup file:
# BACKUP_FILE=/path/to/backup.dump python -m app.scripts.dr_drill
```

### Expected output

```
2026-07-04 12:00:00  INFO    dr_drill: Found 1 backup(s); using latest: backup_validation_test_20260704.db
2026-07-04 12:00:01  INFO    dr_drill: Dropping drill DB 'clinic_dr_drill' if exists...
2026-07-04 12:00:02  INFO    dr_drill: Creating fresh drill DB 'clinic_dr_drill'...
2026-07-04 12:00:03  INFO    dr_drill: Restoring backup_validation_test_20260704.db → clinic_dr_drill...
2026-07-04 12:00:10  INFO    dr_drill: Restore completed.
2026-07-04 12:00:10  INFO    dr_drill: Smoke testing restored DB...
2026-07-04 12:00:10  INFO    dr_drill:   users            → 5 rows
2026-07-04 12:00:10  INFO    dr_drill:   appointments     → 12 rows
2026-07-04 12:00:10  INFO    dr_drill:   services         → 8 rows
2026-07-04 12:00:10  INFO    dr_drill:   audit_log        → 47 rows
2026-07-04 12:00:10  INFO    dr_drill:   admin users      → 1
2026-07-04 12:00:11  INFO    dr_drill: ✅ Smoke test passed.
2026-07-04 12:00:11  INFO    dr_drill: Cleaning up drill DB 'clinic_dr_drill'...
2026-07-04 12:00:12  INFO    dr_drill: ✅ DR drill PASSED — backup is restorable.
```

Exit code 0 = pass. Exit code 1 = restore failed. Exit code 2 =
preconditions not met (no backup, no psql, etc.).

### If it fails

- **"pg_restore not found"**: install `postgresql-client` package
- **"ERROR: relation already exists"**: harmless warning (pg_restore --clean)
- **"Smoke test failed for tables: users"**: schema drift — run
  `alembic upgrade head` on the backup, then retry
- **"No admin user in restored DB"**: backup is incomplete; create admin
  before backing up

---

## Check 3 — AI feature flags kill-switch

**Purpose**: prove that toggling a feature flag actually blocks the endpoint.

**Why it matters**: if a misbehaving AI endpoint starts hallucinating
prescriptions, admin needs to kill it instantly without a code deploy. If
the kill-switch is broken, you can't stop the AI.

### Setup (one-time)

```bash
cd backend
python -m app.scripts.seed_ai_feature_flags
```

### Run

```bash
# Get admin token
ADMIN_TOKEN=$(curl -sS -X POST http://localhost:18000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin@clinic.com","password":"<admin password>"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Get doctor token
DOCTOR_TOKEN=$(curl -sS -X POST http://localhost:18000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"doctor@clinic.com","password":"<doctor password>"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Step 1: verify endpoint works with flag enabled
echo "=== Step 1: flag enabled, endpoint should return 200/422 ==="
curl -sS -o /dev/null -w "HTTP %{http_code}\n" \
  -X POST http://localhost:18000/api/v1/emr-ai-enhanced/generate-smart-template \
  -H "Authorization: Bearer $DOCTOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"specialty":"cardiology","patient_id":1,"visit_id":1}'
# Expected: HTTP 200 or HTTP 422 (validation error) — NOT 503

# Step 2: disable the flag
echo "=== Step 2: disabling ai_smart_template flag ==="
curl -sS -X POST http://localhost:18000/api/v1/admin/feature-flags/ai_smart_template/toggle \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"enabled":false,"reason":"validation test"}'
# Expected: 200 OK with {"key":"ai_smart_template","enabled":false,...}

# Step 3: verify endpoint now returns 503
echo "=== Step 3: flag disabled, endpoint should return 503 ==="
curl -sS -o /dev/null -w "HTTP %{http_code}\n" \
  -X POST http://localhost:18000/api/v1/emr-ai-enhanced/generate-smart-template \
  -H "Authorization: Bearer $DOCTOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"specialty":"cardiology","patient_id":1,"visit_id":1}'
# Expected: HTTP 503

# Step 4: re-enable the flag
echo "=== Step 4: re-enabling flag ==="
curl -sS -X POST http://localhost:18000/api/v1/admin/feature-flags/ai_smart_template/toggle \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"enabled":true,"reason":"validation test cleanup"}'
```

### Expected

- Step 1: HTTP 200 or 422 (NOT 503)
- Step 2: HTTP 200
- Step 3: **HTTP 503** (this is the kill-switch working)
- Step 4: HTTP 200

### If it fails

- **Step 3 returns 200 not 503**: feature flag wiring broken — check
  `backend/app/services/ai_feature_gating.py` + endpoint decorator
- **Step 2 returns 403**: admin token invalid or admin role misconfigured
- **Step 1 returns 503**: flag was already disabled, or `seed_ai_feature_flags`
  wasn't run

---

## Check 4 — AI safety contract (Playwright)

**Purpose**: prove AI endpoints always return `requires_doctor_confirmation: True`.

**Why it matters**: this is the only programmatic signal that AI output is a
suggestion. If it goes missing, AI output might get auto-saved to medical
records → patient harm.

### Run

```bash
cd frontend

# Set test credentials (must match dev_seed.py output)
export QA_DOCTOR_USERNAME=doctor@clinic.com
export QA_DOCTOR_PASSWORD=<doctor password>
export QA_ADMIN_USERNAME=admin@clinic.com
export QA_ADMIN_PASSWORD=<admin password>
export QA_REGISTRAR_USERNAME=registrar@clinic.com
export QA_REGISTRAR_PASSWORD=<registrar password>
export BACKEND_URL=http://localhost:18000

# Run the spec
npx playwright test e2e/ai-safety-guardrails.spec.js --project=chromium
```

### Expected

```
Running 6 tests using 1 worker

  ✓  1 [AI Safety Guardrails] › EMR smart-template response includes safety_meta
  ✓  2 [AI Safety Guardrails] › EMR smart-suggestions response includes safety_meta
  ✓  3 [AI Safety Guardrails] › AI gateway analyze-complaints response is role-gated + safe
  ✓  4 [AI Safety Guardrails] › non-doctor role cannot call AI endpoints (403)
  ✓  5 [AI Safety Guardrails] › AI endpoints require authentication (401 without token)
  ✓  6 [AI Feature Flag Toggle (admin)] › disabling ai_smart_template returns 503 from endpoint

  6 passed (6)
```

### If it fails

- **Test 1-2 fail (no safety_meta)**: endpoint dropped `ai_safety_meta()` call —
  check `backend/app/api/v1/endpoints/emr_ai_enhanced.py`
- **Test 3 fails**: AI gateway not returning audit_id — check `ai_gateway.py`
- **Test 4 fails (registrar got 200)**: RBAC broken — check `require_ai_permission`
- **Test 5 fails (no auth)**: endpoint missing auth dependency
- **Test 6 fails (no 503)**: feature flag wiring broken — see Check 3

---

## Check 5 — arq worker + visit reminder

**Purpose**: prove arq worker processes jobs and visit reminders are sent.

**Why it matters**: without working arq, patients don't get reminders, data
retention doesn't run, scheduled reports don't generate.

### Run

```bash
# Terminal 1: start worker
cd backend
arq app.tasks.worker.WorkerSettings

# Terminal 2: enqueue a test reminder
cd backend
python -c "
import asyncio
from app.tasks import enqueue_reminder

async def main():
    job_id = await enqueue_reminder(visit_id=1, channel='telegram')
    print(f'Enqueued job: {job_id}')

asyncio.run(main())
"

# Watch Terminal 1 for log output:
# Expected: 'job.send_visit_reminder visit_id=1 channel=telegram'
# Then: 'job.send_visit_reminder: visit 1 reminded via telegram' (if send succeeds)
# Or: 'job.send_visit_reminder: send failed for visit 1: <error>' (if Telegram bot not configured)
```

### Expected

- Worker logs show `task.enqueue.ok job_id=reminder:visit:1:telegram`
- Worker attempts to send via `NotificationService.send_confirmation_reminder`
- If Telegram bot is configured: reminder delivered, `visits.reminder_sent_at` set
- If not configured: job fails + retries 3x with 10s/60s/300s backoff, then gives up

### If it fails

- **"arq: command not found"**: `pip install arq>=0.26.0`
- **"Connection refused on redis:6379"**: Redis not running — `docker compose up redis`
- **"send failed: TELEGRAM_BOT_TOKEN not set"**: expected in dev; set token for prod
- **Job not picked up**: worker not running, or queue name mismatch

---

## Check 6 — Telegram bot delivery (optional, if used)

**Purpose**: prove Telegram bot actually sends messages to patients.

**Why it matters**: visit reminders are the primary patient-facing
notification channel. If bot is broken, patients miss appointments.

### Prerequisites

- `TELEGRAM_BOT_TOKEN` env var set (from @BotFather)
- At least one patient has linked their Telegram account via mini-app
- Worker is running (Check 5)

### Run

```bash
# 1. Verify bot is reachable
curl -sS "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getMe" | python -m json.tool
# Expected: {"ok":true,"result":{"id":...,"is_bot":true,"first_name":"...","username":"..."}}

# 2. Send a test message to yourself (replace CHAT_ID with your Telegram chat ID)
curl -sS -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
  -H "Content-Type: application/json" \
  -d '{"chat_id": <CHAT_ID>, "text": "staging validation test - telegram delivery"}'
# Expected: {"ok":true,"result":{"message_id":...,...}}

# 3. Trigger a visit reminder via arq (Check 5 step 2) — patient should receive it in Telegram
```

### If it fails

- **"Unauthorized"**: bot token invalid or revoked
- **"chat not found"**: patient hasn't started a conversation with the bot yet
  (Telegram requires user to /start the bot before bot can message them)
- **"Forbidden: bot was blocked by the user"**: patient blocked the bot —
  handle this case in `NotificationService._determine_best_channel`

---

## Check 7 — PII scrubbing (3 layers)

**Purpose**: prove PII is redacted in logs, Sentry events, and Python objects.

**Why it matters**: patient PII leaking to Sentry/logs is a legal incident
under Uzbekistan data protection law.

### Run

```bash
cd backend
python -c "
from app.core.pii_masker import mask_pii, mask_phone, mask_email, mask_name

# Test per-field maskers
assert mask_phone('+998901234567') == '+998901•••567', mask_phone('+998901234567')
assert mask_email('john@example.com').startswith('j'), mask_email('john@example.com')
assert mask_name('Иван Иванов') == 'И.И.', mask_name('Иван Иванов')

# Test recursive mask_pii
patient = {
    'first_name': 'Akmal',
    'last_name': 'Karimov',
    'phone': '+998901234567',
    'iin': '12345678901234',
    'diagnosis': 'I10 Essential hypertension',
    'id': 42,
}
masked = mask_pii(patient)
print('Masked patient:', masked)
assert masked['first_name'] == 'A.'
assert masked['last_name'] == 'K.'
assert masked['phone'] == '+998901•••567'
assert masked['iin'] == '[REDACTED]'
assert masked['diagnosis'] == '[REDACTED]'
assert masked['id'] == 42  # untouched

print('✅ All PII scrubbing tests passed.')
"
```

### Expected

```
Masked patient: {'first_name': 'A.', 'last_name': 'K.', 'phone': '+998901•••567', 'iin': '[REDACTED]', 'diagnosis': '[REDACTED]', 'id': 42}
✅ All PII scrubbing tests passed.
```

### If it fails

- **"AssertionError"**: a field is not being scrubbed — add it to
  `MEDICAL_PII_KEYS` in `backend/app/core/pii_masker.py` +
  `backend/app/core/sentry.py` + `frontend/src/services/sentry.js`
  (all three lists MUST stay in sync)

---

## Check 8 — Pre-commit hooks installed

**Purpose**: prove local commits are checked before push.

**Why it matters**: CI catches issues, but pre-commit catches them BEFORE
you push — saving 5-10 min per CI run.

### Run

```bash
# Install hooks (one-time after clone)
bash scripts/setup-dev.sh

# Verify hooks are installed
ls -la .git/hooks/pre-commit
# Expected: pre-commit file exists, not a sample

# Test with a fake leak
echo "TELEGRAM_BOT_TOKEN = '1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ'" > /tmp/test_leak.py
git add /tmp/test_leak.py 2>/dev/null || true
git commit -m "test: should be blocked by gitleaks" 2>&1
# Expected: gitleaks hook blocks the commit

# Test with a stray root test file
echo "def test_foo(): pass" > test_stray.py
git add test_stray.py
git commit -m "test: should be blocked by no-stray-root-tests" 2>&1
# Expected: no-stray-root-tests hook blocks the commit
rm test_stray.py
```

### If it fails

- **"pre-commit: command not found"**: `pip install pre-commit` then `pre-commit install`
- **Hooks not running**: check `.pre-commit-config.yaml` exists at root
- **Hook fails but commit goes through**: hooks not installed — re-run `pre-commit install`

---

## Check 9 — Unit + contract tests

**Purpose**: prove backend test suite passes.

**Why it matters**: this is the bare minimum. If unit tests fail, the system
definitely doesn't work.

### Run

```bash
cd backend
pytest tests/unit/ -v --tb=short
pytest tests/integration/test_rbac_matrix.py -v  # RBAC contract
```

### Expected

- All tests pass
- 0 failures, 0 errors
- RBAC matrix covers all roles (Admin, Doctor, Registrar, Lab, Nurse, Cashier, etc.)

### If it fails

- Read the failing test output
- Most likely: schema drift, missing test fixture, or recent refactor broke contract
- Fix the test OR fix the code — do NOT delete or skip the test without understanding why

---

## Check 10 — Frontend build + unit tests

**Purpose**: prove frontend compiles and tests pass.

**Why it matters**: white screen on patient PWA = lost appointment.

### Run

```bash
cd frontend
npm ci
npm run lint:check    # 0 errors (warnings OK)
npm run build         # completes without error
npm run test:run      # 467+ tests pass
```

### Expected

- `lint:check`: 0 errors
- `build`: `✓ built in <30s`
- `test:run`: all test files pass, 0 failures

### If it fails

- **lint errors**: `npm run lint` (with --fix) to auto-fix
- **build errors**: usually missing import, broken JSX, or invalid env var reference
- **test failures**: read the assertion, fix the component or update the test

---

## Automated smoke test script

Run all checks 1, 2, 3, 5, 7, 8, 9 in one command:

```bash
bash scripts/smoke_test_staging.sh
```

This script:
- Sets up env vars from `.env`
- Runs each check
- Prints ✓ / ✗ next to each
- Exits 0 if all pass, 1 if any fail
- Outputs a summary at the end

See `scripts/smoke_test_staging.sh` for the implementation.

---

## When to run this runbook

Run **all checks** before:

- Production deploy
- Major refactor merge
- Database migration deploy
- Adding a new AI provider
- Changing auth/RBAC code
- After security incidents

Run **check 3 (kill-switch) + check 4 (safety contract)** before:

- Any change to AI endpoint code
- Any change to feature flag system
- Any change to RBAC

Run **check 2 (DR drill)** weekly (automated via `.github/workflows/dr-drill.yml`).

---

## What to do if a check fails

1. **Stop**. Do not deploy. Do not claim "it works".
2. **Read** the failure output carefully.
3. **Identify** root cause using the "If it fails" section for that check.
4. **Fix** the root cause (not the symptom).
5. **Re-run** the failing check.
6. **Document** the failure + fix in `docs/incidents/` if it was serious.
7. **Re-run the full runbook** before deploying.

---

## Agent contract

If you are an AI agent (Claude, Cursor, Codex, Aider, etc.):

1. **You MUST run this runbook** before claiming the system works.
2. **You MUST NOT write** "deployment complete" or "system verified" in any
   commit message, PR description, or chat response unless every check passed.
3. **You MUST report** which checks passed and which failed — do not generalize.
4. **You MUST NOT skip** checks you find inconvenient. If a check is broken,
   fix it or report it as broken.
5. **You MUST update** this runbook if you discover a new failure mode or
   add a new subsystem that needs validation.

Violating this contract undermines trust in the entire system. Patient safety
depends on honest reporting.

---

## Related files

| File | Purpose |
|---|---|
| `scripts/smoke_test_staging.sh` | Automated version of this runbook |
| `docs/runbooks/SENTRY_SETUP.md` | Sentry setup + troubleshooting |
| `docs/runbooks/CLINIC_BACKUP_RESTORE_REHEARSAL_RUNBOOK.md` | DR drill details |
| `backend/app/scripts/dr_drill.py` | DR drill implementation |
| `backend/app/scripts/seed_ai_feature_flags.py` | AI flag seeder |
| `frontend/e2e/ai-safety-guardrails.spec.js` | AI safety contract tests |
| `.github/workflows/dr-drill.yml` | Weekly DR drill CI |
| `.github/workflows/ai-safety-guardrails.yml` | Nightly AI safety CI |
| `AGENTS.md` | AI agent rules (references this runbook) |
