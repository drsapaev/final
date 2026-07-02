# LlamaIndex DevBrain Retrieval

Portable local retrieval layer for DevBrain context. The scripts in this folder are safe to run without external API keys: they build a gitignored local lexical index from the repository manifest and can later be upgraded to use real LlamaIndex packages.

This layer starts from the canonical memory/status anchors:

- `AGENTS.md`
- `docs/devbrain/PROJECT_MEMORY.md`
- `docs/devbrain/DEVBRAIN_STATUS.md`

## What Is Committed

- scripts
- manifest
- docs
- `.env.example`
- `requirements.txt`

## What Is Not Committed

- `.env`
- `.venv`
- `storage/`
- `indexes/`
- generated query/cache artifacts

## Commands

Run from the repository root:

```powershell
.\ai\llamaindex\scripts\run_ingest.ps1
.\ai\llamaindex\scripts\run_query.ps1 "Where is runtime API/WS origin resolution implemented on the frontend?"
.\ai\llamaindex\scripts\run_smoke.ps1
```

`run_smoke.ps1` runs ingest, performs a no-key simple-locate query, and updates `docs/devbrain/DEVBRAIN_STATUS.md` only after the smoke passes.

## Status Rules

- LlamaIndex is active only when this folder exists, scripts exist, smoke passes, and `DEVBRAIN_STATUS.md` records the last indexed commit.
- LightRAG remains separate. Do not mark LightRAG active because LlamaIndex fallback retrieval works.
- This layer is retrieval support, not a replacement for source/test evidence or `agent_gate.py` guardrails.
