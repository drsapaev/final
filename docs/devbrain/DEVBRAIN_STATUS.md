# DevBrain Status

Operational status file for the repository's DevBrain layers. Agents must verify this file against the filesystem before assuming a retrieval layer is active.

## Active Portable Layers

| Layer | Status | Notes |
| --- | --- | --- |
| `AGENTS.md` | active | Primary repo-level operating rules. |
| `docs/devbrain/PROJECT_MEMORY.md` | active | Canonical compact project memory anchor. |
| `docs/runbooks/AGENT_CYCLIC_WORKFLOW.md` | active | Small PR execution protocol. |
| `docs/runbooks/CODEX_SUPERPOWERS_GUARD.md` | active | Local Superpowers workflow guard SSOT. |
| `.agents/skills/*` | active | Repo/user skills available when installed in the current agent session. |
| `.ai-factory/*` | active file memory | Logs, dossiers, contracts, patches, plans, and skill-context. |
| PR/CI gates | active | PR template, review gate scripts, and GitHub Actions enforce evidence discipline. |

## Local Retrieval Layers

| Layer | Current checkout status | Required verification before use |
| --- | --- | --- |
| LangGraph gate | active | `Test-Path ai/langgraph/scripts/run_agent_gate.ps1` and run through the launcher. |
| AI Factory dossiers/logs | active file-backed | Check `.ai-factory/dossiers`, `.ai-factory/logs`, `.ai-factory/patches`. |
| LlamaIndex | missing unless verified | Do not assume active unless `ai/llamaindex` and index/query commands exist. |
| LightRAG | missing unless verified | Do not assume active unless graph storage and query commands exist. |

## Active / Documented / Dormant / Missing Status

| Component | Status | Operational meaning |
| --- | --- | --- |
| `agent_gate.py` | active | Use only for gate and gate-known-root-cause modes. |
| `run_agent_gate.ps1` | active | Preferred launcher; do not call bare `python` for the gate. |
| Historical `dev_brain.py` workflows | dormant | Do not run unless restored and verified. |
| LlamaIndex docs/references | documented | Not an active retrieval source without local index evidence. |
| LightRAG evidence log | active evidence | Historical readiness/evaluation record, not proof of active graph storage. |
| LightRAG graph/query path | missing unless verified | Must be proven by filesystem checks and query command before use. |

## LlamaIndex Status

- Current status: `missing unless verified`.
- Required checks:
  - `Test-Path ai/llamaindex`
  - index storage exists
  - query command exists and runs locally
  - last indexed commit is recorded below
- Last indexed commit: `TBD`
- Last verification date: `TBD`
- Acceptance result: `not accepted in this checkout`

## LightRAG Status

- Current status: `missing unless verified`.
- Evidence file: `ai/langgraph/EVIDENCE_LIGHTRAG_READINESS.md`.
- The evidence file is a readiness/regression log, not itself graph storage.
- Required checks:
  - `Test-Path ai/lightrag`
  - graph storage exists
  - ingest manifest exists
  - query command exists and runs locally
  - last indexed commit is recorded below
- Last indexed commit: `TBD`
- Last verification date: `TBD`
- Acceptance result: `not accepted as unified brain in this checkout`

## Acceptance Gates

LightRAG or LlamaIndex may be treated as active project retrieval only after all relevant gates pass with evidence.

1. `simple locate`
   - Expected: reliably finds canonical files for a narrow known task.
   - Status: `TBD`.
2. `Telegram mixed-contract`
   - Expected: separates Bot API/UX/webhook work from token storage, security, and migration ownership.
   - Status: `TBD`.
3. `registrar payment/status persistence ownership`
   - Expected: maps frontend table/status symptoms to backend service, persistence, API DTO/read model, frontend adapter, and validation targets.
   - Status: `TBD`.

## Last Indexed Commit Placeholders

| Retrieval layer | Last indexed commit | Last verified by | Notes |
| --- | --- | --- | --- |
| AI Factory file memory | `file-backed; no index` | `TBD` | Update relevant logs/dossiers manually. |
| LlamaIndex | `TBD` | `TBD` | Missing unless verified. |
| LightRAG | `TBD` | `TBD` | Missing unless verified. |

## Known Limitations

- DevBrain memory is still partly distributed across AGENTS, runbooks, AI Factory logs, dossiers, patches, evidence files, skills, and chat history.
- Gate routing can still misclassify keyword-heavy tasks without a confirmed root-cause anchor.
- Graph retrieval should not be claimed active from documentation alone.
- LightRAG readiness evidence shows where graph retrieval would help, but does not prove current graph availability.
- For simple local fixes, direct execution is often better than invoking the full gate path.
- For risky domains, gate/handoff remains valuable, but it must allow narrow override after confirmed misroute.
