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
| LlamaIndex | active local fallback | `ai/llamaindex` exists; smoke passed without external API; generated storage remains gitignored. |
| LightRAG | active relationship fallback | `ai/lightrag` exists; relationship graph acceptance passed; generated graph storage remains gitignored. |

## Current Main Acceptance

- Main merge commit: `f4ea5b73dc13858c0baf2d8456bdc7a8f1096fe3`
- Retrieval layer commit: `3e11d2c1bc9b9f01a2c26a6ea3bf2504b76387a7`
- Inventory: `passed`
- Guardrail acceptance: `pass: 5`, `warn: 0`, `fail: 0`
- LlamaIndex: `active local fallback`
- LightRAG: `active relationship fallback`
- Unified DevBrain status: `portable accepted in this checkout`
- Limitation: `not a production autonomous brain`

## Active / Documented / Dormant / Missing Status

| Component | Status | Operational meaning |
| --- | --- | --- |
| `agent_gate.py` | active | Use only for gate and gate-known-root-cause modes. |
| `run_agent_gate.ps1` | active | Preferred launcher; do not call bare `python` for the gate. |
| Historical `dev_brain.py` workflows | dormant | Do not run unless restored and verified. |
| LlamaIndex portable retrieval | active local fallback | Uses `ai/llamaindex` scripts; no-key smoke passed; generated storage is gitignored. |
| LightRAG evidence log | active evidence | Historical readiness/evaluation record, not proof of active graph storage. |
| LightRAG relationship graph | active relationship fallback | Uses `ai/lightrag` scripts; acceptance passed; generated graph storage is gitignored. |

## LlamaIndex Status

- Current status: `active local fallback`.
- Required checks:
  - `Test-Path ai/llamaindex`
  - `Test-Path ai/llamaindex/scripts/query.py`
  - `Test-Path ai/llamaindex/scripts/ingest.py`
  - `Test-Path ai/llamaindex/storage/devbrain_index.json`
  - `./ai/llamaindex/scripts/run_smoke.ps1`
- Last indexed commit: `3e11d2c1bc9b9f01a2c26a6ea3bf2504b76387a7`
- Last verification date: `2026-05-25T17:47:52+00:00`
- Indexed document count: `1501`
- Acceptance result: `simple locate smoke passed in no-key fallback mode`
- Smoke query: `Where is runtime API/WS origin resolution implemented on the frontend?`
- Smoke result: `frontend/src/api/runtime.js`

## LightRAG Status

- Current status: `active relationship fallback`.
- Evidence file: `ai/langgraph/EVIDENCE_LIGHTRAG_READINESS.md`.
- Relationship graph storage: `ai/lightrag/indexes/lightrag_graph/graph.json` (gitignored).
- Required checks:
  - `Test-Path ai/lightrag`
  - `Test-Path ai/lightrag/scripts/query.py`
  - `Test-Path ai/lightrag/scripts/ingest.py`
  - `Test-Path ai/lightrag/indexes/lightrag_graph/graph.json`
  - `./ai/lightrag/scripts/run_acceptance.ps1`
- Last indexed commit: `3e11d2c1bc9b9f01a2c26a6ea3bf2504b76387a7`
- Last verification date: `2026-05-25T17:47:58+00:00`
- Indexed document count: `1499`
- Relationship concept count: `9`
- Relationship edge count: `4658`
- Acceptance result: `simple locate, Telegram mixed-contract, registrar payment/status persistence, Alembic migration, notification anti-noise, and queue identity scenarios passed`
- Provider mode: `no-key fallback; DeepSeek bridge optional when DEEPSEEK_API_KEY is set`

## Acceptance Gates

LightRAG or LlamaIndex may be treated as active project retrieval only after all relevant gates pass with evidence.

1. `simple locate`
   - Expected: reliably finds canonical files for a narrow known task.
   - Status: `passed via LightRAG acceptance`.
2. `Telegram mixed-contract`
   - Expected: separates Bot API/UX/webhook work from token storage, security, and migration ownership.
   - Status: `passed via LightRAG acceptance`.
3. `registrar payment/status persistence ownership`
   - Expected: maps frontend table/status symptoms to backend service, persistence, API DTO/read model, frontend adapter, and validation targets.
   - Status: `passed via LightRAG acceptance`.
4. `Alembic migration ownership`
   - Expected: maps SQLAlchemy/table gaps to new Alembic revision ownership and migration validation.
   - Status: `passed via LightRAG acceptance`.
5. `notification catalog anti-noise ownership`
   - Expected: maps notification preferences, mute, snooze, and DND work to catalog/settings/runtime policy ownership.
   - Status: `passed via LightRAG acceptance`.
6. `queue identity/fairness ownership`
   - Expected: maps queue specialist/doctor identity work to backend queue/service ownership and validation.
   - Status: `passed via LightRAG acceptance`.

## How To Verify Guardrail Behavior

Use the local guardrail acceptance checker before changing DevBrain routing rules:

```powershell
.\scripts\devbrain_acceptance.ps1
```

The checker is read-only. It runs `ai/langgraph/scripts/run_agent_gate.ps1` against critical routing scenarios and prints `PASS`, `WARN`, or `FAIL` per scenario. It does not require LlamaIndex or LightRAG, does not run product tests, and exits non-zero only when a core guardrail expectation is clearly violated.

## Last Indexed Commit Placeholders

| Retrieval layer | Last indexed commit | Last verified by | Notes |
| --- | --- | --- | --- |
| AI Factory file memory | `file-backed; no index` | `TBD` | Update relevant logs/dossiers manually. |
| LlamaIndex | `3e11d2c1bc9b9f01a2c26a6ea3bf2504b76387a7` | `2026-05-25T17:47:52+00:00` | Active local fallback; smoke passed without external API. |
| LightRAG | `3e11d2c1bc9b9f01a2c26a6ea3bf2504b76387a7` | `2026-05-25T17:47:58+00:00` | Active relationship fallback; acceptance passed without external API. |

## Known Limitations

- DevBrain memory is still partly distributed across AGENTS, runbooks, AI Factory logs, dossiers, patches, evidence files, skills, and chat history.
- Gate routing can still misclassify keyword-heavy tasks without a confirmed root-cause anchor.
- Graph retrieval should not be claimed active from documentation alone.
- LightRAG readiness evidence shows where graph retrieval would help, but does not prove current graph availability.
- For simple local fixes, direct execution is often better than invoking the full gate path.
- For risky domains, gate/handoff remains valuable, but it must allow narrow override after confirmed misroute.
