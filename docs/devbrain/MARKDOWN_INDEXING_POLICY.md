# Markdown Indexing Policy

Purpose: keep DevBrain aware of durable markdown knowledge without turning
retrieval into an index of every temporary note.

This policy is about local retrieval ingest, not model training. LlamaIndex and
LightRAG remember only repository files that are included in their manifests and
refreshed locally.

## Core Rule

Index markdown by durability and retrieval value.

- LlamaIndex should cover broad durable markdown for source lookup.
- LightRAG should stay curated around ownership, routing, and relationship
  knowledge.
- Temporary or stale markdown should not become trusted DevBrain memory just
  because it exists.

## Tiers

### Tier 1: Broad LlamaIndex Markdown

These files are expected to be covered by LlamaIndex:

- `AGENTS.md`
- `docs/devbrain/*.md`
- `docs/runbooks/*.md`
- `docs/dev/*.md`
- `.ai-factory/logs/*.md`
- `.ai-factory/dossiers/*.md`
- `.ai-factory/patches/*.md`

Use this tier for "where is this documented?" and local source lookup.

### Tier 2: Curated LightRAG Markdown

These files should enter LightRAG only when they carry durable relationship or
ownership value:

- `docs/devbrain/PROJECT_MEMORY.md`
- `docs/devbrain/MEMORY_ROUTING.md`
- `docs/devbrain/DEV_BRAIN_ROLE_MAP.md`
- `docs/devbrain/MARKDOWN_INDEXING_POLICY.md`
- runbooks that define ownership or routing behavior
- AI Factory logs/dossiers promoted by memory routing

Use this tier for "which owner/first-touch/validation chain applies?"

### Tier 3: Not Indexed By Default

Do not automatically trust:

- generated docs;
- stale exploratory drafts;
- archive snapshots;
- temporary notes;
- large historical reports with no current operational value.

Promote them through `docs/devbrain/MEMORY_ROUTING.md` before relying on them.

## New Markdown Workflow

When a new `.md` file is created:

1. Decide whether it is durable memory, temporary evidence, or generated output.
2. If it belongs under a Tier 1 directory, LlamaIndex should cover it through
   directory indexing.
3. If it contains ownership or routing relationships, add a curated LightRAG
   source or priority focus concept.
4. Run:

```powershell
.\scripts\devbrain_markdown_index_coverage.ps1
.\scripts\devbrain_refresh_memory.ps1
```

5. Check that `.\scripts\devbrain_regression_matrix.ps1` has no unexpected
   stale-index or markdown-coverage warnings.

## Non-Goals

- Do not index every markdown file in the repository by default.
- Do not use retrieval results as authority over source code, tests, migrations,
  route registries, or CI gates.
- Do not commit generated LlamaIndex or LightRAG storage/artifacts.
