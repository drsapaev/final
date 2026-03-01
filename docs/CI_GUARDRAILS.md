# CI Guardrails

[Back to README](../README.md)

## Purpose

This repository uses GitHub-native CI guardrails to protect `main` from three classes of regressions:

- code quality and broken tests
- architecture boundary violations
- frontend/backend contract drift, including RBAC-sensitive drift

The merge gate is intentionally strict on correctness and architecture, but pragmatic about performance and external providers.

## Core PR Gates For `main`

These are the checks that matter for pull requests targeting `main`:

| Check | Role in the merge gate |
|---|---|
| `🔍 Качество кода` | Blocks merges on linting, formatting, and static quality failures. |
| `🐍 Backend тесты` | Blocks merges on backend regressions. |
| `🎨 Frontend тесты` | Blocks merges on frontend regressions. |
| `🧱 Context Boundary Integrity` | Blocks merges when code crosses forbidden architecture boundaries. |
| `🔄 Frontend-Backend Parity` | Blocks merges when frontend behavior drifts from backend contracts or role assumptions. |
| `role-system-check` | Blocks merges on role/RBAC integrity failures in the dedicated auth workflow. |

Notes:

- `🧱 Context Boundary Integrity` and `🔄 Frontend-Backend Parity` are required guardrails for app-relevant PRs.
- On docs-only or non-app PRs, those heavy guardrail jobs may be intentionally skipped by `🧭 CI Scope`.
- A skipped heavy guardrail on a docs-only PR is expected behavior, not a CI defect.

## How `🧭 CI Scope` Works

`🧭 CI Scope` is the lightweight decision job that prevents expensive architecture checks from running on irrelevant changes.

Heavy guardrails are enabled when a pull request touches any of:

- `backend/**`
- `frontend/**`
- `ops/**`
- `.github/workflows/**`

Heavy guardrails are skipped when the PR is effectively non-app work, for example:

- Markdown-only changes
- docs-only changes
- other non-application files outside the guarded paths

Behavior by event type:

- `pull_request` into `main`: `🧭 CI Scope` decides whether heavy guardrails are required.
- `push` to `main`: heavy guardrails run.
- `workflow_dispatch`: heavy guardrails run.

This keeps PR feedback fast for documentation work while still enforcing architecture and contract safety where it matters.

## What `🧱 Context Boundary Integrity` Protects

`🧱 Context Boundary Integrity` is the architecture guardrail.

It exists to stop changes that technically compile but break the intended system structure, such as:

- bypassing approved service or repository boundaries
- coupling layers that are supposed to remain isolated
- importing or calling implementation details from the wrong layer
- weakening the separation between API, domain, service, and integration surfaces

In a medical/enterprise system, this matters because architecture drift becomes operational risk. The boundary check turns that drift into a visible, reviewable failure before merge.

## What `🔄 Frontend-Backend Parity` Protects

`🔄 Frontend-Backend Parity` is the contract guardrail.

It exists to catch cases where the frontend and backend both still work in isolation, but no longer agree on system behavior, for example:

- frontend expects endpoints, roles, or payloads that the backend no longer provides
- backend adds or changes behavior that the frontend does not reflect
- RBAC assumptions diverge between UI navigation and backend enforcement
- route or integration wiring drifts away from the actual backend contract

This job runs after frontend tests, backend tests, and architecture validation so that basic failures surface first and parity failures stay focused on contract drift.

## Role System Integrity

Role safety is guarded separately in `.github/workflows/role-system-check.yml`.

`role-system-check` exists to protect RBAC-sensitive changes, especially around:

- role validation
- login and user selection flows
- API role restrictions
- RBAC matrix behavior

This is a dedicated safety check because permission drift in a clinical system is not a normal UI bug; it is an access-control failure.

## Checks That Are Important But Not PR Merge Blockers

These checks remain part of the CI system, but they are not intended to block every PR into `main`:

| Check | Why it is not a PR-required gate |
|---|---|
| `🔒 Security сканирование` | Important, but runs on `push` and `workflow_dispatch` to avoid slowing every PR. |
| `🐳 Docker сборка` | Important for delivery confidence, but not needed as a per-PR blocker. |
| `🔗 Интеграционные тесты` | Heavy system-level verification; kept on `push` to `main` and manual runs. |

This is a deliberate split between merge-time correctness and post-merge or manual assurance.

## Why Vercel Is Not Part Of The Required Gate

Vercel is intentionally treated as an external deployment or preview signal, not as the source of truth for merge safety.

Reasons:

- it is not GitHub-native CI
- it may fail for preview, environment, or external platform reasons
- it does not define architecture correctness
- it should not override deterministic repository-owned checks

Policy:

- GitHub-native checks decide whether the code is safe to merge.
- Vercel indicates preview or deployment state.
- A red Vercel check should be reviewed, but it is not the architecture or parity gate.

## How To Read PR Checks

Use this order:

1. Check `🔍 Качество кода`.
2. Check `🐍 Backend тесты` and `🎨 Frontend тесты`.
3. Check `🧭 CI Scope`.
4. If `🧭 CI Scope` marks the PR as non-app, skipped heavy guardrails are expected.
5. If `🧱 Context Boundary Integrity` fails, fix the architecture violation.
6. If `🔄 Frontend-Backend Parity` fails, fix the frontend/backend contract drift.
7. If `role-system-check` fails, fix RBAC or role-surface integrity.
8. Treat Vercel separately from the merge gate.

Fast interpretation guide:

- `code quality` failed: syntax, lint, formatting, or static quality issue
- `backend tests` failed: backend behavior regression
- `frontend tests` failed: UI or client regression
- `context boundary` failed: wrong architectural dependency or layer violation
- `frontend-backend parity` failed: contract mismatch across UI and API
- `role-system-check` failed: auth or permission integrity issue
- `Vercel` failed: preview or deployment issue, not the branch protection source of truth

## For Tech Leads

This CI model is designed to answer two different questions without mixing them.

Question 1: "Is this pull request safe to merge into `main`?"
Answer: use the GitHub-native merge blockers:

- code quality
- backend tests
- frontend tests
- architecture boundary checks
- parity checks
- RBAC integrity

Question 2: "Is the system healthy at delivery or release level?"
Answer: use the heavier or external checks:

- security scanning
- docker build validation
- integration runs
- deployment and preview providers such as Vercel

This separation keeps PR feedback actionable and fast enough for daily work, while still enforcing the architectural discipline expected in a safety-critical medical system.

## See Also

- `docs/PLAN_CHECKLIST.md`
- `.github/workflows/ci-cd-unified.yml`
- `.github/workflows/role-system-check.yml`
