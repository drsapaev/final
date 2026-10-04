# DevBrain Memory Routing

This file routes durable repository memory and machine-local task memory without turning every observation into global policy.

For component responsibilities and boundaries, use `docs/devbrain/DEV_BRAIN_ROLE_MAP.md`.

## Core Rule

Route memory to the narrowest durable layer that can use it.

- One-off observation -> log or dossier.
- Repeated ownership fact -> `docs/devbrain/PROJECT_MEMORY.md`.
- Current task state and source-backed local knowledge -> the shared local store through `scripts/run_devbrain_memory.ps1`, following the lifecycle in `AGENTS.md`.
- Reviewed repo-wide facts/lessons portable through Git -> `docs/devbrain/memory/curated.json` with pinned source hashes.
- Repeated gate misroute -> `agent_gate.py` routing rule plus acceptance scenario.
- Retrieval/index status -> `docs/devbrain/DEVBRAIN_STATUS.md`.
- Durable agent behavior rule -> `AGENTS.md`.

Do not put raw chat history into `AGENTS.md`. Convert it into a small fact, decision, failure pattern, runbook step, evidence log, or routing rule first.

## Capture Template

Use `docs/devbrain/MEMORY_CAPTURE_TEMPLATE.md` before promoting a chat observation, PR lesson, audit finding, or routing failure into durable DevBrain memory. The template forces the agent to name evidence, target layer, reindex need, validation command, and stop conditions before editing memory.

For local note creation, use:

```powershell
.\scripts\devbrain_new_memory_note.ps1 -Target logs -Title "short memory note title"
```

Use `-Preview` to verify the target path without writing a note. The helper only creates a routed AI Factory note; it does not promote facts into `PROJECT_MEMORY.md`, update `agent_gate.py`, refresh indexes, or mark retrieval status fresh.

For intentional memory-health canaries, use
`docs/devbrain/MEMORY_PROBE_PROTOCOL.md`. Memory probe entries belong in
`.ai-factory/logs/memory-probes.md` unless a repeated lesson from the probe must
be promoted through the normal routing table.

### Automatic task memory protocol

Repo-aware agents call `scripts/run_devbrain_memory.ps1` for task checkpoints
and bounded local recall under the lifecycle in `AGENTS.md`. Begin only a new
substantive task; use exact-task recall to continue; capture at boundaries,
milestones, blockers, and before handoff/final. This is an agent instruction,
not a client event hook or background conversation analyzer.

The store is shared by worktrees of this clone, but not independent clones or
computers. Checkpoints are task state, not repository policy. Source hashes
describe file state; source, tests, migrations, runbooks, and user
authorization remain authoritative. Never store PHI/PII, credentials,
transcripts, or large raw output.

`curated.json` stores reviewed, repo-scoped facts/lessons with relative anchors
and pinned SHA-256 values. It has no worktree or session metadata. The helper
reads it with local memory; stale sources suppress the claim and uncommitted
curated files are worktree-only hints. Local capture never edits tracked files.
Promote durable ownership decisions/failure patterns to `PROJECT_MEMORY.md`
and portable source-backed facts to `curated.json` through a reviewed change.

## Memory Targets

### `AGENTS.md`

Use for short, mandatory operating rules that every repo-aware agent must follow before editing.

Good fit:
- hard safety rules;
- strict mode triggers;
- execution mode selection;
- project-wide rule references.

Bad fit:
- long history;
- detailed audit trails;
- one-off PR notes;
- generated retrieval status.

### `docs/devbrain/PROJECT_MEMORY.md`

Use for compact, durable SSOT decisions and recurring ownership chains.

Good fit:
- canonical ownership decisions;
- known failure patterns;
- routing invariants;
- migration/Alembic ownership rules;
- queue/payment/notification/Telegram/routing SSOT facts.

Update this when the same fact is likely to matter again.

### `docs/devbrain/memory/curated.json`

Use for compact, source-backed repo facts or lessons that should travel with
the repository. Every record needs relative source anchors and author-pinned
hashes. Never put task/session state, machine paths, raw transcripts, PHI/PII,
or secrets here; update through a normal reviewed PR.

### `docs/devbrain/DEVBRAIN_STATUS.md`

Use for current DevBrain layer status, verification evidence, indexed commits, acceptance results, and known limitations.

Good fit:
- whether LlamaIndex/LightRAG is active;
- last indexed commit and verification time;
- acceptance gate status;
- artifact freshness commands;
- dormant/missing layer notes.

Do not store domain decisions here unless they describe DevBrain status itself.

### `.ai-factory/logs`

Use for chronological evidence and implementation status that may be useful later but is not yet a stable rule.

Good fit:
- audit notes;
- incident-style observations;
- rollout status;
- transient risk notes;
- validation summaries.

### `.ai-factory/dossiers`

Use for curated context packets that explain a task or subsystem.

Good fit:
- graph-heavy context;
- ownership maps for a planned change;
- relevant source/test lists;
- handoff-style research without immediate code changes.

### `.ai-factory/patches`

Use for patch histories and implementation evidence.

Good fit:
- what changed;
- why it changed;
- validation evidence;
- follow-up risks.

Do not treat patch files as canonical ownership if `PROJECT_MEMORY.md`, source code, tests, or runbooks disagree.

### `agent_gate.py`

Use for deterministic routing and guardrail behavior when repeated misroutes or risky domains need enforcement.

Good fit:
- keyword classification for risky domains;
- first-touch ownership;
- stop conditions;
- mode selection rules;
- acceptance scenario coverage.

Only promote a memory fact into `agent_gate.py` after it is stable enough to automate.

### LlamaIndex (dormant legacy retrieval)

LlamaIndex is dormant under ADR-0007. Its manifest and generated local index
are not part of default task startup, inventory, regression, or refresh.

Good fit:
- source location;
- lexical anchors;
- "where is X implemented?";
- docs/runbooks/source file lookup.

Missing artifacts are not created by diagnostic commands. An explicit
`devbrain_refresh_memory.ps1 -RefreshRetrieval` may write ignored local index
storage. It does not make LlamaIndex active or change the durable policy.

### LightRAG (dormant legacy retrieval)

LightRAG is dormant under ADR-0007. Its manifest and generated local graph are
not part of default task startup, inventory, regression, or refresh.

Good fit:
- ownership chains;
- mixed-contract routing;
- repeated cross-file relationships;
- migration/queue/payment/notification/Telegram/routing ownership.

Diagnostic commands do not create a missing graph. An explicit
`devbrain_refresh_memory.ps1 -RefreshRetrieval` may export ignored local
artifacts from an existing graph. Neither acceptance output nor artifact
presence changes the durable dormant policy.

### CI / PR Gates

Use CI/PR gates for enforceable evidence discipline.

Good fit:
- PR template completeness;
- review quality gate;
- required check behavior;
- static sweeps;
- validation proof.

CI gates should enforce process and safety. They should not become a substitute for domain memory.

## Routing Table

| Knowledge type | Memory target | Update trigger | Reindex needed | Validation |
| --- | --- | --- | --- | --- |
| One-off task observation | Local task checkpoint or `.ai-factory/logs` / `.ai-factory/dossiers` | Resume state or useful context from one task | No for local checkpoints; legacy index only by explicit request | `run_devbrain_memory.ps1 -Action Recall` or dossier review |
| Portable source-backed fact/lesson | `docs/devbrain/memory/curated.json` | Confirmed fact should travel with Git | No | Helper recall/export plus anchor hash and source review |
| Repeated ownership fact | `docs/devbrain/PROJECT_MEMORY.md` | Same fact affects multiple tasks | No for normal work; legacy index only by explicit request | Source/test review; default `devbrain_refresh_memory.ps1` |
| Durable agent behavior rule | `AGENTS.md` | Rule must affect all agents before editing | No for normal work; legacy index only by explicit request | `git diff --check`; default regression matrix |
| Retrieval/index status | `docs/devbrain/DEVBRAIN_STATUS.md` | Explicit diagnostic or artifact metadata changes | No; historical status text does not make an index fresh | `devbrain_inventory.ps1 -IncludeRetrieval`; inspect artifact metadata |
| Repeated gate misroute | `ai/langgraph/scripts/agent_gate.py` plus acceptance scenario | Same routing bug appears more than once or hits risky domain | No for default checks | `devbrain_acceptance.ps1`; default regression matrix |
| Risky domain stop condition | `AGENTS.md`, `PROJECT_MEMORY.md`, or `agent_gate.py` | Stop condition should be durable | Yes | Gate acceptance; targeted scenario |
| Historical patch evidence | `.ai-factory/patches` | PR/patch completed and evidence may matter later | Optional | Patch note review; PR checks |
| Graph-heavy research | `.ai-factory/dossiers` | Context packet needed for multi-file/risky task | Optional | Dossier has anchors, first-touch, validation |
| LlamaIndex source lookup | Dormant legacy manifest/index | Explicit request to maintain local lexical retrieval | Only for that local index | `devbrain_refresh_memory.ps1 -RefreshRetrieval`; review ignored artifact metadata |
| LightRAG relationship concept | Dormant legacy manifest/graph | Explicit request to maintain local relationship retrieval | Only for that local graph/artifacts | `devbrain_refresh_memory.ps1 -RefreshRetrieval`; review ignored artifact metadata |
| PR evidence discipline | `.github/pull_request_template.md`, PR gate scripts, workflows | Review evidence requirement changes | No, unless indexed docs changed | PR review gate; CI |

## Promotion Rules

1. Start with the smallest memory target.
2. Promote only when the same fact has repeated value.
3. Do not promote one-off observations into global agent rules.
4. Do not promote stale docs over executable source, tests, migrations, or route registries.
5. For normal task memory, use the local helper and keep the checkpoint scoped to its task. The default health check is:

```powershell
.\scripts\devbrain_refresh_memory.ps1
```

It checks file-backed memory and portable guardrails only. Run dormant legacy
indexes only when explicitly requested:

```powershell
.\scripts\devbrain_refresh_memory.ps1 -RefreshRetrieval
```

## Retrieval Refresh Rules

The default refresh does not ingest or query legacy indexes. `-RefreshRetrieval`
is an explicit opt-in for maintaining ignored local artifacts after changes to:

- `AGENTS.md`;
- `docs/devbrain/PROJECT_MEMORY.md`;
- `docs/devbrain/MEMORY_ROUTING.md`;
- `docs/devbrain/MEMORY_CAPTURE_TEMPLATE.md`;
- `docs/runbooks/*` used by agents;
- `.ai-factory/*` logs/dossiers/patches that should be retrievable;
- `ai/llamaindex/data/manifest.json`;
- `ai/lightrag/data/manifest.json`;
- `agent_gate.py` or guardrail acceptance behavior.

For product code changes, do not refresh dormant retrieval by default. If a user
explicitly requests it, keep generated output in ignored local storage and do
not infer current system readiness from a successful smoke or acceptance run.
