# AGENTS.md

Primary repo-level operating rules for Codex, Cursor agents, Claude Code style agents, and other repo-aware executors.

`AGENTS.md` is the short operational layer. `CLAUDE.md`, `.cursor/rules/*`, `.ai-factory/*`, and docs remain compatible secondary context. If instructions conflict, prefer the narrower, safer, more canonical rule.

## Project Anchors

- Product: clinic EMR and operations platform for admin, registrar, doctor, cashier, lab, queue, billing, and rollout workflows.
- Backend: Python 3.11, FastAPI, SQLAlchemy, Pydantic v2, PostgreSQL, Alembic, Redis/WebSocket.
- Frontend: React 18, Vite, React Router, JavaScript/JSX.
- Runtime defaults: backend `18000`, frontend `5173`, staging Postgres `55432`.
- Context SSOT: `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`, this file, and the canonical source/test files found for the task.
- Active local dev-brain tooling lives outside runtime in `ai/langgraph`.
- `ai/llamaindex` and `ai/lightrag` are not guaranteed to exist in this checkout; use them only after verifying the directories and commands are present.

## Skill Routing Policy

Installed repo skills live in `.agents/skills`. User-level skills may live under `$HOME/.agents/skills`. Load skills only when the task matches their trigger, and prefer the most project-specific skill first.

- Codex/Superpowers local SSOT: use `docs/runbooks/CODEX_SUPERPOWERS_GUARD.md` together with this file. The external Superpowers plugin is a manual workflow guard, not repo runtime code, and must not be vendored into this repository.
- Skill discovery/setup: use `find-skills` only when searching for or installing new skills.
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

- Treat LightRAG as an active dev-brain retrieval layer for graph-heavy workflows, but not as a fully accepted `unified brain` yet.
- Do not call the stack a `unified brain` until keyed ingest has passed the acceptance gate.
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
python scripts\agent_gate.py "<user task>"
```

- For `gate_known_root_cause`, run:

```powershell
cd C:\final\ai\langgraph
python scripts\agent_gate.py "<user task>" --known-root-cause "<relative/path.py>"
```

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
python scripts\agent_gate.py "<task>"
python scripts\agent_gate.py "<task>" --known-root-cause "<relative/path.py>"
```

Current checkout note:

- `scripts\agent_gate.py` is the only verified local dev-brain command.
- Do not run historical `scripts\dev_brain.py`, `scripts\planner_smoke.py`, `scripts\dossier_smoke.py`, or `scripts\handoff_smoke.py` unless those files are restored and verified in the current checkout.
- For `plan`, `dossier`, or `handoff` modes, produce the artifact directly from repo-grounded evidence and use `agent_gate.py` only when an execution boundary is needed.
- Use handoff as the default input contract for the next agent when a real code change is risky or multi-file.
