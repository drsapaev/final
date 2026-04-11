# AGENTS.md

Primary repo-level operating rules for Codex, Cursor agents, Claude Code style agents, and other repo-aware executors.

`AGENTS.md` is the short operational layer. `CLAUDE.md`, `.cursor/rules/*`, `.ai-factory/*`, and docs remain compatible secondary context. If instructions conflict, prefer the narrower, safer, more canonical rule.

## Project Anchors

- Product: clinic EMR and operations platform for admin, registrar, doctor, cashier, lab, queue, billing, and rollout workflows.
- Backend: Python 3.11, FastAPI, SQLAlchemy, Pydantic v2, PostgreSQL, Alembic, Redis/WebSocket.
- Frontend: React 18, Vite, React Router, JavaScript/JSX.
- Runtime defaults: backend `18000`, frontend `5173`, staging Postgres `55432`.
- Context SSOT: `.ai-factory/DESCRIPTION.md`, `.ai-factory/ARCHITECTURE.md`, this file, and the canonical source/test files found for the task.
- Dev-brain tools live outside runtime in `ai/llamaindex` and `ai/langgraph`.

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

## Automatic Pre-Execute Gate

Before any `execute` task, run the local gate yourself:

```powershell
cd C:\final\ai\langgraph
python scripts\agent_gate.py "<user task>"
```

- If the gate says handoff is required, read the generated `Ready-to-send execution prompt` before editing.
- Execute only inside the prompt's `First-touch files`.
- Treat the prompt's `Stop conditions` as hard stops.
- Do not broaden scope without returning a report to the user.
- If the gate fails or cannot run, stop and report instead of editing.

## LightRAG Readiness Evidence

For every real risky change-task executed through `agent_gate` or handoff, append one factual evidence entry to:

```text
C:\final\ai\langgraph\EVIDENCE_LIGHTRAG_READINESS.md
```

- Create the file if it does not exist.
- Record what the handoff solved well, missing relationship mapping, manual reconstruction needed, and whether multi-hop gap, ownership ambiguity, or manual graph reconstruction occurred.
- Do not inflate the signal: write `none` when no gap was observed and mark LightRAG as helpful only when the task produced a concrete observed gap.
- After 5 to 10 risky task entries, add a short evidence-based mini-review with counts and a recommendation.
- Do not change `backend/`, `frontend/`, or `ops/` only for this evidence log.

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
