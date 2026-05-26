# DevBrain Role Map

This file is the responsibility map for the repository DevBrain. It prevents agents from confusing memory, retrieval, relationship hints, guardrails, skills, CI evidence, and model reasoning.

## Final DevBrain Definition

```text
DevBrain = project memory + retrieval + relationship hints + execution guardrails + PR/CI evidence.
Codex/ChatGPT = reasoning + execution engine.
```

DevBrain is not one brain. It is a layered assisted-development system. The active model reasons and executes; repo-owned DevBrain layers provide durable context, routing, safety boundaries, and verification evidence.

## Component Responsibility Matrix

| Component | Unique function | Inputs | Outputs | When to use | When not to use | Must not override | Health check | Overlap risk | Boundary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Model / Codex / ChatGPT | Reasoning and execution engine | User task, repo files, DevBrain context, validation output | Plans, patches, reviews, summaries, commands | All tasks needing judgment or implementation | As durable memory or source of truth | Source, tests, migrations, AGENTS, PR gates | Human/evidence review, tests, CI | Model may rely on stale chat memory | Use repo evidence for durable facts |
| `AGENTS.md` | Operating law and mode policy | Repo-level safety rules, strict triggers | Required behavior for agents before editing | Every repo-aware task | Long history, status, task logs | Product source/tests, narrower safety rules | File exists; referenced by inventory | Can grow into memory dump | Keep short and operational |
| `PROJECT_MEMORY.md` | Compact canonical project memory | Repeated ownership facts, known failure patterns | Durable SSOT decisions and ownership chains | Risky, graph-heavy, ownership-sensitive work | One-off notes, status, raw chat | Executable source, tests, migrations | Inventory and retrieval refresh | Can become a journal | Store repeated durable facts only |
| `DEVBRAIN_STATUS.md` | Current layer status and acceptance evidence | Smoke, inventory, acceptance, indexed commits | Active/dormant/missing status, limitations | Before trusting LlamaIndex, LightRAG, or unified DevBrain | Domain ownership truth | Source, tests, PROJECT_MEMORY | `devbrain_inventory.ps1`, regression matrix | Can be mistaken for canonical memory | Store status, not product truth |
| AI Factory | Operational file memory | Logs, dossiers, patches, contracts, plans, skill context | Resume-friendly working context and evidence | Dossiers, rollout notes, patch evidence, task history | Project-wide canonical facts unless promoted | PROJECT_MEMORY, AGENTS, source/tests | Filesystem inventory | Can duplicate PROJECT_MEMORY | Promote repeated facts to PROJECT_MEMORY |
| LlamaIndex | Broad local fallback retrieval | Manifest sources and local lexical index | Source locations and lexical anchors | "Where is X implemented?" and broad lookup | Ownership decisions or safety routing | LightRAG, agent_gate, source/tests | `ai/llamaindex/scripts/run_smoke.ps1` | Confused with LightRAG | Broad retrieval only |
| LightRAG | Relationship graph retrieval | Manifest focus sources, ownership concepts, local graph | Relationship hints, canonical anchors, first-touch, validation targets | Mixed-contract, graph-heavy, ownership chain tasks | Deterministic execution blocking | agent_gate, AGENTS, source/tests | `ai/lightrag/scripts/run_acceptance.ps1`; artifact check | Confused with gate or truth | Hints, not authority |
| LangGraph / `agent_gate.py` | Deterministic routing and execution guardrails | Task text, known root cause, repo paths, strict rules | Mode, first-touch files, stop conditions, validation targets | Risky execution, DB/migration, RBAC, payment, queue, Telegram security/storage, CI/deploy | Simple known-root-cause local edits | Source/tests, user-confirmed narrow override | `devbrain_acceptance.ps1` | Can over-gate simple work | Strict only when risk requires |
| Skills | Domain expertise and workflow advice | Task intent, skill instructions, relevant source | Checklists, domain-specific plan, validation advice | UI/UX, security, Telegram Bot API, CI, testing, framework-specific work | As operating law or repo SSOT | AGENTS, PROJECT_MEMORY, source/tests, gate | Skill availability in session | Generic advice may conflict with clinic rules | Advisory layer |
| Evidence logs | Historical evaluation and incident memory | Misroutes, retrieval comparisons, readiness reviews | Evidence of what helped or failed | Concrete DevBrain evaluation or regression notes | Routine log for every task | PROJECT_MEMORY, DEVBRAIN_STATUS | File review; memory routing | Noise and stale conclusions | Log facts, promote only repeated lessons |
| PR/CI gates | Enforcement and evidence discipline | PR body, workflows, scripts, tests | Pass/fail enforcement, validation trail | Every PR and safety workflow | Architecture reasoning or product ownership | Human/model reasoning, source/tests | GitHub Actions, PR quality gate | Can be treated as reasoning | Enforce evidence, not decisions |
| Inventory / acceptance / regression scripts | Local DevBrain health checks | Filesystem, status, gate scenarios, retrieval probes | Active/dormant/missing, pass/warn/fail | Before trusting DevBrain for risky/graph-heavy work | As proof of product correctness | Product tests and source evidence | `devbrain_inventory.ps1`, `devbrain_acceptance.ps1`, `devbrain_regression_matrix.ps1` | Overclaiming "brain is perfect" | Health checks only |

## Boundary Rules

- `LlamaIndex != LightRAG`: LlamaIndex finds files and lexical anchors; LightRAG maps relationships, ownership chains, first-touch hints, and validation targets.
- `LightRAG != agent_gate`: LightRAG suggests relationship context; `agent_gate.py` sets deterministic execution boundaries for risky work.
- `AGENTS.md != PROJECT_MEMORY`: `AGENTS.md` is operating law; `PROJECT_MEMORY.md` is compact durable project memory.
- `AI Factory != PROJECT_MEMORY`: AI Factory stores operational logs, dossiers, and patch evidence; PROJECT_MEMORY stores repeated canonical ownership facts.
- `Skills != AGENTS`: skills advise by domain; `AGENTS.md` and project source/tests remain stronger authority.
- `CI != reasoning`: CI proves checks and evidence discipline; it does not decide architecture or product intent.
- `Model != durable memory`: the active model reasons from evidence; durable memory must be written into repo-owned memory files.

## Mode Routing

| Task type | Components to use | Do not use |
| --- | --- | --- |
| Simple narrow task | Model/Codex, `AGENTS.md`, source/tests | Full gate, LightRAG, dossier ritual |
| Graph-heavy task | `PROJECT_MEMORY.md`, LlamaIndex, LightRAG, AI Factory dossier if useful | Direct execution before ownership is clear |
| Risky execution task | `AGENTS.md`, `PROJECT_MEMORY.md`, `agent_gate.py`, relevant skills, narrow validation | Skills or LightRAG as override authority |
| Known root-cause task | `agent_gate.py --known-root-cause` only if risky; otherwise direct execute with explicit boundary | Repeated gate retries after confirmed misroute |
| DB/Alembic migration task | `AGENTS.md`, `PROJECT_MEMORY.md`, `agent_gate.py` migration mode, Alembic validation | Telegram/UI/status routing as first-touch |
| UI/UX task | `clinic-ui-ux-master` or `clinic-frontend-design`, route/design anchors, browser/static QA | Backend/contract/RBAC/payment changes in visual cleanup |
| CI failure task | GitHub Actions logs, PR/CI gates, `gh-fix-ci` or GitHub Actions docs, targeted local repro | Product refactor unless failure proves scope |
| Notification / Telegram / Queue / Payment task | `PROJECT_MEMORY.md`, LightRAG relationship hints, `agent_gate.py` if risky, relevant domain skill as advisory | Frontend-only assumptions for backend-owned state |

## Health Checks

Use these commands from `C:\final`:

```powershell
.\scripts\devbrain_inventory.ps1
.\scripts\devbrain_acceptance.ps1
.\scripts\devbrain_regression_matrix.ps1
.\scripts\devbrain_refresh_memory.ps1
```

What they prove:

- Inventory proves expected DevBrain files, launchers, and local retrieval layers exist in the checkout.
- Acceptance proves `agent_gate.py` handles critical routing scenarios.
- Regression matrix probes inventory, acceptance, LlamaIndex locate, LightRAG relationship queries, artifact integrity, and indexed commit freshness.
- Refresh memory updates local retrieval/status evidence after durable memory, manifest, or routing changes.

What they do not prove:

- They do not prove product behavior is correct.
- They do not replace backend/frontend tests.
- They do not make LightRAG or LlamaIndex canonical truth.
- They do not make the system autonomous.

## Current Status Labels

| Label | Status | Reason |
| --- | --- | --- |
| Portable unified DevBrain | yes | Inventory, acceptance, LlamaIndex, and LightRAG are active in this checkout when verified by status and filesystem checks. |
| Excellent assisted-development DevBrain | partial until this role map/status patch is merged | Core layers work, but role boundaries need this file as final SSOT. |
| Production autonomous brain | no | The model still performs reasoning and execution; DevBrain is support infrastructure, not an autonomous production developer. |

## Minimal Operating Formula

```text
Simple work: model + AGENTS + source/tests.
Graph-heavy work: add PROJECT_MEMORY + LlamaIndex/LightRAG.
Risky execution: add agent_gate + strict stop conditions.
Domain craft: add the relevant skill, but never let it override repo law.
PR safety: prove with validation and CI.
```
