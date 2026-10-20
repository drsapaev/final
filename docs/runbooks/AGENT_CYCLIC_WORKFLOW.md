# Agent Cyclic Workflow

This runbook is the repository-owned source of truth for the agent execution style used in this project.

Name: Evidence-Based Small PR Protocol.

Core formula:

```text
Fresh origin/main in an isolated worktree.
Clean branch.
Small scope.
Explicit scope and validation; use a blocking gate when required by `AGENTS.md`.
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
inspect the production checkout without switching or editing it
create or reuse an isolated clean worktree and branch from fresh origin/main
inspect that worktree with git status --short --branch
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
clean up only the current task's branch/worktree, or record why it is retained
sync production main only when safe; otherwise record synchronization as pending
start the next independent cycle from refreshed origin/main
```

Do not start the next PR while the current one is red, unmerged, or unresolved.
This restriction applies to the current task's PR. An unrelated task or a dirty,
stale production checkout does not block a new authorized isolated cycle. Never
switch production main to satisfy this protocol. Clean, synced production main
is required for operations that use that checkout and for deployment.

## Authorization and routine decisions

The user's authorized outcome covers necessary reversible implementation,
isolated setup, relevant validation, CI repair and preparation of a reviewable
PR. Reuse prior answers and permissions. Writing a plan, selecting a skill,
recording scope or running a gate does not require a new confirmation.

Ask when a consequential decision is missing, a required action would exceed an
explicit user-imposed scope, an explicit approval requirement is not already
satisfied, or an action differs materially from existing authorization.
Do all authorized preparation before asking. Merge, publication and production
operations still need their existing authorization and safeguards; this rule
does not grant them. Stop only the dependent action and continue other safe
work. Do not repeatedly report unchanged blockers instead of preparing what
can safely be prepared.

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
- If the user explicitly limited paths, honor that limit and ask before expanding it. For an agent-written list, update the recorded scope for necessary files within the same authorized outcome and rerun any mandatory gate before editing; ask only if a consequential new decision or protected domain is introduced.
- If a contract, migration, RBAC, payment, queue, Telegram, EMR, CI, or deploy boundary appears unexpectedly, stop and re-plan.

When a gate is required or selected, use `--known-root-cause <path>` and repeated
`--scope <path>` on the canonical gate launcher after confirming the owner and
full source list. Read the
resulting prompt; supplying scope does not bypass the gate. For host operations,
record the actual authorized actions and their runbook, validation and rollback
separately. Unchanged source anchors are reference-only; a source-first-touch
list does not require an otherwise unnecessary code edit or authorize a host
mutation.

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
Fetch and create the session branch in an isolated worktree; updating the live
production checkout is not a prerequisite. Record a deferred production-main
sync with its reason and the next safe action, without blocking independent work.

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
- use a clean isolated worktree when the dirty checkout belongs to another task
- stop only an operation that requires the dirty checkout; record the conflict and continue independent work

Root `/.scratch/` and `/.gate_artifacts/` are reserved for generated session
files. They are ignored deliberately; never commit source or required evidence
there. Similar names elsewhere and all ordinary untracked files still remain
visible to Git and the deployment guard. Do not move or delete foreign scratch
to make the checkout appear clean.

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
- required edits exceed an explicit user scope limit, or the complete agent-selected scope cannot pass its required gate
- validation target is not clear
- CI failure points to a broader architecture problem
- migration chain has multi-head ambiguity
- a task requires live production secrets or live DB access
- branch protection needs human approval
- the user-owned dirty workspace blocks an action that cannot run in isolation
- the task requires a consequential product/policy decision outside the authorized outcome

These stop conditions apply to the affected action. They do not suspend safe,
independent work that remains within the approved outcome.

## Relationship To Skills And Dev-Brain

Skills and dev-brain are guardrails, not substitutes for judgment.

- Use project-specific skills first when a task matches them.
- Use `agent_gate.py` only for risky execution tasks or when `AGENTS.md` requires it.
- GPT-6 may use the gate as optional context for eligible UI/API work; it must not block that work or override canonical source, tests, user scope, and explicit patch boundaries.
- Keep the gate mandatory for DB/schema migrations, authentication/RBAC/security, production configuration/deployment, and changes to queue ownership/fairness or clinical lifecycle/signature rules. Other agent models follow `AGENTS.md` without the GPT-6 exception.
- If the gate misroutes, retry once with the confirmed root cause and complete reviewed scope. After that retry, a narrow override still needs an explicit human or repository-approved basis, recorded scope and stop conditions; do not change the router to pass the task.
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
