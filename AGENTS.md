# AGENTS.md

Primary repo-level operating rules for Codex, Cursor agents, Claude Code style agents, and other repo-aware executors.

`AGENTS.md` is the short operational layer. `CLAUDE.md`, `.cursor/rules/*`, `.ai-factory/*`, and docs remain compatible secondary context. If instructions conflict, prefer the narrower, safer, more canonical rule.

## Project Anchors

- Product: clinic EMR and operations platform for admin, registrar, doctor, cashier, lab, queue, billing, and rollout workflows.
- Backend: Python 3.11, FastAPI, SQLAlchemy, Pydantic v2, PostgreSQL, Alembic, Redis/WebSocket.
- Frontend: React 18, Vite, React Router, JavaScript/JSX.
- Runtime defaults: backend `18000`, frontend `5173`, staging Postgres `55432`.
- Context SSOT: `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`, this file, and the canonical source/test files found for the task.
- Dev-brain tools live outside runtime in `ai/llamaindex`, `ai/langgraph`, and `ai/lightrag`.

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

## Execution Mode Selection

Before any execution task, first choose exactly one mode:

- `direct_execute`: local narrow task, root cause known, likely one file or very small slice, no risky domain, no ownership ambiguity, no canonical/legacy ambiguity, no expected scope creep. Do not run `agent_gate.py`.
- `gate`: risky task, unclear root cause, likely multi-file impact, frontend/backend ownership ambiguity, canonical/legacy ambiguity, scope-creep risk, or handoff-style brief needed.
- `gate_known_root_cause`: risky task with a confirmed root-cause file; use the gate but anchor it with `--known-root-cause`.
- `narrow_override`: only after `agent_gate.py` misroutes, one retry still misses the confirmed root-cause file, and there is explicit human or repo-approved basis for a narrow bypass.

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
python scripts\dev_brain.py plan "<task>"
python scripts\dev_brain.py dossier "<task>"
python scripts\dev_brain.py handoff "<task>"
python scripts\planner_smoke.py
python scripts\dossier_smoke.py
python scripts\handoff_smoke.py
```

Use handoff as the default input contract for the next agent when a real code change is risky or multi-file.
