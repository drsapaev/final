# Project Memory

Canonical compact memory for DevBrain routing and guardrails. Keep this file short and operational. Do not turn `AGENTS.md` into a full history dump; update this file when project-wide ownership decisions change.

## Core SSOT Decisions

- Backend business rules are the source of truth for payment, queue, RBAC, EMR, lab, Telegram security, and persistence behavior.
- Frontend is presentation and interaction orchestration unless a route-specific adapter is explicitly documented as a read model.
- Route registry ownership starts from `frontend/src/routing/routeRegistry.js`.
- Database shape ownership starts from SQLAlchemy models plus Alembic revisions, not endpoint text or UI assumptions.
- CI and PR gates are repository safety infrastructure and must not be bypassed to save time.
- AI Factory, dossiers, evidence logs, and skills are advisory memory layers; executable source and tests still win when they conflict.

## Known Ownership Chains

- DB persistence: `SQLAlchemy model -> schema/table contract -> Alembic revision -> DB validation -> tests`.
- Local dev runtime: `clinic_dev Postgres -> Alembic upgrade/reset/seed -> backend 18000 -> frontend 5173 -> browser smoke`.
- Registrar payment/status: `backend service/persistence -> API DTO/read model -> frontend adapter/table -> print/payment UI`.
- Queue identity/fairness: `profile/specialist/doctor mapping -> queue service ordering -> API contract -> frontend presentation`.
- Notifications: `event catalog -> producer service -> user preference/anti-noise policy -> delivery adapter -> frontend consumer`.
- Telegram token/security: `token model/storage -> Alembic revision -> service expiry/single-use checks -> webhook/command UX`.
- Routing: `routeRegistry.js -> route guards/layouts -> role panels -> links/navigation`.

## Known Failure Patterns

- Keyword routing can misclassify storage or migration tasks as Telegram, queue, status, endpoint, or UI tasks.
- Multi-hop ownership is often missed when a change spans UI, endpoint, service, persistence, and tests.
- Manual reconstruction repeats when dossiers/evidence are not consulted before graph-heavy work.
- Existing migrations can be tempting to edit, but already-applied revisions must remain immutable.
- Frontend presentation code must not invent backend-owned values such as payment status, queue ordering, role policy, or appointment time.
- Broad audit findings should be converted into small PR slices before implementation.

## Strict Operating Rules

- Use direct execution only for narrow known-root-cause tasks with no risky domain or ownership ambiguity.
- Use dossier or handoff for graph-heavy, mixed-contract, or ownership-sensitive work.
- Use gate or gate-known-root-cause for DB, RBAC, payment, queue, Telegram security/storage, EMR/lab, CI/CD, deploy, and frontend/backend contract work.
- If the gate misroutes, retry once with `--known-root-cause`; if it still misses the confirmed file, use narrow override and report it.
- Do not silently expand scope. Stop when the required file set exceeds the declared first-touch boundary.
- Every PR needs evidence: local validation, `git diff --check`, PR scope/impact notes, and green GitHub checks when opened.

## Local Dev Runtime Contour

- Manual local UI/dev runs use PostgreSQL, not SQLite.
- Use a disposable local database such as `clinic_dev` for local manual testing and browser QA.
- Canonical local ports are backend `18000` and frontend `5173`.
- Dev DB reset/seed belongs to the manual CLI tooling documented in `docs/dev/POSTGRES_DEV_DATABASE.md` and `docs/runbooks/LOCAL_DEV_ONBOARDING.md`.
- Set `DATABASE_URL` explicitly to a PostgreSQL URL for `clinic_dev`; do not rely on fallback database behavior.
- Dev reset/seed commands must keep safety confirmations such as `--confirm-dev-reset`, `--confirm-dev-seed`, and `--confirm-db-name clinic_dev`.
- Local 2FA bypass flags are manual smoke-test aids only and must not be used in production-like environments.

## Migration / Alembic Ownership Rules

- SQLAlchemy model without a matching table/migration is migration ownership, not endpoint, webhook, queue, status, or UI ownership.
- If a model exists and the table is missing, first-touch must include a new Alembic revision under `backend/alembic/versions/`.
- Never edit an already-applied migration as a substitute for creating a new revision.
- Treat the existing model and previous revision as read-only references unless the user explicitly changes the model contract.
- Validate Alembic chain state with heads/history review and disposable/test database upgrade when available.
- Stop on multi-head ambiguity, existing target table, destructive migration requirements, or model/table mismatch.

## Queue Identity Rules

- Queue ordering and fairness belong to backend queue services and persistence.
- Do not infer queue identity from labels, display names, frontend filters, or QR text alone.
- Preserve the distinction between specialist, profile, doctor, and ticket identity.
- Frontend queue changes should remain presentation-only unless an API contract change is explicitly planned.

## Payment / Status Separation

- Payment state and visit/queue status are separate domains.
- Frontend must not normalize or invent backend payment status values.
- Registrar/cashier UI should display backend-owned payment state and route actions through canonical payment endpoints/services.
- Print/receipt behavior must not become the source of truth for payment completion.

## Notification Catalog Ownership

- Notification event types belong to the catalog/producer contract first.
- Producer services must emit catalog-backed events rather than ad hoc strings.
- User preferences and anti-noise behavior must be checked before adding notifications.
- Frontend notification UI consumes catalog-backed events and must not invent delivery semantics.

## Telegram Token / Security Ownership

- Bot UX/webhook design is separate from token storage/security ownership.
- Staff link tokens, webhook secrets, bot tokens, and one-time tokens are security-sensitive.
- Do not hardcode secrets, expose tokens in logs, weaken expiry, or weaken single-use guarantees.
- Telegram tasks mentioning Alembic, SQLAlchemy, table missing, Postgres SSOT, storage migration, create table, link token storage, or revision use DB ownership first.
- Use `telegram-bot-builder` only after confirming the task is Bot API/UX/webhook work rather than storage/migration/security root cause.

## Route Registry SSOT

- Start route work from `frontend/src/routing/routeRegistry.js`.
- Preserve canonical routes, aliases, guards, and role ownership.
- Do not create duplicate navigation truth in page components, tests, or docs.
- Stop when a route change implies RBAC, backend contract, or legacy redirect behavior not covered by the current scope.

## Z.ai Cleanup Sprint (2026-07-03 → 2026-07-04)

Large multi-PR cleanup sprint executed via Z.ai (Claude Sonnet 4.5 + GitHub
PAT). All PRs merged to main. Facts below are durable and supersede any
older assumption that conflicts with them.

### Security posture (current state)

- **Bandit**: 0 HIGH, 0 MEDIUM findings (CI blocks on MEDIUM+ via `bandit -ll`)
- **pip-audit**: 0 CVEs in `backend/requirements.txt` (CI blocks via `pip-audit --strict -r requirements.txt`)
- **safety**: report-only (cross-validation; pip-audit is the strict gate)
- **gitleaks**: scans full repo history on every push/PR + daily 03:30 UTC
- **Dependabot**: 5 ecosystems (pip, npm root, npm frontend, github-actions, docker)
- **CVEs closed in V5**: python-jose 3.3→3.4 (5 CVEs), jinja2 3.1.0→3.1.6 (5 CVEs)
- **npm audit**: 7 vulnerabilities (5 high, 2 critical) → 0 (PR #1796)

### Monitoring (Sentry)

- **Frontend DSN** (committed, public send-only): `https://57fde20209e223ec5a4a96e3a5a59fa2@o4511673323749376.ingest.us.sentry.io/4511673366282240`
- **Backend DSN** (committed, public send-only): `https://65b5195082de2f0522c27dd6695536b7@o4511673323749376.ingest.us.sentry.io/4511673347670016`
- Sentry org ID: `o4511673323749376`, region: US
- PII scrubbing in 3 layers: `pii_masker.py` (code) → `PIIMaskingFilter` (logs) → `beforeSend` (Sentry)
- 30+ medical field names redacted: iin, passport, phone, email, diagnosis, complaints, prescription, allergies, etc.
- `SENTRY_AUTH_TOKEN` (for source map upload) is CI-only secret, NOT committed

### AI subsystem — feature flags + safety contract

- **18 AI endpoints** gated by feature flags via `Depends(RequireAiFeature("flag_key"))`
- Endpoints: `ai_gateway.py` (9), `emr_ai_enhanced.py` (7), `ai_chat.py` (1), `phrase_suggest.py` (1)
- **Fail-open policy**: missing flag = endpoint proceeds (avoid breaking prod on first deploy)
- **8 default flags** seeded by `backend/app/scripts/seed_ai_feature_flags.py`:
  ai_complaint_analysis, ai_icd10_suggestion, ai_smart_template, ai_smart_suggestions,
  ai_chat_assistant, ai_phrase_suggest, telegram_mini_app_enabled, online_queue_enabled
- `ai_safety_meta()` returns `requires_doctor_confirmation: True` on every AI response
- Playwright spec `frontend/e2e/ai-safety-guardrails.spec.js` — 6 contract tests, nightly CI

### Background jobs (arq + Redis)

- arq worker replaced dead Celery stub (celery was never in requirements)
- 3 jobs: `send_visit_reminder`, `run_data_retention`, `generate_scheduled_report`
- Worker in `ops/docker-compose.yml` + `ops/compose.staging.yml` (5 services: postgres + backend + frontend + redis + worker)
- Cron: daily 03:00 UTC data retention
- Retry policy: 3 tries, exp backoff (10s/60s/300s)
- `send_visit_reminder` calls `NotificationService.send_confirmation_reminder()` (Telegram/SMS/email)

### Repo hygiene

- **0 stray `.py` at repo root** (was 37 before P0.4)
- **0 stray `.py` at `backend/` root** (was 97 before V5)
- **6 canonical root .md files**: README, CHANGELOG, SECURITY, AGENTS, CLAUDE, MIGRATIONS
- 64 status/fix/phase reports archived to `docs/archive/{phase-reports,fix-summaries,reports,setup-guides}/`
- Pre-commit hooks: gitleaks, ruff, ruff-format, black, eslint, no-stray-root-tests, no-stray-backend-root-scripts, no-db-files, no-env-files
- 4 GitHub labels created: `p0-incident`, `dr-drill`, `ai-safety`, `auto-generated`

### CI/CD workflows (current)

- `ci-cd-unified.yml` — main pipeline (backend pytest + frontend lint/unit/build + parity + e2e)
- `security-scan.yml` — bandit -ll (MEDIUM+ blocking) + pip-audit --strict (CVE blocking) + safety (report-only)
- `gitleaks.yml` — full repo secret scan, SARIF to GitHub Security
- `role-system-check.yml` — RBAC matrix test
- `pr-review-quality-gate.yml` — PR body template enforcement (catch-22 resolved by #1787)
- `dr-drill.yml` — weekly Sunday 04:00 UTC backup restore test
- `ai-safety-guardrails.yml` — nightly 02:30 UTC AI safety contract regression
- `weekly-maintenance.yml` — npm audit + pip-audit + architecture tests
- Deleted in V5: `monitoring.yml` (fake "✅ Доступна" reports), `load-testing.yml` (always passed)

### MANDATORY pre-deploy validation

- `docs/runbooks/STAGING_VALIDATION.md` — 10 checks (Sentry, DR drill, AI kill-switch, AI safety, arq, PII, pre-commit, tests, build)
- `scripts/smoke_test_staging.sh` — automated version
- Referenced in 4 entry points: `AGENTS.md`, `CLAUDE.md`, `README.md`, `.cursor/rules/project-rules.mdc`
- Agent contract: MUST NOT claim "it works" without running all 10 checks

### New modules added (need tests maintained)

- `backend/app/core/pii_masker.py` — PII scrubbing (35 unit tests in `test_pii_masker.py`)
- `backend/app/core/sentry.py` — backend Sentry init
- `backend/app/services/wait_time_predictor.py` — ML bucket-average model (20 tests)
- `backend/app/services/ai_feature_gating.py` — `RequireAiFeature` dependency
- `backend/app/synthetic_seed.py` — bulk fake data generator (15 tests)
- `backend/app/scripts/dr_drill.py` — DR drill (backup restore + smoke test)
- `backend/app/scripts/seed_ai_feature_flags.py` — 8 default flags
- `backend/app/tasks/` — arq package (scheduler.py, worker.py)
- `frontend/src/services/sentry.js` — frontend Sentry init + PII scrubbing
- `frontend/e2e/ai-safety-guardrails.spec.js` — 6 contract tests
- `mcp-servers/synthetic_data_server.py` — stdlib MCP server for IDE test data gen

### Known issues / debt

- **Frontend CI failures on main**: Frontend lint/build/unit tests failing after #1792/#1793 CSS migration. Partially fixed by #1795-#1799. Verify before deploy.
- **PR Review Quality Gate**: requires literal "not applicable" on its own line per section. Body validator is strict — see `docs/runbooks/pr-review-samples/docs-only-pr.md` for format.
- **PAT rotation**: Z.ai PATs were used in chat history. User must rotate. New PATs are fine-grained, repo-scoped, expire.
- **LightRAG**: dormant. PowerShell-only scripts, doesn't work in CI/Linux. See ADR-0007.
- **safety CLI**: unstable options across v3 minor versions. pip-audit is the strict gate now.

### Z.ai PR index (commit → PR → what)

- `6e60819f` #1781 — P0+P1+P2+V2 (28 commits): security/CI/monitoring/AI safety
- `cce9edaa` #1787 — hotfix: PR review gate catch-22 (legacy tests path)
- `1f038914` #1786 — V3: 60+ unit tests + 17 bandit HIGH fixes
- `79b4e19a` #1788 — V4: 53 bandit MEDIUM fixes + CI threshold MEDIUM+
- `ba29d5ef` #1790 — hotfix: @sentry/vite → @sentry/vite-plugin
- `8913f313` #1789 — cloud follow-up #1 (useVisitLifecycle, ADR-0002/0003)
- `b94a4656` #1793 — cloud follow-up #2 (shared helpers, ADR-0004/0005/0006, +17 tests)
- `2d73f805` #1792 — Phase 2 CSS migration (CashierPanel + DoctorPanel)
- `d51ed330` #1791 — V5: 10 CVE fixes + pip-audit strict + 97 backend root scripts moved
- `70f5c4d5` #1794 — Sentry setup runbook + DSNs committed
- `383610f5` #1795 — bandit HIGH fixes (B701 jinja2 autoescape + B324 weak hash)
- `9bd8120b` #1796 — npm audit: 7 vulns → 0
- `85e1914a` #1797 — eslint auto-fix single quotes (229 warnings)
- `efe9e833` #1798 — no-unused-vars ignore underscore-prefixed
- `ab990286` #1799 — remove 3 genuinely unused imports
- `940e0f19` #1800 — staging validation runbook + smoke test script
- `dab544d1` #1801 — fix 3 failing GitHub Actions workflows
- `1451c72a` #1802 — gitleaks allowlist (50→0 findings)
- `c02631e3` #1803 — re-apply Phase 2 + Phase 3 (lost during #1791 force-push)
- `1aeef136` #1805 — fix qr_queue visit_id None → is_(None) SQL filter
