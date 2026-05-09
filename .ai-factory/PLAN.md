# Implementation Plan: Full Recovery + UX-First Stabilization

Branch: none
Created: 2026-05-09

## Settings

- Testing: yes
- Logging: verbose
- Docs: yes

## Roadmap Linkage

Milestone: "VPS Staging Promotion Path (Mandatory Next Milestone)"
Rationale: Before VPS promotion, the local product must be mechanically verified, user-visible defects cleaned, and critical flows proven.

## AIF Workflow Contract

This plan is the active fast-mode AIF plan at `.ai-factory/PLAN.md`.

Required sequence:

1. Improve this plan before coding:
   `/aif-improve @.ai-factory/PLAN.md improve for UX-visible defects, critical clinic flows, safety tests, first-touch boundaries, and AIF handoff compatibility`
2. Implement sequentially:
   `/aif-implement @.ai-factory/PLAN.md`
3. Verify after implementation:
   `/aif-verify --strict`
4. If verification finds issues:
   `/aif-fix <verification issue summary>`
5. Before commit or PR, use the appropriate AIF overlays:
   `/aif-security-checklist`
   `/aif-review`
   `/aif-docs`
   `/aif-roadmap check`
   `/aif-evolve`
   `/aif-commit`

Hard implementation rule:

- Implementation must proceed through `/aif-implement @.ai-factory/PLAN.md`; do not perform ad hoc coding outside the active plan.
- If a reviewer, gate, or verification pass raises a higher-severity finding, refine this plan first, then resume `/aif-implement @.ai-factory/PLAN.md`.

## Resume And Progress Tracking

During `/aif-implement`, keep progress resume-friendly:

- active plan: `.ai-factory/PLAN.md`
- progress log: `.ai-factory/logs/RECOVERY_IMPLEMENTATION_STATUS.md`
- after every task: update the task checkbox and record current task, completed checks, blockers, next action, and validation evidence
- do not rely on chat memory between sessions

## Execution Gate Rules

Before any runtime/code task, print the `AGENTS.md` execution pre-work block.

- Use `direct_execute` only for narrow single-file fixes with known ownership and a clear validation target.
- Use `gate` for queue, EMR, RBAC, payment, Telegram, routing, frontend/backend contract, or multi-file UX work.
- Use `gate_known_root_cause` only when the root-cause file is already confirmed.
- Gate command for risky tasks:
  `cd C:\final\ai\langgraph && python scripts\agent_gate.py "<task>"`
- Gate command with known root cause:
  `cd C:\final\ai\langgraph && python scripts\agent_gate.py "<task>" --known-root-cause "<relative/path>"`
- If the gate emits a handoff, read and obey the generated `Ready-to-send execution prompt` before editing.
- If the gate fails, stop and report instead of editing.

## Recovery Principles

- Facts first, then diagnosis, then prioritization, then small verified fixes.
- Do not trust "100% complete" reports unless executable source, tests, migrations, CI, or browser evidence proves them.
- Preserve the dirty worktree and do not revert unrelated user or agent changes.
- Use `AGENTS.md` execution mode rules before every implementation slice.
- Use `agent_gate.py` for risky, multi-file, canonical/legacy ambiguous, queue, EMR, RBAC, payment, Telegram, routing, or frontend/backend contract work.
- Do not expose secrets, credentials, tokens, production URLs, or patient data.
- AI features must remain draft/suggestion/support only; final clinical decisions require doctor/admin approval.

## Principal Review Override (2026-05-09)

This section supersedes the earlier Task 2 baseline where severities or ordering conflict. The former UX Task 6 and all lower-priority UX work are blocked until the P0 STOP & SECURE tasks below are closed or explicitly downgraded by evidence.

### New / Elevated P0

- P0-A: Canonical login appears to bypass blocking 2FA
  - Evidence checked: `frontend/src/components/auth/LoginFormStyled.jsx` calls `buildApiUrl('/auth/minimal-login')`; `backend/app/api/v1/endpoints/minimal_auth.py` returns `access_token`; existing `backend/tests/test_2fa_enforcement.py` targets `/api/v1/authentication/login`.
  - Risk: staff/admin/cashier login can receive an access token before 2FA verification.
  - Required first step: gated auth surface audit, no edits.
  - Execution mode: `gate_known_root_cause` with `backend/app/api/v1/api.py`.
  - Validation: auth route map, 2FA tests for canonical and fallback paths, login smoke through Vite proxy.

- P0-B: Tracked plaintext auth fixture
  - Evidence checked: `git ls-files` tracks `test_auth.json`; content must not be printed in logs or plans.
  - Risk: credential reuse or leaked test user in dev/staging.
  - Required first step: prove whether the referenced user exists in any accessible environment or stop for rotation instruction.
  - Execution mode: `gate` if auth/database state is changed; `direct_execute` only for metadata cleanup after rotation is resolved.
  - Validation: secret scanner, git tracked-file check, auth fixture removal proof, rotation note.

- P0-C: Payment webhook can silently lose provider events
  - Evidence checked: `backend/app/api/v1/endpoints/payment_webhook.py` catches exceptions and returns a normal JSON body instead of an HTTP error; `backend/app/api/v1/api.py` also mounts `payment_webhooks_router`.
  - Risk: provider may not retry after DB/service failures; payment state can be lost or split across duplicate callback surfaces.
  - Execution mode: `gate_known_root_cause` with `backend/app/api/v1/endpoints/payment_webhook.py`.
  - Validation: provider webhook tests for validation errors, DB/service errors, idempotency, and canonical callback URL.

- P0-D: Simple file upload endpoint is production-mounted without sufficient file security
  - Evidence checked: `backend/app/api/v1/endpoints/file_upload_simple.py` accepts `UploadFile`, uses user-provided filename, writes to relative `uploads/`, and logs user/file data via `print`; `backend/app/api/v1/api.py` mounts it under `/files`.
  - Risk: PHI/file exposure, unsafe filename handling, unbounded upload, unsupported storage location.
  - Execution mode: `gate_known_root_cause` with `backend/app/api/v1/endpoints/file_upload_simple.py`.
  - Validation: file upload security tests or endpoint disabled behind explicit non-production gate.

- P0-E: OAuth2 tokenUrl documents the bypass endpoint
  - Evidence checked: `backend/app/api/deps.py` sets `OAuth2PasswordBearer(tokenUrl="/api/v1/auth/minimal-login")`.
  - Risk: Swagger/API clients normalize the fallback/bypass path as canonical auth.
  - Execution mode: same gated auth slice as P0-A.
  - Validation: OpenAPI/auth dependency check and 2FA enforcement tests.

### New / Elevated P1

- P1-F: 2FA tests are false-green because they do not cover the real frontend login path.
- P1-G: `emr_v2.router` is mounted at `prefix="/v2"`, yielding `/api/v1/v2/...`; verify intended EMR v2 contract before edits.
- P1-H: Queue has multiple mounted surfaces: `qr_queue`, `online_queue_new`, legacy `queue_router`, and `/queues`; verify SSOT and `QUEUE_GROUPS`.
- P1-I: Telegram webhook secret-token and PHI handling are unverified across multiple Telegram routers.
- P1-J: Payment providers have duplicate callback URLs; determine which URL is configured with Payme/Click before consolidation.
- P1-K: Alembic revision chain and clean PostgreSQL upgrade to head are unverified.
- P1-L: AI clinical navigation is visible before provider configuration, draft-only boundaries, and fallback UX are proven.

### P2 Corrections

- `temp_token.json` is no longer treated as proven P0 by filename alone; classify as tracked trash unless a scanner proves sensitive content.
- `VITE_ENABLE_INTERNAL_DEMO` is now required for internal demo UI; update `frontend/.env.example` and developer docs before treating Task 5 as fully DX-complete.

### Stop Card

Do not proceed to UX friction, landing polish, VPS promotion, or commit until P0-A through P0-E are audited and either fixed or explicitly downgraded with evidence.

## Recovery Backlog (Task 2 Baseline)

This backlog is evidence-led and must be refined as tasks uncover better facts.

### P0 - Critical Until Proven Safe

- Possible tracked credential/auth artifacts: `temp_token.json`, `test_auth.json`
  - Where: repo root, tracked by git
  - Why: file names imply token/auth material; content was not printed or inspected
  - Risk: accidental secret or auth fixture exposure
  - Fix: secret-safe triage, prove fixtures are harmless or remove/rotate/sanitize
  - Execution mode: `direct_execute` for safe metadata triage, `gate` if runtime auth behavior changes
  - Validation: `git ls-files`, secret scanner, targeted auth tests

### P1 - Important Recovery Risks

- Multiple auth routers mounted under `/auth`
  - Where: `backend/app/api/v1/api.py` includes `auth`, `simple_auth`, and `minimal_auth`; `backend/app/api/deps.py` points OAuth token URL at minimal login
  - Why: overlapping auth surfaces can create inconsistent login, token, RBAC, and production behavior
  - Risk: broken or bypass-prone authentication/role access
  - Fix: canonical auth audit first, then narrow consolidation or guard tests
  - Execution mode: `gate`
  - Validation: auth integration tests, RBAC matrix, production fail-closed config checks

- Published legacy/test/simple file and upload endpoints
  - Where: `backend/app/api/v1/api.py` mounts `file_upload_simple`, `file_upload_json`, and `file_test` under `/files`
  - Why: test/simple upload surfaces may bypass intended file security or confuse clients
  - Risk: file upload security, PHI exposure, unsupported user flows
  - Fix: classify canonical vs legacy, gate or restrict non-canonical routes
  - Execution mode: `gate`
  - Validation: file security tests and endpoint contract checks

- Payment webhook surface duplication
  - Where: `payment_webhooks_router` and `payment_webhook.router` are both mounted
  - Why: duplicate callback paths can split idempotency/signature/reconciliation logic
  - Risk: duplicate or incorrect payment state
  - Fix: identify provider-canonical callbacks, add idempotency/signature regression coverage
  - Execution mode: `gate`
  - Validation: payment webhook tests, payment E2E, reconciliation checks

- Mixed-language and possible encoding-artifact UX in route/UI metadata
  - Where: `frontend/src/routing/routeRegistry.js`, `frontend/src/routing/routeSelectors.js`, `frontend/src/App.jsx`
  - Why: current source decodes correctly, but role sidebars mix English and Russian labels and older reports/terminal output can make encoding state look worse than it is
  - Risk: poor trust, confusing navigation for clinic staff
  - Fix: choose per-surface language policy, repair only confirmed broken visible text, and keep route tests green
  - Execution mode: `direct_execute` after route ownership is confirmed
  - Validation: route tests, frontend build, browser smoke

- AI/Telegram surfaces need human-approval and external-service safety audit
  - Where: backend AI and Telegram endpoints in `backend/app/api/v1/api.py`; docs under `docs/AI*`, `docs/*TELEGRAM*`
  - Why: medical AI and messaging can leak sensitive data or imply autonomous decisions
  - Risk: privacy/security readiness gap and unsafe clinical UX
  - Fix: classify AI as draft-only, verify approval workflow, verify Telegram token/webhook behavior
  - Execution mode: `gate`
  - Validation: AI safety tests/docs, Telegram mock/webhook tests

### P2 - Improvement / Maintainability Risks

- Internal demo/test routes require production visibility confirmation
  - Where: `frontend/src/routing/routeRegistry.js` group `internal-demo`, components such as `PaymentTest`, `CSSTestPage`, `ButtonShowcase`
  - Why: hidden navigation is present, but legacy paths and Admin access still need production-mode confirmation
  - Risk: confusing or misleading UI
  - Fix: route tests for internal-demo gating and production assumptions
  - Execution mode: `direct_execute` or `gate` if route contract changes broadly
  - Validation: route contract/ownership tests and browser smoke

- Historical reports and completed plans create operator/agent confusion
  - Where: root reports, backend/frontend reports, old completed `.ai-factory/PLAN.md` content replaced by this active plan
  - Why: stale "100% complete" claims conflict with current recovery work
  - Risk: agents trust stale docs instead of executable source
  - Fix: docs/runbook cleanup later; keep active plan explicit
  - Execution mode: `direct_execute` for docs-only cleanup
  - Validation: docs index and no runtime changes

- Runtime config writes/loads local `.secret_key` in development
  - Where: `backend/app/core/config.py`
  - Why: production is fail-closed, but development key files can drift into packages or operator machines
  - Risk: deployment hygiene and confusing secret source of truth
  - Fix: document/verify secret source policy, avoid tracked secret files
  - Execution mode: `gate` if config behavior changes
  - Validation: settings tests and secret scanner

### P3 - Polish

- Landing and product copy should be checked after core recovery
  - Where: `frontend/src/pages/Landing.jsx`, `frontend/src/pages/landingContent.js`, `frontend/src/pages/Landing.css`
  - Why: conversion/product clarity matters after operational correctness
  - Risk: weaker SaaS positioning, not a blocker for clinic workflow
  - Fix: landing audit after P0/P1/P2 work
  - Execution mode: `direct_execute`
  - Validation: landing tests and browser visual smoke

## User-Visible Defects Backlog (Task 3 Baseline)

- UVD-1: Internal demo/test routes have legacy direct aliases
  - Severity: P1/P2
  - Affected users: Admin and anyone with stale direct links
  - Routes: `/payment/test`, `/css-test`, `/buttons`, `/macos-demo`, `/medilab-demo`, `/integration-demo`
  - Current evidence: internal-demo routes are hidden from navigation and route tests pass, but direct legacy redirects still target internal demo pages
  - Impact: test/fake/demo screens can look production-adjacent and confuse operators
  - Disposition: Task 5 verified default gating. Internal demo routes now require explicit `VITE_ENABLE_INTERNAL_DEMO=1`; direct legacy alias smoke for `/payment/test` renders `/not-found` by default.

- UVD-2: Mixed-language role navigation
  - Severity: P2
  - Affected users: registrar, doctor, cashier, lab, admin, specialists
  - Routes/components: `SIDEBAR_PRESETS` and `nav` labels in `frontend/src/routing/routeRegistry.js`
  - Current evidence: some panels use English labels while lab/admin use Russian labels
  - Impact: inconsistent clinic workflow and lower trust
  - Disposition: decide language policy per role/surface, then make narrow copy fixes

- UVD-3: AI Assistant appears in clinical navigation before safety posture is proven
  - Severity: P1
  - Affected users: doctor, cardiology, dermatology, dentistry
  - Routes/components: doctor and specialist sidebar presets
  - Current evidence: AI navigation entries are present; backend exposes multiple AI routers
  - Impact: users may infer autonomous clinical decision-making or configured AI when it is only draft/support
  - Disposition: verify AI module, label as assistant/draft-only, hide/disable when unconfigured, require human approval workflow

- UVD-4: Large compatibility redirect surface
  - Severity: P2
  - Affected users: all roles with old links/bookmarks
  - Routes: 33 compatibility redirects
  - Current evidence: route contract tests pass, but compatibility aliases are broad and include internal demo aliases
  - Impact: stale links can bypass intended mental model and complicate support
  - Disposition: keep critical clinical aliases, deprecate risky/demo aliases, document redirect policy

- UVD-5: Public callback/queue/display routes need user-state smoke
  - Severity: P2
  - Affected users: patients and waiting-room display operators
  - Routes: `/queue/join`, `/queue/join/:token`, `/payment/success`, `/payment/cancel`, `/queue-board`, `/display-board`
  - Current evidence: routes are public and hidden from nav; frontend/backend are available locally
  - Impact: public users may see weak empty/error/recovery states
  - Disposition: browser-smoke public routes first, then fix only confirmed broken states

- UVD-6: Browser smoke is available but role credentials must be resolved safely
  - Severity: P2
  - Affected users: admin, registrar, doctor, cashier, lab
  - Current evidence: frontend `http://localhost:5173` and backend `http://localhost:18000/api/v1/health` returned `200`
  - Impact: static route tests are not enough to prove role workflows
  - Disposition: before authenticated smoke, resolve credentials from live DB/auth response per `.ai-factory/RULES.md`; do not guess from docs

- UVD-7: Demo/Test/Showcase components exist in source
  - Severity: P2/P3
  - Affected users: mostly admin/developer
  - Files: `MediLabDemo.jsx`, `MacOSDemoPage.jsx`, `PaymentTest.jsx`, `CSSTestPage.jsx`, `ButtonShowcase.jsx`, `IntegrationDemo.jsx`
  - Current evidence: components are internal-demo or source-only candidates
  - Impact: confusing source surface and possible accidental exposure
  - Disposition: keep source if useful, but enforce internal-only route policy and no normal role navigation

## Commit Plan

- **Commit 1** after Tasks 1-5: `chore: establish recovery plan and route hygiene`
- **Commit 2** after Tasks 6-10: `fix: close auth p0 and credential fixture risks`
- **Commit 3** after Tasks 11-12: `fix: secure payment webhook and upload surfaces`
- **Commit 4** after Tasks 13-18: `test: verify critical clinic contracts`
- **Commit 5** after Tasks 19-21: `docs: align recovery security testing and deployment docs`

## Tasks

### Phase 0: Baseline Audit

- [x] Task 1: Build the real project map and canonical anchors.
  Inspect repo structure, dirty worktree, backend/frontend manifests, API router, frontend route registry, migrations, tests, CI, docs, and existing AIF context. Distinguish canonical source from legacy, demo, compatibility, generated, and stale report files. Create/update the recovery status log. Do not edit runtime code in this task.
  Files: `AGENTS.md`, `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`, `.ai-factory/RULES.md`, `.ai-factory/logs/RECOVERY_IMPLEMENTATION_STATUS.md`, `backend/app/main.py`, `backend/app/api/v1/api.py`, `frontend/src/routing/routeRegistry.js`, `frontend/src/App.jsx`
  LOGGING REQUIREMENTS: log audit commands run, files inspected, skipped secret files, canonical anchors found, and uncertainty points in the session notes only; do not log secrets or patient data.

- [x] Task 2: Create the P0/P1/P2/P3 recovery backlog.
  Classify technical, security, database, frontend/backend contract, AI, payment, Telegram, docs, and deployment gaps. Mark which items require `gate`, `gate_known_root_cause`, `handoff`, or `direct_execute` under `AGENTS.md`.
  Files: `.ai-factory/PLAN.md`
  LOGGING REQUIREMENTS: log severity rationale, canonical anchor, validation target, and stop condition for every P0/P1 item.

- [x] Task 3: Create the user-visible defects backlog.
  Audit admin, registrar, doctor, cashier, lab, patient QR, and landing workflows. Find broken buttons, visible fake/demo/test screens, redundant routes, mojibake text, bad empty/loading/error states, confusing navigation, role mismatch, and unnecessary UI. Prefer browser smoke on frontend `5173` when local servers are available; otherwise record the blocker and use static route/component inspection.
  Files: `frontend/src/routing/routeRegistry.js`, `frontend/src/routing/routeSelectors.js`, `frontend/src/App.jsx`, `frontend/src/pages/*`, `frontend/src/pages/__tests__/*`, `frontend/src/routing/__tests__/*`
  LOGGING REQUIREMENTS: log affected role, route, symptom, business impact, and chosen disposition: fix, hide, move internal, deprecate, or delete later.

### Phase 1: UX-First Safe Fixes

- [x] Task 4: Fix or isolate mixed-language and broken visible text.
  Repair confirmed user-facing broken text, inconsistent role navigation labels, loading text, nav section names, page titles, and obvious encoding artifacts in canonical route/UI files. Do not touch unrelated copy. Add/adjust route tests if labels or route metadata are asserted.
  Files: `frontend/src/routing/routeRegistry.js`, `frontend/src/routing/routeSelectors.js`, `frontend/src/App.jsx`, `frontend/src/routing/__tests__/*`
  LOGGING REQUIREMENTS: log before/after route IDs touched and why each text change is user-visible.

- [x] Task 5: Hide or internalize misleading demo/test UI from normal users.
  Verify `internal-demo`, payment test, CSS test, button showcase, and similar demo routes cannot appear in production navigation or normal role menus. Preserve internal access only when explicitly gated. Confirm route access behavior in production-like env assumptions.
  Files: `frontend/src/routing/routeRegistry.js`, `frontend/src/routing/routeSelectors.js`, `frontend/src/App.jsx`, `frontend/src/routing/__tests__/*`
  LOGGING REQUIREMENTS: log every route disposition and whether it remains public, authenticated, role-scoped, or internal.

### Phase 1B: STOP & SECURE (Blocking P0)

- [x] Task 6: Audit auth router precedence and 2FA-bypass surfaces.
  Run the gate before edits: `cd C:\final\ai\langgraph && python scripts\agent_gate.py "audit auth router precedence and bypass surfaces" --known-root-cause "backend/app/api/v1/api.py"`. Build an endpoint map for `/api/v1/auth/*`, `/api/v1/authentication/*`, and 2FA verification paths. Identify which endpoints can return `access_token` before OTP and which frontend/API docs call them. Do not edit code in this task unless the gate handoff explicitly permits a narrow first-touch file.
  Files: `backend/app/api/v1/api.py`, `backend/app/api/v1/endpoints/auth*.py`, `backend/app/api/v1/endpoints/minimal_auth.py`, `backend/app/api/v1/endpoints/simple_auth.py`, `backend/app/api/v1/endpoints/authentication.py`, `backend/app/api/deps.py`, `frontend/src/components/auth/LoginFormStyled.jsx`, `backend/tests/test_2fa_enforcement.py`
  LOGGING REQUIREMENTS: log route path, router owner, whether it returns `access_token`, 2FA requirement, canonical/legacy status, and validation target; do not log passwords or tokens.

- [x] Task 7: Route canonical frontend login through the 2FA-aware flow.
  After Task 6 confirms the canonical endpoint and response contract, change the login form away from fallback/minimal auth and preserve the existing user-facing 2FA UI. Keep the slice frontend-first unless the gate identifies a required backend contract fix.
  Files: `frontend/src/components/auth/LoginFormStyled.jsx`, existing auth API helpers/tests, 2FA UI components
  LOGGING REQUIREMENTS: log login path selected, 2FA pending state, success/failure outcome, and localized user message without usernames or passwords.

- [x] Task 8: Disable fallback auth surfaces by default and correct OAuth2 tokenUrl.
  Put `minimal_auth` and `simple_auth` behind an explicit non-production/fallback flag or remove their production mount, depending on the Task 6 handoff. Update `OAuth2PasswordBearer.tokenUrl` to the canonical 2FA-aware login path. Stop if a product/operator decision is required for emergency fallback behavior.
  Files: `backend/app/api/v1/api.py`, `backend/app/api/v1/endpoints/minimal_auth.py`, `backend/app/api/v1/endpoints/simple_auth.py`, `backend/app/api/deps.py`, `backend/app/core/config.py`, `.env.example` files
  LOGGING REQUIREMENTS: log whether fallback auth is enabled, environment source, and denied fallback requests; never log credentials or token payloads.

- [x] Task 9: Add 2FA regression coverage for canonical and fallback login paths.
  Extend tests so the real frontend login route and any fallback `/auth/*` routes cannot issue `access_token` before 2FA in production-like settings. Existing false-green tests on `/api/v1/authentication/login` are not sufficient alone.
  Files: `backend/tests/test_2fa_enforcement.py`, auth fixtures, targeted frontend auth tests if present
  LOGGING REQUIREMENTS: test logs must identify endpoint and expected state only; do not include fixture passwords in failure messages.

- [x] Task 10: Triage tracked auth artifacts and remove unsafe fixtures only after rotation is resolved.
  Classify `test_auth.json` as a P0 credential artifact without printing its content. Classify `temp_token.json` as tracked trash unless scanning proves sensitive content. Before deleting `test_auth.json`, check whether the referenced account exists in accessible dev/staging state or stop with a required rotation action.
  Files: `test_auth.json`, `temp_token.json`, secret scanner config/docs if present
  LOGGING REQUIREMENTS: log filename, classification, rotation status, and removal decision; do not log credential values.

- [x] Task 11: Fix payment webhook silent-loss behavior.
  Run the gate before edits with `backend/app/api/v1/endpoints/payment_webhook.py` as known root cause. Ensure provider callback errors return retryable HTTP errors where appropriate, validation errors return explicit non-success statuses, and canonical callback ownership is clear across `payment_webhook.py` and `payment_webhooks.py`.
  Files: `backend/app/api/v1/endpoints/payment_webhook.py`, `backend/app/api/v1/endpoints/payment_webhooks.py`, payment services/models/tests, payment reconciliation tests
  LOGGING REQUIREMENTS: log provider, correlation/idempotency key, validation result, state transition, and retryable/non-retryable classification without secrets.

- [x] Task 12: Disable or harden simple file upload before production use.
  Run the gate before edits with `backend/app/api/v1/endpoints/file_upload_simple.py` as known root cause. Either disable the simple endpoint outside explicit dev/test mode or add filename normalization, size/MIME allowlist, storage-root configuration, and safe structured logging. Stop if business ownership of patient file storage is unclear.
  Files: `backend/app/api/v1/endpoints/file_upload_simple.py`, `backend/app/api/v1/api.py`, canonical file/document upload services/tests, config/env docs
  LOGGING REQUIREMENTS: log upload decision, normalized metadata, rejection reason, and storage target class without PHI, raw filenames, or usernames.

### Phase 2: Critical Contract Safety

- [x] Task 13: Verify EMR v2 route contract and audit coverage.
  Audit `emr_v2.router` mount at `prefix="/v2"` and determine whether `/api/v1/v2/...` is intended or a contract bug. Check EMR v2 save/history/audit tests before edits and preserve human-confirmed final decisions for AI-assisted EMR.
  Files: `backend/app/api/v1/api.py`, `backend/app/api/v1/endpoints/emr_v2.py`, EMR services/models/tests, doctor panels
  LOGGING REQUIREMENTS: log route contract, EMR action type, actor role/id, version/audit event, and AI draft/final boundary without PHI.

- [x] Task 14: Verify queue, QR, and queue SSOT ownership.
  Use gate/handoff before edits. Compare `qr_queue`, `online_queue_new`, `/queue/legacy`, `/queues`, and `QUEUE_GROUPS` against actual mounted routes. Preserve `queue_time`, fairness, QR token expiry/signature, and display-board update semantics.
  Files: backend queue endpoints/services/tests, `frontend/src/api/queue.js`, queue-related pages/components, service mapping files
  LOGGING REQUIREMENTS: log queue route owner, state transition, event name, role, stop condition, and validation evidence; never log sensitive patient details.

- [x] Task 15: Verify registrar patient and visit creation.
  Check patient registration, visit creation, appointment linkage, IIN/phone/age validation, duplicate-patient risk, nullable/unique email behavior, role access, transactions, and audit logs.
  Files: `backend/app/api/v1/endpoints/patients.py`, `backend/app/api/v1/endpoints/visits.py`, patient/visit schemas/services/repositories/tests, relevant migrations
  LOGGING REQUIREMENTS: log validation failures, role checks, transaction boundaries, and audit-relevant actions without PHI.

- [x] Task 16: Verify Telegram webhook and notification safety.
  Audit all Telegram routers for webhook secret-token validation, retry behavior, message templates, PHI exposure, opt-in/opt-out assumptions, and failed notification handling.
  Files: Telegram endpoints/services/tests/docs
  LOGGING REQUIREMENTS: log webhook verification result, notification status, template id, and retry state without bot tokens or patient details.

- [x] Task 17: Verify Alembic chain and clean PostgreSQL upgrade.
  Check that all 22 migrations form an unbroken `down_revision` chain and that a clean PostgreSQL upgrade to head is mechanically verified in the local/staging contour or documented as blocked.
  Files: `backend/alembic/versions/*`, Alembic config, CI/runbook files
  LOGGING REQUIREMENTS: log revision ids, head, upgrade command, database target class, and result; do not log database URLs or credentials.

- [x] Task 18: Verify AI module safety and visible fallback.
  Audit AI routers and clinical sidebar exposure. Ensure AI is draft/suggestion/support only, external provider absence has a user-friendly fallback, sensitive data boundaries are explicit, and doctor/admin approval is required for final decisions.
  Files: backend AI endpoints/services/tests/docs, frontend AI navigation/widgets/panels
  LOGGING REQUIREMENTS: log AI feature, provider configured yes/no, approval boundary, draft/final status, and fallback outcome without PHI.

### Phase 3: Deferred UX / Product Polish

- [x] Task 19: Fix top workflow friction in visible role screens.
  This task is blocked until P0-A through P0-E are closed or downgraded by evidence. Address only the highest-impact verified UX defects from Task 3: broken primary actions, unclear empty states, missing loading/error states, or role-inappropriate menu items.
  Files: first-touch files selected by verified UX evidence only
  LOGGING REQUIREMENTS: log user role, workflow step, before symptom, after behavior, and validation evidence.

- [x] Task 20: Add internal-demo DX documentation.
  Add `VITE_ENABLE_INTERNAL_DEMO=1` to the appropriate frontend env example and one short developer note so local developers can intentionally re-enable internal demo pages without restoring dev-mode auto-exposure.
  Files: `frontend/.env.example`, README or a targeted dev runbook
  LOGGING REQUIREMENTS: log doc source and exact runtime behavior; do not claim production safety beyond verified route gating.

- [x] Task 21: Align docs and AIF context.
  Update recovery, security, testing, deployment, AI, and README docs with verified facts only. Add new project rules via `/aif-rules` only if repeatable conventions are discovered. Update roadmap via `/aif-roadmap check` only when evidence supports it.
  Files: `docs/*`, `README.md`, `.env.example`, `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`
  LOGGING REQUIREMENTS: log source evidence for each documentation claim and mark anything unverified as unverified.

### Phase 4: CI-Ready Follow-Up Slices

- [x] Task 22: Remove legacy payment webhook endpoint print/error leakage.
  Continue through `/aif-implement @.ai-factory/PLAN.md` only. Replace remaining `print(...)` diagnostics in `backend/app/api/v1/endpoints/payment_webhook.py` admin/registrar endpoints with structured logger calls and generic HTTP error details. Preserve existing role guards and payment webhook semantics, including accepted failed-payment domain results with a saved webhook record. Commit and push this task as its own CI-ready slice.
  Files: `backend/app/api/v1/endpoints/payment_webhook.py`, payment webhook API/service/repository tests as validation only unless a test update is proven necessary
  LOGGING REQUIREMENTS: log endpoint name, provider/status/visit filters only as metadata classes where safe, and exception class; do not print raw exception text, provider secrets, payloads, credentials, or patient/payment sensitive details.

- [x] Task 23: Audit remaining payment service logging and public error leakage.
  After Task 22, inspect `backend/app/services/payment_webhook.py` and adjacent payment services for remaining raw `print(...)`, raw exception text in public HTTP responses, or logs that could expose payment/provider details. Use a new gate slice before edits and commit/push separately.
  Files: `backend/app/services/payment_webhook.py`, payment service tests selected by evidence
  LOGGING REQUIREMENTS: keep logs structured and non-sensitive; preserve reconciliation/audit evidence needed for financial operations.

- [x] Task 24: Fix next verified user-visible role-screen friction.
  Select exactly one high-confidence user-visible defect from the prior UX audit, preferably a broken/no-op primary action or misleading empty/error state in a role screen. Use static proof and browser smoke when available before editing. Commit/push separately after targeted validation.
  Files: first-touch frontend role-screen file selected by evidence only
  LOGGING REQUIREMENTS: log role, workflow step, visible before/after behavior, and validation evidence.

## Verification Plan

- Plan refinement: confirm `.ai-factory/PLAN.md` remains the only active fast-mode plan, Tasks 1-5 remain completed, and Task 6 is the next pending `/aif-implement @.ai-factory/PLAN.md` task.
- Auth P0: route map plus 2FA tests proving no production login path issues `access_token` before required 2FA.
- Payment P0: webhook tests prove retryable failures do not return successful HTTP status and duplicate callback ownership is explicit.
- Upload P0: simple upload endpoint is either disabled outside explicit dev/test mode or covered by filename, size, MIME, storage, and logging tests.
- Backend targeted tests: auth/RBAC, patients, visits, queue, EMR v2, payments, audit logs.
- Frontend targeted tests: route contract, role navigation, route access, visible UI smoke.
- Existing useful frontend tests include route contract/ownership, API runtime/interceptors/queue, landing, login accessibility, queue join accessibility, and user profile tests.
- Existing useful backend tests include patient documents, registrar appointments/services, queue/QR, doctor queue, payment E2E, RBAC matrix, visit flows, and security middleware tests.
- Browser smoke: admin, registrar, doctor, cashier, lab, patient QR, landing on frontend `5173`.
- Database: Alembic upgrade against PostgreSQL where schema/persistence is touched.
- Security: `/aif-security-checklist` before commit.
- Review: `/aif-review` before commit.
- Final: `/aif-verify --strict`.

## Stop Conditions

Stop and report if:

- canonical vs legacy ownership is unclear
- frontend/backend contract ambiguity appears
- role permissions are uncertain
- payment/webhook validation is not mechanically checkable
- P0 auth, payment, upload, or credential-fixture work starts without the required gate
- AI could appear to make autonomous medical decisions
- first-touch files are no longer enough
- validation target is vague
