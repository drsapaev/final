# DevBrain Memory Routing

This file is the routing table for durable project memory. It keeps DevBrain useful as project memory, retrieval, routing, guardrails, and evidence without turning every observation into global policy.

For component responsibilities and boundaries, use `docs/devbrain/DEV_BRAIN_ROLE_MAP.md`.

## Core Rule

Route memory to the narrowest durable layer that can use it.

- One-off observation -> log or dossier.
- Repeated ownership fact -> `docs/devbrain/PROJECT_MEMORY.md`.
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

### LlamaIndex

LlamaIndex is local fallback retrieval. It remembers what is in its manifest and generated local index.

Good fit:
- source location;
- lexical anchors;
- "where is X implemented?";
- docs/runbooks/source file lookup.

It does not remember chat unless the chat decision is written into an indexed repo file.

### LightRAG

LightRAG is relationship retrieval. It remembers relationship concepts, canonical anchors, first-touch files, verification targets, and generated local graph artifacts.

Good fit:
- ownership chains;
- mixed-contract routing;
- repeated cross-file relationships;
- migration/queue/payment/notification/Telegram/routing ownership.

It does not create durable project memory on its own. It builds graph artifacts from indexed repo sources.

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
| One-off task observation | `.ai-factory/logs` or `.ai-factory/dossiers` | Useful context discovered once | Yes, if the file is indexed and trusted retrieval needs it | Dossier/log reviewed; optional retrieval refresh |
| Repeated ownership fact | `docs/devbrain/PROJECT_MEMORY.md` | Same ownership fact affects multiple tasks | Yes | `devbrain_refresh_memory.ps1`; regression matrix |
| Durable agent behavior rule | `AGENTS.md` | Rule must affect all agents before editing | Yes | `git diff --check`; regression matrix if DevBrain behavior changes |
| Retrieval/index status | `docs/devbrain/DEVBRAIN_STATUS.md` | Smoke, acceptance, artifact, or inventory status changes | No, if status-only bookkeeping; yes if source/memory changed | Official status flow; regression matrix |
| Repeated gate misroute | `ai/langgraph/scripts/agent_gate.py` plus acceptance scenario | Same routing bug appears more than once or hits risky domain | Yes | `devbrain_acceptance.ps1`; regression matrix |
| Risky domain stop condition | `AGENTS.md`, `PROJECT_MEMORY.md`, or `agent_gate.py` | Stop condition should be durable | Yes | Gate acceptance; targeted scenario |
| Historical patch evidence | `.ai-factory/patches` | PR/patch completed and evidence may matter later | Optional | Patch note review; PR checks |
| Graph-heavy research | `.ai-factory/dossiers` | Context packet needed for multi-file/risky task | Optional | Dossier has anchors, first-touch, validation |
| LlamaIndex source lookup | `ai/llamaindex/data/manifest.json` source files | Indexed source set changes | Yes | `ai/llamaindex/scripts/run_smoke.ps1` |
| LightRAG relationship concept | `ai/lightrag/data/manifest.json` priority focus source or indexed memory/source | Ownership graph needs a stable concept | Yes | `ai/lightrag/scripts/run_acceptance.ps1`; artifact check |
| PR evidence discipline | `.github/pull_request_template.md`, PR gate scripts, workflows | Review evidence requirement changes | No, unless indexed docs changed | PR review gate; CI |

## Promotion Rules

1. Start with the smallest memory target.
2. Promote only when the same fact has repeated value.
3. Do not promote one-off observations into global agent rules.
4. Do not promote stale docs over executable source, tests, migrations, or route registries.
5. When memory changes affect retrieval, run:

```powershell
.\scripts\devbrain_refresh_memory.ps1
```

## Retrieval Refresh Rules

Run the refresh wrapper after changes to:

- `AGENTS.md`;
- `docs/devbrain/PROJECT_MEMORY.md`;
- `docs/devbrain/MEMORY_ROUTING.md`;
- `docs/devbrain/MEMORY_CAPTURE_TEMPLATE.md`;
- `docs/runbooks/*` used by agents;
- `.ai-factory/*` logs/dossiers/patches that should be retrievable;
- `ai/llamaindex/data/manifest.json`;
- `ai/lightrag/data/manifest.json`;
- `agent_gate.py` or guardrail acceptance behavior.

For product code changes, refresh only when the change affects canonical ownership, route contracts, migrations, queue/payment/notification/Telegram/EMR/lab ownership, or other graph-heavy retrieval anchors.
