# Legacy Markdown Indexing Policy

This policy applies only to the dormant LlamaIndex and LightRAG tools described
by ADR-0007. It does not govern the local automatic-memory store, which keeps
task checkpoints and selected knowledge outside the repository tree.

## Default behavior

Legacy retrieval is dormant. Inventory, coverage, regression, and refresh skip
index reads or writes unless explicitly requested. A missing index is never
created by a diagnostic command, and the presence of an index or successful
smoke run does not change the durable dormant policy.

Use the opt-in commands only when deliberately inspecting or maintaining a
legacy index:

```powershell
.\scripts\devbrain_inventory.ps1 -IncludeRetrieval
.\scripts\devbrain_markdown_index_coverage.ps1 -IncludeRetrieval
.\scripts\devbrain_regression_matrix.ps1 -IncludeRetrieval
.\scripts\devbrain_refresh_memory.ps1 -RefreshRetrieval
```

Explicit freshness checks read commit metadata from the generated artifacts,
not old Markdown status claims. Refresh uses the canonical Python launcher and
does not pass `--update-status`. Generated output remains in ignored local
storage and must not be committed.

## Optional legacy coverage tiers

If retrieval is explicitly reactivated for a local investigation, retain the
old coverage split:

### Broad LlamaIndex sources

- `AGENTS.md`
- `docs/devbrain/*.md`
- `docs/runbooks/*.md`
- `docs/dev/*.md`
- `.ai-factory/logs/*.md`
- `.ai-factory/dossiers/*.md`
- `.ai-factory/patches/*.md`

### Curated LightRAG sources

- `docs/devbrain/PROJECT_MEMORY.md`
- `docs/devbrain/MEMORY_ROUTING.md`
- `docs/devbrain/DEV_BRAIN_ROLE_MAP.md`
- `docs/devbrain/MARKDOWN_INDEXING_POLICY.md`
- runbooks with durable ownership or routing rules
- AI Factory logs or dossiers explicitly promoted through memory routing

Do not index generated docs, stale exploratory drafts, archive snapshots,
temporary notes, or historical reports without current operational value.

## Optional legacy indexing workflow

When a local legacy index is intentionally maintained:

1. Decide whether the Markdown is durable, temporary evidence, or generated.
2. Run coverage with `-IncludeRetrieval`.
3. Run refresh with `-RefreshRetrieval` only when the artifacts should be rebuilt.
4. Inspect generated artifact commit metadata and keep the output ignored.
5. Treat retrieved content as a hint; source, tests, migrations, route
   registries, and CI gates remain authoritative.
