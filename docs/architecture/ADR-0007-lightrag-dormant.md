# ADR-0007: LightRAG and LlamaIndex are dormant — portable DevBrain is canonical

**Date**: 2026-07-04
**Status**: Accepted
**Supersedes**: Implicit assumption that LightRAG/LlamaIndex are active retrieval layers

## Context

The clinic repo has three "DevBrain" retrieval layers documented in
`docs/devbrain/DEVBRAIN_STATUS.md`:

1. **Portable DevBrain** — `AGENTS.md`, `CLAUDE.md`, `docs/devbrain/PROJECT_MEMORY.md`,
   `docs/runbooks/*`, `.cursor/rules/*`. Active. Read directly by AI agents.
2. **LightRAG** — `ai/lightrag/` with ingest/query/acceptance scripts.
   PowerShell-only (`run_ingest.ps1`, `run_query.ps1`). Graph storage is gitignored.
3. **LlamaIndex** — `ai/llamaindex/`. Local fallback. Storage is gitignored.

LightRAG and LlamaIndex were added in 2023 when AI agents had 8K-32K context
windows and could not read the full repo. They built a relationship graph +
vector index so agents could query "what depends on X?" without reading
everything.

In 2026, the situation changed:
- Claude Sonnet 4.5 has 200K context window (can read entire `backend/app/` in one call)
- GPT-4o has 128K context window
- Cursor's @codebase and Claude Code's built-in retrieval do semantic search natively
- The Z.ai cleanup sprint (PRs #1781-#1805) added `AGENTS.md` + `PROJECT_MEMORY.md`
  + 6 runbooks + 4 entry-point references — this covers 80% of what LightRAG provided
- LightRAG scripts are PowerShell-only — they don't run in GitHub Actions (Linux CI)
  or on Mac/Linux developer machines

## Decision

**LightRAG and LlamaIndex are dormant.** They remain in the repo for historical
reference and potential future re-activation, but:

1. **Portable DevBrain is canonical** — `AGENTS.md`, `PROJECT_MEMORY.md`, runbooks
   are the single source of truth for project memory. AI agents should read these
   files directly, not query a graph.

2. **Do NOT run LightRAG ingest in CI** — the PowerShell scripts don't work on
   Linux, and the graph would be stale within hours of any merge.

3. **Do NOT recommend LightRAG to new agents** — point them to `AGENTS.md` and
   `docs/runbooks/STAGING_VALIDATION.md` instead.

4. **Graph storage stays gitignored** — if a developer wants to build a local
   graph for exploration, they can run `ai/lightrag/scripts/run_ingest.ps1`
   locally on Windows. The output is machine-specific and should not be committed.

5. **If retrieval quality becomes a problem** (agent loses context, can't find
   files, makes wrong assumptions), the solution is:
   - First: improve `PROJECT_MEMORY.md` with the missing fact
   - Second: add a runbook section covering the confusing area
   - Third (last resort): re-evaluate modern retrieval tools (Cursor @codebase,
     Claude Code retrieval, or rewrite LightRAG scripts in Python for CI)

## Consequences

### Positive

- **Simpler mental model** — one canonical memory layer, not three
- **No stale graph risk** — agents read source files directly, always current
- **Cross-platform** — works on Linux CI, Mac, Windows without PowerShell
- **Lower maintenance** — no ingest scripts to debug, no graph storage to manage
- **Better agent context** — modern agents with 200K context can read whole
  directories; LightRAG was a workaround for 8K context

### Negative

- **Lost relationship graph** — "what depends on X?" queries now require
  `git grep` + agent reasoning instead of a graph lookup
- **Lost vector search** — semantic similarity queries ("find code like this")
  require agent's own retrieval, not a local index
- **PowerShell scripts orphaned** — `ai/lightrag/scripts/*.ps1` won't run in CI

### Mitigation

- For dependency analysis: `git grep` + modern agent's 200K context covers 95% of cases
- For semantic search: Cursor's @codebase, Claude Code's built-in retrieval
- For onboarding: `docs/runbooks/STAGING_VALIDATION.md` + `PROJECT_MEMORY.md`
  provide structured context that LightRAG would have surfaced

## Re-evaluation triggers

Revisit this decision if ANY of the following becomes true:

1. **Agent context quality degrades** — agents repeatedly miss files or make
   wrong assumptions about dependencies, AND improving `PROJECT_MEMORY.md`
   doesn't fix it
2. **Repo grows beyond 5000 files** — at that scale, even 200K context may
   struggle. Re-evaluate retrieval.
3. **Team grows beyond 5 developers** — shared graph becomes more valuable
   with more concurrent agents
4. **LightRAG scripts get ported to Python** — if someone rewrites
   `run_ingest.ps1` → `ingest.py` (cross-platform), the cost of re-activation
   drops and this decision can be revisited

## Related

- `docs/devbrain/PROJECT_MEMORY.md` — canonical compact memory
- `docs/devbrain/DEVBRAIN_STATUS.md` — marks LightRAG/LlamaIndex as dormant
- `docs/runbooks/STAGING_VALIDATION.md` — MANDATORY pre-deploy checks
- `AGENTS.md` — primary operating rules for agents
- ADR-0001 through ADR-0006 — earlier architecture decisions

## References

- LightRAG: https://github.com/HKUDS/LightRAG
- LlamaIndex: https://www.llamaindex.ai/
- Cursor @codebase: https://docs.cursor.com/@codebase
- Claude Code: https://claude.com/claude-code
