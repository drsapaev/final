# AGENTS.md

Primary repo-level operating rules for Codex, Cursor agents, Claude Code style agents, and other repo-aware executors.

`AGENTS.md` is the short operational layer. `CLAUDE.md`, `.cursor/rules/*`, `.ai-factory/*`, and docs remain compatible secondary context. If instructions conflict, prefer the narrower, safer, more canonical rule.

## Project Anchors

- Product: clinic EMR and operations platform for admin, registrar, doctor, cashier, lab, queue, billing, and rollout workflows. Supports multiple doctors per specialty with per-doctor queues, extensible to new specialties without code changes.
- Backend: Python 3.11, FastAPI, SQLAlchemy, Pydantic v2, PostgreSQL, Alembic, Redis/WebSocket.
- Architecture: see `docs/adr/ADR-001-queue-ownership-and-specialty-architecture.md` for queue ownership and specialty routing decisions.
- Frontend: React 18, Vite, React Router, JavaScript/JSX.
- Runtime defaults: backend `18000`, frontend `5173`, staging Postgres `55432`.
- Context SSOT: `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`, this file, and the canonical source/test files found for the task.
- Active local dev-brain tooling lives outside runtime in `ai/langgraph`.
- `ai/llamaindex` and `ai/lightrag` are not guaranteed to exist in this checkout; use them only after verifying the directories and commands are present.

## ⚠️ MANDATORY: Pre-Deploy Validation

**Before claiming "the system works" or "deployment complete", you MUST run the staging validation checklist:**

```
docs/runbooks/STAGING_VALIDATION.md
```

Or run the automated smoke test:

```bash
bash scripts/smoke_test_staging.sh
```

**The validation checklist covers 10 checks**:
1. Sentry smoke test (frontend + backend event delivery)
2. DR drill (backup actually restores)
3. AI feature flag kill-switch (toggle → 503)
4. AI safety contract (Playwright spec — `requires_doctor_confirmation` always present)
5. arq worker (jobs enqueue + process)
6. Telegram bot delivery (if used)
7. PII scrubbing (3 layers: code → logs → Sentry)
8. Pre-commit hooks installed locally
9. Backend unit tests pass
10. Frontend build + unit tests pass

**Agent contract (binding on all AI agents)**:
- You MUST NOT write "deployment complete", "system verified", or "it works" in any commit message, PR description, or chat response unless every check passed.
- You MUST report which checks passed and which failed — do not generalize.
- You MUST NOT skip checks you find inconvenient. If a check is broken, fix it or report it as broken.
- Code passing CI ≠ system working. CI proves compilation; this runbook proves functionality.

**If a check fails**: stop, fix the root cause, re-run. Do not deploy a broken system. Patient safety depends on honest reporting.

Full details: `docs/runbooks/STAGING_VALIDATION.md`.

## Project Memory / DevBrain Status

- Use `docs/devbrain/PROJECT_MEMORY.md` as the compact canonical memory anchor for project-wide ownership decisions, failure patterns, and strict domain guardrails.
- Use `docs/devbrain/DEVBRAIN_STATUS.md` to verify which DevBrain layers are active, documented, dormant, or missing in the current checkout.
- For durable memory routing, follow `docs/devbrain/MEMORY_ROUTING.md`.
- For DevBrain component responsibilities and boundary rules, follow `docs/devbrain/DEV_BRAIN_ROLE_MAP.md`.
- Before graph-heavy, risky, or ownership-sensitive work, consult both files together with the current filesystem state.
- Do not assume LlamaIndex or LightRAG are active unless `DEVBRAIN_STATUS.md` and filesystem checks confirm the required directories, storage, commands, and indexed commit evidence.
- Keep `AGENTS.md` short and operational; move durable history, ownership notes, and retrieval status details into the DevBrain docs instead of expanding this file into a full history dump.

## Evidence-Based Small PR Protocol

Use `docs/runbooks/AGENT_CYCLIC_WORKFLOW.md` as the repository-owned SSOT for the cyclic agent workflow. The short rule is: fresh main, clean branch, small scope, explicit gate, evidence before merge, green before next, no silent scope creep, and fix red checks in the same PR.

Hard rules for all repo-aware agents:

- Always start execution PR work from a fresh `origin/main` unless the user explicitly asks for a different base.
- Inspect the workspace before editing; never work on dirty files without understanding whether the changes are yours, user-owned, or unrelated.
- One PR must have one clear purpose. Do not mix unrelated runtime, UI, migration, CI, dependency, and docs changes.
- Define allowed paths, denied paths, validation, and stop conditions before the first edit.
- Never silently expand scope. If the task needs denied files or a broader contract change, stop and report or open a new plan.
- Every PR needs evidence: local validation, `git diff --check`, PR body scope/impact notes, and GitHub checks when a PR is opened.
- Do not start the next PR cycle until the current PR is green, merged, branches are cleaned up, and local `main` is synced.
- If CI is red, fix the same PR instead of opening unrelated follow-up PRs.
- Never discard user changes, use destructive git reset/checkout, touch secrets, live production data, or production deploy settings without explicit instruction.

Small PR means small blast radius, not shallow reasoning. Even tiny changes need scope, risk, validation, and rollback clarity.

## Skill Routing Policy

Installed repo skills live in `.agents/skills`. User-level skills may live under `$HOME/.agents/skills`. Load skills only when the task matches their trigger, and prefer the most project-specific skill first.

- Codex/Superpowers local SSOT: use `docs/runbooks/CODEX_SUPERPOWERS_GUARD.md` together with this file. The external Superpowers plugin is a manual workflow guard, not repo runtime code, and must not be vendored into this repository.
- Skill discovery/setup: use `find-skills` only when searching for or installing new skills.
- SSOT contract repair: use `final-ssot-contract-repair` when React appears to make backend-owned decisions such as `record_type` branching, `payment_status` normalization, queue ordering, endpoint selection, role policy, EMR/lab/payment/Telegram action rules, or when a task says contract repair, frontend presentation-only, Registrar/Queue contract, or boundary cleanup.
- BFF-lite/read-model work: use `final-bff-lite-read-model` only after SSOT contract leaks are checked or repaired. Keep screen/read-model endpoints inside the existing FastAPI backend, do not create a separate BFF service without strong evidence, and never move core business rules into `/ui/*` endpoints.
- OpenAPI/API contract work: use `final-openapi-contract-review` when adding, changing, or reviewing API DTOs, `/api/v1/ui/*` screen models, generated OpenAPI shape, frontend API adapters, schema-shape tests, or frontend/backend contract assertions.
- Telegram bot work: use `telegram-bot-builder` for Telegram Bot API, command/menu UX, inline keyboards, webhook architecture, and bot interaction design, but only after this file and `agent_gate.py` have established the execution mode, canonical anchors, and first-touch boundaries. Treat the skill as advisory; it must not override DB/Alembic routing, Postgres SSOT, token/security handling, or canonical backend/frontend ownership.
- Clinic frontend UI/UX: `clinic-ui-ux-master` is mandatory first for substantial Admin, Doctor, Registrar, Cashier, Lab, Patient, dashboard, route view, form, table, empty/loading/error, accessibility, responsive, visual consistency, design-system convergence, or browser visual QA work. Use `clinic-frontend-design` as the narrower fallback for small one-screen clinic UI patches if the master skill is unavailable or excessive for the task.
- React implementation: use `vercel-react-best-practices` for performance, bundle, data-fetching, and rerender concerns; add `vercel-composition-patterns` when component APIs, contexts, providers, or boolean-prop-heavy components are involved.
- UI audit: use `web-design-guidelines` only as a secondary accessibility/interface audit after `clinic-ui-ux-master`; do not let it override clinic workflow readability or the existing design system.
- Frontend validation: use `javascript-testing-patterns`, `vitest`, `webapp-testing`, and `playwright-best-practices` for unit, browser smoke, and E2E work. Prefer existing project scripts and keep artifacts in the repo's established output locations.
- Backend and database: use `fastapi-templates` for FastAPI/Pydantic/SQLAlchemy shape and `supabase-postgres-best-practices` for Postgres query, index, schema, locking, and performance review. Do not assume Supabase runtime services are used here.
- GitHub Actions and CI: use `github-actions-docs` for workflow syntax/security questions and `gh-fix-ci` for failing GitHub Actions checks.
- Security: use `code-security` for secure-by-default review and `semgrep` when a concrete static-analysis scan or custom detection rule is needed.
- Do not use a generic `frontend-design` skill for clinic application screens unless the user explicitly asks for non-clinic marketing or experimental design work.

## LightRAG Status

- Treat LightRAG as unavailable until `docs/devbrain/DEVBRAIN_STATUS.md` and filesystem checks prove that graph storage, query commands, and indexed commit evidence exist in the current checkout.
- Do not call the stack a `unified brain` until keyed ingest has passed the acceptance gate and the status file records that result.
- Acceptance order:
  1. `simple locate` as a sanity check.
  2. `Telegram mixed-contract` as an intermediate check.
  3. `registrar payment/status persistence ownership` as the acceptance gate.
- Only mark LightRAG useful if keyed ingest measurably improves canonical anchors, first-touch files, verification targets, misroute rate, and manual reconstruction on the registrar case.

## Default Task Mode

Before acting, classify the request as one mode:

`analysis`, `locate`, `impact`, `canonical`, `plan`, `dossier`, `handoff`, or `execute`.

- Use `locate` to find implementation/docs locations.
- Use `impact` to understand touched files, tests, docs, and risks.
- Use `canonical` to separate SSOT from legacy/adapters.
- Use `plan` for a patch checklist.
- Use `dossier` for curated engineering context.
- Use `handoff` for a strict execution brief for another agent.
- Use `execute` only after canonical anchors, first-touch files, references, and validation targets are clear.

## Graph-Heavy Defaults

For graph-heavy, mixed-contract, or ownership-sensitive tasks:

- Use `dossier` as the default context layer to understand the shape of the change.
- Use `handoff` as the default execution brief when the task is risky, multi-file, or needs transfer to another agent.
- Use `plan` as a supporting change checklist, not as the primary execution contract.
- Keep `dossier` first unless the task is already a narrow direct execute with a known root cause.

## Canonical First

- Identify canonical/SSOT sources before proposing or changing code.
- Prefer executable source, contract tests, route registries, service layers, migrations, and runbooks over broad overview docs.
- Explicitly distinguish canonical files from legacy, adapters, compatibility paths, redirects, and stale docs when ambiguity exists.
- Stop instead of guessing if canonical vs legacy ownership is unclear.

## Safe Patch Slice

Before the first edit, name:

- Canonical anchors.
- Files to read as reference only.
- First-touch files allowed for the first iteration.
- Narrow validation target.

For code changes:

- Start with the smallest safe patch slice.
- Touch only first-touch files first.
- Do not do opportunistic cleanup.
- Do not expand scope without a concrete reason and user-visible report.

## Execution Posture

- Do not silently choose between multiple plausible interpretations when the choice changes behavior, scope, or ownership. Surface the assumption or stop.
- Prefer the simplest change that satisfies the requested behavior. Do not add speculative abstractions, configuration, or flexibility that the task did not ask for.
- Keep edits surgical. Every changed line should trace directly to the requested behavior or to cleanup made unused by your own change.
- For multi-step work, express the implementation as a short goal-driven loop: `step -> verify`, then execute against that loop.
- If success is not mechanically checkable yet, tighten the validation target before editing instead of coding against a vague goal.

## Dev-Brain Usage Policy

The local dev-brain is an advisory memory, retrieval, guardrail, and evidence layer. It is not an absolute blocker or a replacement for the active model's reasoning.

- Use direct execution for narrow, local, known-root-cause tasks with no risky domain, ownership ambiguity, or canonical/legacy ambiguity.
- Use dossier-style repo grounding for graph-heavy context building when ownership or SSOT discovery matters but a strict execution gate would be too heavy.
- Use handoff/gate only for risky execution tasks, multi-file contract changes, or domains listed under Strict Mode Triggers.
- If `agent_gate.py` misroutes or excludes a confirmed root-cause file, retry at most once with `--known-root-cause`, then use `narrow_override` instead of looping on the gate.
- Treat repeated gate misroutes as a dev-brain rule bug to fix, not as a reason to keep blocking the product task.
- Keep durable project memory in concise repo rules, runbooks, evidence logs, and canonical source/test anchors rather than expanding `AGENTS.md` into a full history dump.

## Execution Mode Selection

Before any execution task, first choose exactly one mode:

- `direct_execute`: local narrow task, root cause known, likely one file or very small slice, no risky domain, no ownership ambiguity, no canonical/legacy ambiguity, no expected scope creep. Do not run `agent_gate.py`.
- `gate`: risky task, unclear root cause, likely multi-file impact, frontend/backend ownership ambiguity, canonical/legacy ambiguity, scope-creep risk, or handoff-style brief needed.
- `gate_known_root_cause`: risky task with a confirmed root-cause file; use the gate but anchor it with `--known-root-cause`.
- `narrow_override`: only after `agent_gate.py` misroutes, one retry still misses the confirmed root-cause file, and there is explicit human or repo-approved basis for a narrow bypass.

DB/Alembic/SQLAlchemy migration work is always a risky domain and must use `gate` or `gate_known_root_cause`. If the gate classifies the task as `Mode: migration`, treat the Alembic revision as the first-touch owner even when the task text also mentions Telegram, queue, status, webhook, endpoint, or UI files.

Always start execution work with this pre-work block:

```text
Execution mode
selected mode:
reason:
risky domain: yes/no
root cause known: yes/no
scope expectation: single-file / narrow / multi-file
command:
actual command to run
or not needed for direct execute

Initial boundaries
canonical anchor:
first-touch files:
validation target:
stop condition to watch first:
```

For `direct_execute`, still name the canonical anchor, first-touch file(s), narrow validation target, and first stop condition before editing.

## Automatic Pre-Execute Gate

Run the local gate only when the selected mode is `gate` or `gate_known_root_cause`:

```powershell
cd C:\final\ai\langgraph
.\scripts\run_agent_gate.ps1 "<user task>"
```

- For `gate_known_root_cause`, run:

```powershell
cd C:\final\ai\langgraph
.\scripts\run_agent_gate.ps1 "<user task>" --known-root-cause "<relative/path.py>"
```

Use `scripts\run_agent_gate.ps1` instead of calling `python` or `py` directly. The launcher validates a Python 3.11+ interpreter, skips broken `.venv`/Windows Store aliases, and can fall back to the bundled pgAdmin Python.

- If the gate says handoff is required, read the generated `Ready-to-send execution prompt` before editing.
- Execute only inside the prompt's `First-touch files`.
- Treat the prompt's `Stop conditions` as hard stops.
- Do not broaden scope without returning a report to the user.
- If the gate fails or cannot run, stop and report instead of editing.
- If the gate returns a misroute or misses the confirmed root-cause file, retry at most once with `--known-root-cause`.
- If the retry still misses the confirmed file, switch to `narrow_override`: edit only the approved narrow file set, preserve stop conditions, do not expand scope, and report the override in the task outcome.
- When a LightRAG/dev-brain evaluation entry is explicitly created, include `gate_misroute`, `override_used`, and `known_root_cause_file` when applicable.
- Do not use `agent_gate.py` as a ritual for every small safe task.

## LightRAG Evidence Policy

`C:\final\ai\langgraph\EVIDENCE_LIGHTRAG_READINESS.md` is a historical decision log from the period before LightRAG was accepted into the dev-brain stack.

- Do not append routine entries for every `agent_gate`, handoff, or risky change-task.
- Preserve the file as historical evidence; do not delete or rewrite it during normal implementation work.
- Append a new factual entry only when explicitly evaluating LightRAG/dev-brain quality or when a concrete gate/retrieval regression is observed.
- Examples that may justify a new entry: gate misroute, LightRAG retrieval missing an expected canonical relationship, before/after retrieval comparison, or a deliberate acceptance/regression review.
- When such an evaluation entry is needed, record the task context, observed gap or regression, whether LightRAG/gate/prompt rules helped or missed, and the concrete follow-up.

## Strict Mode Triggers

Automatically move to `plan`, `dossier`, or `handoff` before `execute` when a task touches:

- Routing canonicalization or route aliases.
- Queue fairness, specialist/profile/doctor mapping, or `queue_time`.
- Frontend/backend contract alignment.
- Telegram integration.
- DB schema, Alembic revisions, SQLAlchemy models, table creation, storage migrations, or Postgres SSOT.
- EMR, lab, rollout, evidence packs, go/no-go, or production-sensitive behavior.
- Any canonical vs legacy ambiguity.

For risky multi-file work, prefer `handoff` before implementation.

## Stop Conditions

Stop and report instead of continuing silently if:

- Canonical vs legacy conflict is unclear.
- Required edits leave the first safe patch slice.
- Frontend/backend ownership is not obvious.
- No clear verification target exists.
- Scope begins to spread across unrelated areas.
- Contract ambiguity appears.
- A policy, product, rollout, or runtime behavior decision is needed.

## Validation Discipline

- After changes, run the narrowest relevant validation first.
- Prefer targeted tests, contract checks, smoke checks, and runbook proof over broad unrelated suites.
- Do not run heavy checks without a reason.
- Report exactly what ran, what passed or failed, and what was not checked.

## Execute Response Format

For completed `execute` tasks, answer with:

- `Changed`
- `Why`
- `Validation run`
- `Result`
- `Scope check`
- `Stop conditions hit`
- `Next smallest step`

For risky tasks that should not execute yet, output `plan`, `dossier`, or `handoff` instead.

## Domain Guardrails

DB / Alembic / SQLAlchemy migrations:

- Use the ownership chain `model -> schema -> migration -> tests`.
- SQLAlchemy model without a matching table/migration is migration ownership, not endpoint, webhook, status, queue, or UI ownership.
- If the root cause is a missing table for an existing SQLAlchemy model, the first-touch patch must include a new Alembic revision under `backend/alembic/versions/`.
- Treat the existing SQLAlchemy model and the previous Alembic revision as read-only references unless the user explicitly changes the model contract.
- Never edit an already-applied migration as a substitute for creating a new revision.
- Migration validation must include Alembic chain checks such as heads/history review and, when a disposable/test Postgres database is available, upgrade validation.
- Stop on multi-head ambiguity, existing target table, destructive migration requirements, or model/table mismatch.

Routing:

- Start from routing SSOT files such as `frontend/src/routing/routeRegistry.js`.
- Verify route contract/snapshot tests before broad cleanup.
- Do not mass-edit unrelated routes in the first slice.

Queue:

- Protect fairness invariants and `queue_time`.
- Inspect queue-related tests first.
- Avoid SSOT drift between profile, specialist, doctor, queue, and online queue mapping layers.

Telegram:

- Consider both frontend manager files and backend Telegram endpoint/service contracts.
- Do not infer integration behavior from frontend text alone.
- Use `telegram-bot-builder` only as a Bot API, bot UX, command/menu, inline keyboard, and webhook design helper after confirming the task is not primarily DB/storage/migration ownership.
- If a Telegram task mentions Alembic, SQLAlchemy model, table missing, Postgres SSOT, storage migration, create table, link token storage, or revision, apply the DB/Alembic/SQLAlchemy migration guardrail first. The first-touch owner is the new Alembic revision when a table is missing for an existing model.
- Do not let Telegram bot skill guidance route migration/root-cause work into Telegram status, webhook, endpoint, or UI files.
- Treat bot tokens, staff link tokens, webhook secrets, and one-time token storage as security-sensitive; do not hardcode secrets, expose tokens in logs, or weaken expiry/single-use guarantees.
- Keep the first patch slice narrow even for mixed frontend/backend changes.

EMR, Lab, Rollout-sensitive areas:

- Prefer canonical runbooks, contract docs, migrations, and evidence docs.
- Do not infer production-critical behavior from random overview docs.
- Stop on ambiguity rather than improvising.

## Repo Hygiene

- Do not introduce unrelated edits.
- Do not rewrite architecture opportunistically.
- Do not touch generated evidence in `output/`, `test-results/`, or `storage/` unless the task is explicitly about artifacts.
- Do not reintroduce SQLite-first defaults. PostgreSQL + Alembic are the database source of truth.
- Do not edit shared MCP or agent settings unless the task explicitly asks for it.
- Preserve user changes in a dirty worktree. Never revert unrelated work.

## Local Dev-Brain Commands

From `C:\final\ai\langgraph`:

```powershell
.\scripts\run_agent_gate.ps1 "<task>"
.\scripts\run_agent_gate.ps1 "<task>" --known-root-cause "<relative/path.py>"
```

Current checkout note:

- For local Python commands in this Windows checkout, prefer `C:\final\scripts\run_python.ps1` over bare `python` or `py` unless a tool already provides a narrower launcher.
- For backend pytest in this Windows checkout, prefer `C:\final\scripts\run_backend_pytest.ps1 <tests...>`; it selects a Python 3.11+ interpreter with `pytest` installed and runs from `backend/` with `PYTHONPATH` set.
- `scripts\run_agent_gate.ps1` is the verified launcher for `scripts\agent_gate.py`; do not rely on bare `python` or `py` in local shells.
- `scripts\agent_gate.py` is the only verified local dev-brain Python entrypoint.
- Do not run historical `scripts\dev_brain.py`, `scripts\planner_smoke.py`, `scripts\dossier_smoke.py`, or `scripts\handoff_smoke.py` unless those files are restored and verified in the current checkout.
- For `plan`, `dossier`, or `handoff` modes, produce the artifact directly from repo-grounded evidence and use `agent_gate.py` only when an execution boundary is needed.
- Use handoff as the default input contract for the next agent when a real code change is risky or multi-file.

## Medical Domain — PHI / PII / Threat Model

This system handles patient data (PHI — Protected Health Information) for a
clinic operating in Uzbekistan. While Uzbekistan's data protection regime is
not HIPAA/GDPR, the same principles apply: patient data leakage is a legal
and ethical incident. Agents MUST treat the following as hard constraints.

### PII fields — what counts as sensitive

These fields are PII and must NEVER appear in plaintext in:

- Logs (backend or frontend)
- Sentry breadcrumbs / extra context
- Error messages returned to the client
- Audit log payloads (mask except for explicit audit need)
- Test fixtures committed to the repo
- AI prompts sent to external LLMs

| Field | Masking rule for logs | Source |
|---|---|---|
| `phone` | `+998901•••567` (last 3 digits) | `patients.phone` |
| `email` | `a•••@example.com` (first char + domain) | `patients.email` |
| `iin` / `passport_number` / `doc_number` | full redact (`[REDACTED]`) | `patients.doc_number` |
| `birth_date` | year only (`1985-••-••`) | `patients.birth_date` |
| `diagnosis`, `icd10_code`, `complaints` | full redact in non-medical contexts | `visits.*`, EMR records |
| `prescription`, `medications`, `allergies` | full redact in non-medical contexts | EMR |
| `first_name`, `last_name` | initials only (`I.I.`) | `patients.*` |

The frontend Sentry integration already enforces this in
`frontend/src/services/sentry.js` (`beforeSend` scrubs 15+ medical field
keys). Backend Python logging must apply the same masking — see
`backend/app/core/pii_masker.py` (TODO: P1.x — backfill backend masking).

### Threat model — who can attack, what's at risk, what protects it

| Threat actor | Capability | Asset at risk | Control |
|---|---|---|---|
| Compromised patient token | Read own appointments, queue position | Self-PHI only | JWT expiry + refresh rotation |
| Compromised doctor token | Read all patients in their specialty | Cross-specialty leakage | RBAC per-specialty (`require_roles` + specialty filter) |
| Compromised admin token | Read all patients, audit logs, finance | Full PHI dump | 2FA mandatory for admin role + audit log on every read |
| Compromised Telegram bot token | Send messages as clinic, read bot chats | Phishing patients | Bot token in env (not code), scope-limited Telegram API |
| Compromised DB credentials | Direct PHI/PII read/write | Total compromise | DB not exposed to internet; secrets in env; gitleaks in CI |
| Malicious insider (admin) | Bulk-export patient data | Mass exfiltration | Audit log on every patient read; weekly audit review |
| AI hallucination in EMR | Wrong diagnosis/suggestion in medical record | Patient harm | `requires_doctor_confirmation: True` on every AI response; doctor must explicitly save |
| Backup file leak | Full PHI dump from stolen backup | Total compromise | Backup encryption at rest; access restricted to backup_service |

### AI hallucination response protocol (runbook)

If an AI endpoint (`/ai/*`, `/emr-ai/*`, `/ai-gateway/*`) returns medical
content WITHOUT the `ai_safety_meta` block containing
`requires_doctor_confirmation: True`, this is a P0 incident:

1. **Stop** — do not commit or deploy anything related.
2. **Verify** — check the response payload in the Sentry/audit log.
3. **Block** — disable the affected endpoint via feature flag (P2.2) or
   hotfix revert.
4. **Trace** — find which AI provider returned the unguarded response
   (check `ai_tracking` table).
5. **Report** — file an incident in `docs/incidents/` with timestamp,
   endpoint, provider, and root cause.
6. **Fix** — re-add `ai_safety_meta()` to the response shape, add a
   Playwright guardrail test (P2.4) so this can't regress.

### Break-glass procedure (AI/DB unavailable during patient visit)

If the AI/DB is down while a doctor is with a patient:

1. The doctor's panel must show cached patient data (PWA offline cache) —
   verify `frontend/public/sw.js` includes `/api/v1/patients/:id` and
   `/api/v1/emr/:patient_id` in the runtime cache.
2. The doctor can record the visit manually in the EMR editor — all fields
   are editable, AI suggestions are optional.
3. When the connection is restored, the frontend must sync offline changes
   and reconcile with any AI suggestions that arrive late.
4. **Never block medical care on AI availability.** AI is a suggestion
   layer, not a system-of-record dependency.

### Synthetic data policy

- Any data used for dev/staging/demo MUST be generated by
  `backend/app/synthetic_seed.py` or `backend/app/scripts/dev_seed.py`.
- Both tag generated records with `SYNTHETIC-` prefix or `DEV-DEMO` marker.
- Never copy production data to staging. If you need realistic volumes, use
  `synthetic_seed.py --count-patients 10000 --count-visits 100000`.
- Never commit fixtures containing real-looking names + phone numbers. The
  pre-commit `gitleaks` hook may flag these — that's a feature, not a bug.

## Monitoring — Sentry Integration

The clinic uses **Sentry** for error monitoring (both frontend and backend).
Full setup instructions: `docs/runbooks/SENTRY_SETUP.md`.

### DSNs (public, safe to commit)

- Frontend (React PWA): `https://57fde20209e223ec5a4a96e3a5a59fa2@o4511673323749376.ingest.us.sentry.io/4511673366282240`
- Backend (FastAPI): `https://65b5195082de2f0522c27dd6695536b7@o4511673323749376.ingest.us.sentry.io/4511673347670016`

Both DSNs are **send-only public keys** — they cannot read your Sentry data,
only submit events. They are safe to commit to the repo (and already are, in
`frontend/.env.example`, `backend/.env.example`, `ops/docker-compose.yml`).

### What gets captured

- Unhandled exceptions (frontend + backend)
- Failed HTTP 5xx responses
- Slow DB queries (>1s, via SQLAlchemy integration)
- WebSocket disconnects
- Failed arq background jobs (visit reminders, data retention)
- 5% of performance traces (errors always captured regardless)

### PII scrubbing (3 layers)

PII is scrubbed before any event leaves your infrastructure:

1. **Code layer** — `backend/app/core/pii_masker.py` scrubs dicts before logging
2. **Log layer** — `PIIMaskingFilter` in `logging_config.py` scrubs log records
3. **Sentry layer** — `beforeSend` callback scrubs request bodies, breadcrumbs,
   extras before sending to sentry.io

All three layers use the same field list (`MEDICAL_PII_KEYS`) — keep them in
sync when adding new PII fields. See `docs/runbooks/SENTRY_SETUP.md` section
"Maintenance → Adding new PII fields".

### Smoke testing Sentry

After deploy, verify Sentry is receiving events:

```bash
# Frontend (in browser DevTools console on production URL):
setTimeout(() => { throw new Error("smoke test sentry frontend") }, 1000)
# Check Sentry dashboard → Issues in 10 seconds

# Backend (in shell with SENTRY_DSN set):
cd backend
python -c "
from app.core.sentry import init_sentry, capture_exception
init_sentry()
try:
    raise RuntimeError('smoke test sentry backend')
except RuntimeError as e:
    capture_exception(e)
"
# Check Sentry dashboard → Issues in 10 seconds
```

### Incident: "Sentry is silent"

If you suspect Sentry isn't capturing errors:

1. Verify `SENTRY_DSN` env var is set (frontend: `VITE_SENTRY_DSN`)
2. Check `[sentry] initialized` log line on backend startup
3. Verify network reachability: `curl -I https://o4511673323749376.ingest.us.sentry.io`
4. Check Sentry UI → Settings → Projects → "Last received event" timestamp
5. See `docs/runbooks/SENTRY_SETUP.md` section 9 for full troubleshooting
