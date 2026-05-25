# LightRAG DevBrain Relationship Retrieval

Portable relationship-retrieval layer for DevBrain. This folder builds a local gitignored relationship graph from curated repository sources and focus-domain ownership rules.

The layer is provider-aware:

- no-key fallback mode is the default and must keep working;
- `DEEPSEEK_API_KEY` may enable an isolated dev-brain bridge later;
- embeddings and graph storage stay inside `ai/lightrag`;
- ChatGPT Plus or the Codex app must not be treated as an API key.

## Commands

Run from the repository root:

```powershell
.\ai\lightrag\scripts\run_ingest.ps1
.\ai\lightrag\scripts\run_query.ps1 "fix registrar payment status persistence ownership"
.\ai\lightrag\scripts\run_acceptance.ps1
```

`run_acceptance.ps1` performs ingest, checks the relationship scenarios, and updates `docs/devbrain/DEVBRAIN_STATUS.md` only after acceptance passes.

## Git Policy

Committed:

- scripts
- manifest
- docs
- `.env.example`
- `requirements.txt`

Ignored:

- `.env`
- `.venv`
- generated graph storage
- provider caches
- generated indexes

## Relationship Scope

LightRAG is for ownership chains and cross-file relationships. Use LlamaIndex fallback for simple lexical source location. Do not call the stack a unified brain unless both retrieval status and acceptance gates prove it.
