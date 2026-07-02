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
.\ai\lightrag\scripts\run_artifacts.ps1
.\ai\lightrag\scripts\run_artifact_check.ps1
```

`run_acceptance.ps1` performs ingest, checks the relationship scenarios, and updates `docs/devbrain/DEVBRAIN_STATUS.md` only after acceptance passes.

`run_artifacts.ps1` exports local graph artifacts from the existing gitignored graph storage without requiring API keys or committing generated files:

- `entities.jsonl`
- `relationships.jsonl`
- `vector_store.jsonl`
- `doc_store.jsonl`
- `graph_store.json`
- `metadata.json`

By default artifacts are written under `ai/lightrag/indexes/lightrag_graph/artifacts/`, which is ignored by git. Set `LIGHTRAG_ARTIFACT_DIR` or pass `--output-dir` to write elsewhere. The vector store is a local sparse term-hash store for no-key DevBrain retrieval; it is not a provider embedding index.

`run_artifact_check.ps1` is read-only. It verifies required artifact files, JSON/JSONL integrity, metadata counts, source graph alignment, gitignored status, and whether `metadata.commit` matches the current `HEAD`. Use `--warn-stale` when stale artifacts should be reported as a warning instead of a failure.

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
- generated graph artifacts
- provider caches
- generated indexes

## Relationship Scope

LightRAG is for ownership chains and cross-file relationships. Use LlamaIndex fallback for simple lexical source location. Do not call the stack a unified brain unless both retrieval status and acceptance gates prove it.
