# DevBrain Role Map

This file is the responsibility map for the repository DevBrain. It prevents agents from confusing memory, retrieval, relationship hints, guardrails, skills, CI evidence, and model reasoning.

## Final DevBrain Definition

```text
DevBrain = repository memory + local task checkpoints + execution guardrails + PR/CI evidence.
Codex/ChatGPT = reasoning + execution engine.
```

DevBrain is an assisted-development system. The active model reasons and executes; repo-owned memory and guardrails provide durable context, task recovery, safety boundaries, and verification evidence. LlamaIndex and LightRAG remain dormant legacy tools.

## Component Responsibility Matrix

| Component | Unique function | Inputs | Outputs | When to use | When not to use | Must not override | Health check | Overlap risk | Boundary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Model / Codex / ChatGPT | Reasoning and execution engine | User task, repo files, DevBrain context, validation output | Plans, patches, reviews, summaries, commands | All tasks needing judgment or implementation | As durable memory or source of truth | Source, tests, migrations, AGENTS, PR gates | Human/evidence review, tests, CI | Model may rely on stale chat memory | Use repo evidence for durable facts |
| `AGENTS.md` | Operating law and mode policy | Repo-level safety rules, strict triggers | Required behavior for agents before editing | Every repo-aware task | Long history, status, task logs | Product source/tests, narrower safety rules | File exists; referenced by inventory | Can grow into memory dump | Keep short and operational |
| `PROJECT_MEMORY.md` | Compact canonical project memory | Repeated ownership facts, known failure patterns | Durable SSOT decisions and ownership chains | Risky, graph-heavy, ownership-sensitive work | One-off notes, status, raw chat | Executable source, tests, migrations | Inventory and retrieval refresh | Can become a journal | Store repeated durable facts only |
| `DEVBRAIN_STATUS.md` | Current layer status and acceptance evidence | Smoke, inventory, acceptance, artifact commits | Active/dormant/missing status, limitations | Before trusting optional retrieval artifacts | Domain ownership truth | Source, tests, PROJECT_MEMORY | `devbrain_inventory.ps1`, regression matrix | Can be mistaken for canonical memory | Store status, not product truth |
| AI Factory | Operational file memory | Logs, dossiers, patches, contracts, plans, skill context | Resume-friendly working context and evidence | Dossiers, rollout notes, patch evidence, task history | Project-wide canonical facts unless promoted | PROJECT_MEMORY, AGENTS, source/tests | Filesystem inventory | Can duplicate PROJECT_MEMORY | Promote repeated facts to PROJECT_MEMORY |
| Local memory helper | Shared checkpoint and knowledge store for one clone's linked worktrees | Agent-provided task checkpoint and source-backed knowledge | Bounded recall packet and task recovery | When explicitly invoked for a task | Synchronizing independent clones or replacing source verification | AGENTS, canonical source/tests, explicit permission rules | `scripts/run_devbrain_memory.ps1 -Action Status` | Treated as system instruction or cross-machine memory | Advisory data; source truth and authorization stay unchanged |
| LlamaIndex | Dormant legacy lexical retrieval | Manifest sources and optional local index | Source locations and lexical anchors | Explicit `-IncludeRetrieval` diagnostics only | Default task routing or ownership decisions | ADR-0007, agent_gate, source/tests | `devbrain_regression_matrix.ps1 -IncludeRetrieval` | Mistaken for current/active memory | Dormant; may be missing or stale |
| LightRAG | Dormant legacy relationship retrieval | Manifest focus sources and optional local graph | Relationship hints and validation targets | Explicit `-IncludeRetrieval` diagnostics only | Default task routing or deterministic execution | ADR-0007, agent_gate, AGENTS, source/tests | `devbrain_regression_matrix.ps1 -IncludeRetrieval` | Mistaken for current/active memory | Dormant; may be missing or stale |
| LangGraph / `agent_gate.py` | Deterministic routing and execution guardrails | Task text, known root cause, repo paths, strict rules | Mode, first-touch files, stop conditions, validation targets | Risky execution, DB/migration, RBAC, payment, queue, Telegram security/storage, CI/deploy | Simple known-root-cause local edits | Source/tests, user-confirmed narrow override | `devbrain_acceptance.ps1` | Can over-gate simple work | Strict only when risk requires |
| Skills | Domain expertise and workflow advice | Task intent, skill instructions, relevant source | Checklists, domain-specific plan, validation advice | UI/UX, security, Telegram Bot API, CI, testing, framework-specific work | As operating law or repo SSOT | AGENTS, PROJECT_MEMORY, source/tests, gate | Skill availability in session | Generic advice may conflict with clinic rules | Advisory layer |
| Evidence logs | Historical evaluation and incident memory | Misroutes, retrieval comparisons, readiness reviews | Evidence of what helped or failed | Concrete DevBrain evaluation or regression notes | Routine log for every task | PROJECT_MEMORY, DEVBRAIN_STATUS | File review; memory routing | Noise and stale conclusions | Log facts, promote only repeated lessons |
| PR/CI gates | Enforcement and evidence discipline | PR body, workflows, scripts, tests | Pass/fail enforcement, validation trail | Every PR and safety workflow | Architecture reasoning or product ownership | Human/model reasoning, source/tests | GitHub Actions, PR quality gate | Can be treated as reasoning | Enforce evidence, not decisions |
| Inventory / acceptance / regression scripts | Local DevBrain health checks | Filesystem, local memory status, gate scenarios; optional legacy retrieval | Active/dormant/missing, pass/warn/fail | Before risky work or when explicitly diagnosing legacy retrieval | As proof of product correctness | Product tests and source evidence | Default commands skip legacy retrieval; use `-IncludeRetrieval` to inspect it | Overclaiming "brain is perfect" | Health checks only |

## Boundary Rules

- `Automatic local memory != retrieval`: task checkpoints and selected knowledge are stored separately from the dormant LlamaIndex/LightRAG indexes.
- `LlamaIndex != LightRAG`: if explicitly inspected, LlamaIndex provides lexical lookup and LightRAG relationship hints; neither is current project truth.
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
| Graph-heavy task | `PROJECT_MEMORY.md`, local task recall, canonical sources/tests, AI Factory dossier if useful | Assuming dormant LlamaIndex/LightRAG are available |
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

Legacy retrieval checks are opt-in: add `-IncludeRetrieval` to inventory,
regression, or markdown coverage; use `-RefreshRetrieval` only when deliberately
refreshing ignored local retrieval artifacts.

What they prove:

- Inventory checks portable DevBrain files and local memory health. Legacy retrieval is reported dormant unless explicitly inspected.
- Acceptance proves `agent_gate.py` handles critical routing scenarios.
- Default regression checks inventory, acceptance, memory probes, and portable guardrails. Retrieval probes run only with `-IncludeRetrieval` and use existing artifacts.
- Default refresh checks file-backed memory and portable regression. `-RefreshRetrieval` is the only mode that invokes legacy Python retrieval entry points, without rewriting durable status policy.

What they do not prove:

- They do not prove product behavior is correct.
- They do not replace backend/frontend tests.
- They do not make LightRAG or LlamaIndex canonical truth.
- They do not make the system autonomous.

## Current Status Labels

| Label | Status | Reason |
| --- | --- | --- |
| Portable memory and guardrails | active | Repository rules, local task memory, and deterministic gate are separate layers with explicit boundaries. |
| LlamaIndex / LightRAG | dormant | ADR-0007; opt-in local diagnostics only. |
| Production autonomous brain | no | The model still performs reasoning and execution; DevBrain is support infrastructure, not an autonomous production developer. |

## Minimal Operating Formula

```text
Simple work: model + AGENTS + source/tests.
Graph-heavy work: add PROJECT_MEMORY + local task recall + direct source/test reconstruction.
Risky execution: add agent_gate + strict stop conditions.
Domain craft: add the relevant skill, but never let it override repo law.
PR safety: prove with validation and CI.
```
