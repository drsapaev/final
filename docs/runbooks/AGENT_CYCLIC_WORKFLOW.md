# Agent Cyclic Workflow

This runbook is the repository-owned source of truth for the agent execution style used in this project.

Name: Evidence-Based Small PR Protocol.

Core formula:

```text
Fresh main.
Clean branch.
Small scope.
Explicit gate.
Evidence before merge.
Green before next.
No silent scope creep.
Fix red in the same PR.
```

This is an operating protocol for Codex, Cursor agents, Claude Code style agents, AI Factory agents, and other repo-aware executors. It is not application runtime code.

## Purpose

Agent work must leave the repository in a known, mergeable state after every cycle. The goal is not to maximize the amount changed per turn; the goal is to make each change small, reviewable, reversible, and supported by evidence.

Small PR means small blast radius, not shallow reasoning. A tiny patch still needs scope, risk assessment, validation, and rollback clarity.

## Authority

Use these sources in order:

1. `AGENTS.md`
2. This runbook
3. Task-specific repo skills under `.agents/skills`
4. `docs/runbooks/CODEX_SUPERPOWERS_GUARD.md` when the user asks for Superpowers-style execution
5. Canonical source, tests, routes, migrations, contracts, and runbooks found for the task

If instructions conflict, follow the narrower, safer, more canonical rule.

## When This Protocol Is Required

Use the full cycle for any task that will create a PR, change repository files, touch CI, or affect a sensitive domain.

Strict mode domains always require explicit scope, validation, and stop conditions:

- database migrations, SQLAlchemy, Alembic, Postgres SSOT
- RBAC, auth, route guards, permissions
- payment, queue, status, billing, cashier flows
- Telegram tokens, webhooks, staff link tokens, Bot API contracts
- EMR, lab, clinical data, patient-facing flows
- frontend/backend contracts, OpenAPI, DTOs, route registry
- CI/CD, deployment, production readiness, workflow permissions
- dependency, security, or secret-handling changes

For tiny read-only analysis or a single local command, use judgment and keep the response concise. Do not turn this protocol into ritual overhead for harmless questions.

## Standard Cycle

For each PR-sized task:

```text
git fetch origin
git checkout main
git pull --ff-only origin main
git status --short --branch
create clean branch from fresh origin/main
define scope gate
make one scoped change
run local validation
git diff --check
commit
push branch
open PR
wait for GitHub Actions
if checks are red: fix in the same PR, push, wait again
merge only after green checks
delete remote/local branch when appropriate
sync local main
start the next cycle only after main is synced
```

Do not start the next PR while the current one is red, unmerged, or unresolved.

## Scope Gate

Before editing, state or record:

```text
Allowed paths:
- ...

Denied paths:
- ...

Expected risk:
- low / medium / high

Validation required:
- ...

Stop conditions:
- ...
```

Rules:

- Touch only the allowed paths.
- Do not use denied files as a workaround.
- Do not silently expand scope because nearby cleanup is tempting.
- If the task needs denied files, stop and report the new scope requirement.
- If a contract, migration, RBAC, payment, queue, Telegram, EMR, CI, or deploy boundary appears unexpectedly, stop and re-plan.

## Evidence Requirements

Every PR needs evidence. Evidence can be narrow, but it must be real.

Examples:

- `git diff --check`
- YAML parse for workflow changes
- targeted unit tests
- targeted backend tests
- frontend lint/build
- Playwright smoke or browser QA
- audit script output
- PR body quality gate
- GitHub Actions green

Docs-only PRs still need evidence:

- docs-only diff confirmed
- `git diff --check`
- PR body gate when applicable
- no runtime files changed

Bad evidence:

```text
Done.
Should work.
Not tested.
```

Good evidence:

```text
Validation:
- git diff --check passed
- targeted smoke passed
- GitHub checks green
- Not checked: full backend suite, because this PR is docs-only
```

## Fix-Then-Continue Rule

If CI fails:

1. Inspect the failing job and logs.
2. Identify whether the failure belongs to the current PR scope.
3. Fix the cause in the same PR when it belongs to the current scope.
4. Push a fix commit.
5. Wait for checks again.
6. Continue only after green.

Do not create unrelated PRs to escape a red check. Do not merge a red PR because a failure "looks unrelated" unless branch protection and a human maintainer explicitly approve that exception.

## Fresh Main Rule

Every new cycle starts from the latest `origin/main`.

Do not stack unrelated PRs on the previous feature branch. Stacked branches are allowed only when the user explicitly asks for a stack and the dependency is documented in each PR body.

## Dirty Workspace Rule

Before editing, inspect:

```powershell
git status --short --branch
```

If the workspace is dirty:

- identify whether each change is yours, user-owned, generated, or unrelated
- preserve user-owned changes
- ignore unrelated changes when safe
- do not use `git reset --hard` or destructive checkout to clear the tree unless the user explicitly asks
- if dirty changes block the task, stop and report the conflict

## PR Size And Shape

One PR should answer one question.

Good PR shapes:

- docs-only evidence update
- one accessibility class
- one route smoke
- one workflow gate hardening
- one Alembic revision and its tests
- one UI state family
- one backend contract repair

Avoid:

- UI plus backend plus migration plus CI in one PR
- opportunistic refactors
- broad formatting churn
- changing dependencies in a feature PR
- adding new policy and enforcing it in the same large diff

## Direct Push Exception

Default behavior is PR-based.

Direct push to `main` is allowed only when the user explicitly asks for direct push, or when the repository owner has defined a separate emergency process. Even then:

- inspect workspace first
- keep scope narrow
- run validation
- report the commit and evidence
- sync local `main`

## PR Body Expectations

Every PR should explain:

- Summary
- Scope Gate
- Contract Impact
- RBAC / Permissions
- Notification / Realtime
- Frontend Resilience
- Validation

If a section is not applicable, write a specific reason, not a blank section.

For example:

```text
not applicable - documentation-only change; no API, websocket, event, route, or frontend consumer contract changed.
```

## Stop Conditions

Stop and report instead of continuing silently when:

- canonical vs legacy ownership is unclear
- required edits exceed the scope gate
- validation target is not clear
- CI failure points to a broader architecture problem
- migration chain has multi-head ambiguity
- a task requires live production secrets or live DB access
- branch protection needs human approval
- the user-owned dirty workspace blocks safe edits
- the task turns into a product/policy decision

## Relationship To Skills And Dev-Brain

Skills and dev-brain are guardrails, not substitutes for judgment.

- Use project-specific skills first when a task matches them.
- Use `agent_gate.py` only for risky execution tasks or when `AGENTS.md` requires it.
- If the gate misroutes twice, treat that as a rule bug and use a narrow override only when the root-cause file and scope are confirmed.
- Do not let generic skills override clinic safety, RBAC, migration ownership, payment/queue semantics, or existing design-system rules.

## Final Response Checklist

At the end of a completed cycle, report:

- what changed
- files changed
- validation run
- GitHub PR/check/merge status when applicable
- what was intentionally not changed
- remaining risks or next smallest step

Keep the final answer concise, but include the evidence that matters.
