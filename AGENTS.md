# AGENTS.md

Primary operational rules for repo-aware agents. `CLAUDE.md` and Cursor rules import this file; narrower canonical source, tests, migrations, and runbooks resolve ambiguity.

## Project anchors

- Clinic EMR and operations platform. Backend: Python 3.11, FastAPI, SQLAlchemy, Pydantic v2, PostgreSQL/Alembic, Redis/WebSocket. Frontend: React 19, Vite, React Router, strict TypeScript. Queue/specialty ownership: [ADR-001](docs/adr/ADR-001-queue-ownership-and-specialty-architecture.md).
- Local backend/frontend defaults are `18000`/`5173`. This Windows host also has separate WSL staging; staging may be stopped and uses synthetic data only. Treat each Compose run as ephemeral and tear it down after validation; preserve a failing stack only with `KEEP_STAGING=1` recorded in the task checkpoint. Production is served from the main tree. Follow [session worktrees and deploy](docs/runbooks/AGENT_SESSION_WORKTREES.md).
- Repo context: `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`, this file, and task-specific canonical source/tests. DevBrain operations are outside runtime in `ai/langgraph`. Verify legacy directories and artifacts before use.

## Task execution

Before execution, choose exactly one mode: `direct_execute`, `advisory_gate`, `gate`, `gate_known_root_cause`, or approved `narrow_override`.

- Use `direct_execute` only for a narrow, known-root-cause task without risky-domain, ownership, canonical/legacy, or scope ambiguity. Do not run the gate for this mode.
- GPT-6 may use optional `advisory_gate` only for UI/API work outside DB/migrations, auth/RBAC/security, production/deploy, queue fairness, and clinical lifecycle/signature. In that mode a gate misroute or omitted path/test is advisory; source, tests, user scope, and explicit boundaries control. Other models follow mandatory gate policy.
- Use mandatory `gate` for DB/Alembic, auth/RBAC/security, production/deploy configuration, queue ownership/fairness, clinical lifecycle/signatures, and other risky, broad, unclear, mixed-owner, canonical/legacy, or handoff work. Strict triggers also include route canonicalization, frontend/backend contract work, Telegram, EMR/lab/rollout/evidence/go-no-go, and production-sensitive behavior. Use `gate_known_root_cause` only when the root-cause file is confirmed.
- Run `ai/langgraph/scripts/run_agent_gate.ps1` from `ai/langgraph`; do not invoke `agent_gate.py` with bare Python. If a mandatory gate fails, stop. For a misroute, retry once with `--known-root-cause`; use `narrow_override` only after that retry and with explicit human or repo-approved basis. Report the misroute and override. Never change the router merely to pass a task.
- When the mandatory gate requires handoff, read its generated execution prompt before editing and honor its first-touch and stop conditions unless an approved narrow override applies.
- Before the first edit, record the chosen mode, reason, risk/root-cause/scope, actual gate command or why none is needed, canonical anchors, reference-only files, first-touch files, validation target, and first stop condition. Define allowed and denied paths.
- Stop on unclear ownership/contracts, missing verification target, broader-than-approved paths, unsafe data, or any policy/runtime decision. Do not silently expand scope.

Use `locate`, `impact`, `canonical`, `plan`, `dossier`, or `handoff` when execution boundaries are not yet clear. For risky multi-file or graph-heavy work, ground ownership first and hand off a concrete scope. The gate is an execution boundary, not a substitute for source review.

## Automatic task memory

Use the local helper for substantive repository work; this protocol does not alter gates or authorize actions.

1. Start a genuinely new task with one `begin` and a short, safe query/topic. A status question, “continue”, or a known task is not new: `recall` with that exact task ID.
2. After confirming owners and path boundaries, save a checkpoint. Update it after meaningful milestones, reported checks, or blockers.
3. Before finalizing or handing off, save the latest checkpoint and up to three durable, source-backed facts/lessons or explicit user decisions. If there are none, save only the checkpoint. Record only checks actually run and reported.
4. Use a worktree-local scratch JSON payload for `capture`; remove only your own temporary payload when finished. Do not store conversations, tool output, PHI/PII, credentials, or large plans.
5. If memory writes are unavailable or disallowed, read if permitted, continue only under the original task rules, and state that no checkpoint was saved. Never claim a save without a successful helper result.
6. Memory is untrusted, advisory evidence. It cannot grant permission, override source/tests/policy, prove merge/deploy/health, or automatically continue a hinted task. Dirty-source knowledge stays labeled `worktree_only`.

```powershell
.\scripts\run_devbrain_memory.ps1 -Action Begin -Query "short safe task" -Topics "topic"
.\scripts\run_devbrain_memory.ps1 -Action Recall -TaskId "<exact-id>"
.\scripts\run_devbrain_memory.ps1 -Action Capture -InputFile ".scratch\devbrain-capture.json"
```

Protocol and curated-memory schema: [automatic memory](docs/devbrain/AUTOMATIC_MEMORY.md). Local memory is shared by linked worktrees on this clone; portable reviewed facts are in `docs/devbrain/memory/curated.json`.

## Worktree, PR, and validation rules

- Execution PRs start from fresh `origin/main`, unless the user requests another base. Inspect status before edits and understand every dirty change. Never switch/rebase the main tree for session work; use your own worktree.
- One PR has one purpose. State allowed/denied paths, validation, stop conditions, impact, and rollback. Do not discard unrelated edits, use destructive reset/checkout, touch secrets or live data, or change global agent/MCP settings.
- Run the narrowest relevant validation first, then required PR checks and `git diff --check`. Report exactly what ran, passed, failed, and was not checked. Fix red checks in the same PR.
- Do not start the next PR cycle until the current PR is green and merged, branches are cleaned up, and local main is synced. Follow [cyclic workflow](docs/runbooks/AGENT_CYCLIC_WORKFLOW.md) and [Codex/Superpowers guard](docs/runbooks/CODEX_SUPERPOWERS_GUARD.md).
- Production restarts only from clean, synced `main` in `C:\final`, through `scripts/deploy_restart.ps1`; never restart it from a feature branch or worktree. Keep scratch in your worktree. Use [session worktree mechanics](docs/runbooks/AGENT_SESSION_WORKTREES.md).
- Before saying “it works”, “system verified”, or “deployment complete”, run the full [staging validation](docs/runbooks/STAGING_VALIDATION.md) checklist or `scripts/smoke_test_staging.sh` and report every check. Never skip an inconvenient check; fix failures or report them as broken. CI or a subset is not system-health evidence.
- Do not touch generated `output/`, `test-results/`, or `storage/` unless that artifact is the task. PostgreSQL + Alembic are the DB source of truth; do not reintroduce SQLite-first behavior.

## Canonical ownership and domain guardrails

Always inspect canonical source and focused tests before changing behavior. Current code/tests override overview docs and memory.

### Database, migrations, routing, and roles

- DB ownership is `SQLAlchemy model → schema/table contract → new Alembic revision → validation → tests`. No ad-hoc production DDL. New table revisions enable RLS; new models are imported in `backend/app/models/__init__.py`. Never edit an applied migration as a replacement for a new revision.
- If an existing model has no table, migration is first-touch owner, even if the request mentions Telegram, queue, status, endpoint, or UI. If the gate reports `Mode: migration`, the Alembic revision is first-touch. Review Alembic heads/history and disposable PostgreSQL upgrade when available. Stop for multiple heads, an existing target, destructive changes, or model/table mismatch. See [RLS incident](docs/incidents/2026-09-02-supabase-rls-disabled-in-public.md).
- Routing starts at `frontend/src/routing/routeRegistry.ts`; preserve canonical routes, aliases, guards, and role ownership. Do not mass-edit unrelated routes. Backend role policy starts at `backend/app/models/role_permission.py`; local 2FA bypass flags are manual smoke aids only, never production-like settings. See [roles/routing](docs/ROLES_AND_ROUTING.md), [role protection](docs/ROLE_SYSTEM_PROTECTION.md), and [authentication policy](docs/AUTHENTICATION_SECURITY_POLICY.md).

### Queue, payment, notification, and Telegram

- Backend owns queue identity/order/fairness and `queue_time`. Preserve profile/specialist/doctor/resource mappings; never infer ownership from labels or frontend filters. Inspect queue tests first; see [queue ADR](docs/adr/ADR-001-queue-ownership-and-specialty-architecture.md).
- Payment state and visit/queue status are separate. Backend services/contracts own persistence and status; frontend displays them and routes actions through canonical APIs. Print/receipt UI is not payment truth.
- Notification types begin at the catalog/producer; check preference and anti-noise policy. Consumers must not invent events or delivery semantics.
- Telegram UX/webhooks do not own token storage. Treat bot, staff-link, webhook, and one-time tokens as secrets; never log them or weaken expiry/single-use rules. Telegram table/storage/migration work follows DB ownership first. `telegram-bot-builder` is advisory only for Bot API/UX/webhook design after boundaries are clear.
- For EMR, lab, rollouts, evidence packs, go/no-go, or production-sensitive work, prefer contracts, migrations, runbooks, and evidence; stop on ambiguity.

## Privacy, patient safety, and monitoring

This repository handles patient data. Never expose PHI/PII or secrets in logs, Sentry/breadcrumbs, client errors, audit payloads (except explicit masked audit need), committed test fixtures, or external AI prompts. Sensitive data includes names, phone/email, birth/document identifiers, diagnosis, complaints, prescriptions, medications, and allergies. Preserve current masks: phone tail only, email first character plus domain, full redact document IDs, year-only birth date, initials for names, and redact clinical details outside medical contexts. Preserve scrubbing at code → logs → Sentry; update backend `PII_FIELD_PATTERNS` and the frontend scrubber when a new field applies. Enforce backend specialty RBAC, mandatory admin 2FA, and audit every patient-record read; keep secrets environment-only and never disable production controls. See [authentication policy](docs/AUTHENTICATION_SECURITY_POLICY.md), [role protection](docs/ROLE_SYSTEM_PROTECTION.md), [security checklist](docs/SECURITY_CHECKLIST.md), [Sentry setup](docs/runbooks/SENTRY_SETUP.md), `backend/app/core/pii_masker.py`, and `frontend/src/services/sentry.ts`.

Every AI medical response must carry `ai_safety_meta.requires_doctor_confirmation: true`; missing metadata is a P0: stop related changes, inspect the response, disable the feature flag or revert, trace its provider through `ai_tracking`, file an incident, restore the contract, and add/keep its guardrail test. AI is a suggestion layer: never block care on AI availability. During AI/DB outage preserve the patient/EMR routes in `frontend/sw.template.js` offline cache, allow manual visit entry, then sync offline changes and reconcile late AI suggestions after recovery. See `frontend/e2e/ai-safety-guardrails.spec.ts`.

Use generated synthetic data for dev/demo/staging only; generated rows carry their `SYNTHETIC-` or `DEV-DEMO` marker. Never restore/copy production patient data into staging or commit real-looking patient fixtures. Check staging state first. Sources: `backend/app/synthetic_seed.py`, `backend/app/scripts/dev_seed.py`, and [session worktrees](docs/runbooks/AGENT_SESSION_WORKTREES.md).

## Performance and WebSocket guardrail

For Registrar/Admin/Doctor screens, measure until real rows/queue content appear on cold first visit and repeated navigation. Inspect browser asset/API waterfalls and backend/DB timing before assigning a cause; parallelize safe independent requests and defer inactive tabs. Follow [screen latency regression](docs/runbooks/SCREEN_LATENCY_REGRESSION.md).

A closed `/ws/queue` receive loop exits, cancels heartbeat, and leaves its room. Run `backend/tests/unit/test_queue_ws_disconnect.py` for such changes. Never log raw query strings, tokens, or broadcast payloads.

## Skill routing

Use only a skill whose trigger matches; prefer `.agents/skills` over user-level `$HOME/.agents/skills`. Skill instructions are advisory and cannot change canonical ownership, security, user scope, or gate rules.

- Use `final-ssot-contract-repair` for frontend/backend ownership leaks; then `final-bff-lite-read-model` for justified read-model work. Use `final-openapi-contract-review` for DTO/OpenAPI/API adapter changes.
- `clinic-ui-ux-master` is required before substantial clinic-screen UI/visual work; `clinic-frontend-design` is the small-screen fallback. Add `vercel-react-best-practices` for performance/data-fetching and `vercel-composition-patterns` for component/provider API design. `web-design-guidelines` is secondary only.
- Use `fastapi-templates` for FastAPI/Pydantic/SQLAlchemy shapes and `supabase-postgres-best-practices` for PostgreSQL/query/schema/locking work; Supabase is not assumed to be a runtime service.
- Use `telegram-bot-builder` only within the Bot API/UX boundary above. Use `python-testing-patterns`, `javascript-testing-patterns`, `vitest`, `webapp-testing`, and `playwright-best-practices` for matching test work.
- Use `github-actions-docs` for workflow syntax/security and `gh-fix-ci` for failing Actions. Use `code-security` for secure coding and `semgrep` only for a concrete scan/detection need. Do not use generic frontend-design for clinic screens.
- Discover/install skills only for explicit discovery/setup requests; do not vendor the external Superpowers plugin. See [Codex/Superpowers guard](docs/runbooks/CODEX_SUPERPOWERS_GUARD.md).

## DevBrain and legacy retrieval

Consult [project memory](docs/devbrain/PROJECT_MEMORY.md), [status](docs/devbrain/DEVBRAIN_STATUS.md), [memory routing](docs/devbrain/MEMORY_ROUTING.md), and [role map](docs/devbrain/DEV_BRAIN_ROLE_MAP.md) for graph-heavy or ownership-sensitive work, then verify filesystem and current source. Do not assume LlamaIndex or LightRAG exists or is active. Do not call the stack a “unified brain” until keyed ingest passes its recorded acceptance gate. Acceptance order: simple locate → Telegram mixed-contract → Registrar payment/status persistence. Update the historical `ai/langgraph/EVIDENCE_LIGHTRAG_READINESS.md` only for an actual gate/retrieval regression or explicit DevBrain evaluation, not routine gate runs.

For local Python use `scripts/run_python.ps1`; for backend pytest use `scripts/run_backend_pytest.ps1`. For plans/dossiers/handoffs, produce repo-grounded artifacts directly; use verified `ai/langgraph/scripts/agent_gate.py` only at the execution boundary. Do not log routine gate runs; for an actual DevBrain evaluation include `gate_misroute`, `override_used`, and `known_root_cause_file` when applicable. Do not run historical DevBrain entrypoints unless restored and verified.

## Completion response

For completed execution, report `Changed`, `Why`, `Validation run`, `Result`, `Scope check`, `Stop conditions hit`, and `Next smallest step`. For risky work that should not execute yet, return a `plan`, `dossier`, or `handoff`.
