# Document Archive

This directory holds historical documentation that is no longer canonical
but is preserved for traceability. **Do not edit files here** — if a fact in
an archived doc becomes relevant again, restore it to a new canonical doc
under `docs/` (top level) and update this index.

## Layout

```
docs/
├── ci-cd.md                       ← canonical CI/CD reference (root-level)
├── archive/
│   ├── ci-cd-history/             ← old CI/CD docs (pre-P0.5 consolidation)
│   ├── phase-reports/             ← PHASE_2_1..PHASE_5 reports
│   ├── fix-summaries/             ← AUTH_*, QUEUE_*, ROUTE_*, etc. fix reports
│   ├── reports/                   ← audit reports, completion reports, project gaps
│   └── setup-guides/              ← ADMIN_PANEL_README, FULL_IMPLEMENTATION_PLAN, etc.
```

## Why archive instead of delete?

- AI agents (Claude, Cursor, Codex) read the repo root as the most relevant
  context. 40+ status MDs at the root polluted their context with stale
  phase-2 status info, causing them to suggest fixes for already-fixed bugs.
- The reports contain some durable facts (decisions made, why a refactor was
  done a certain way) that are useful to reference months later.
- Git history alone is not enough — agents don't browse git log.

## When to delete (not archive)

Delete a file from archive when:
1. The fact it documents is now in a canonical doc (e.g. `docs/ci-cd.md`),
   AND
2. The file has not been touched in >12 months, AND
3. A grep for the file's title returns no hits in code/comments.

## Index of most-referenced archived docs

| Old path | New path | Why archived |
|---|---|---|
| `CI-CD-README.md` | `archive/ci-cd-history/CI-CD-README.md` | Superseded by `docs/ci-cd.md` (P0.5) |
| `README-CI-CD.md` | `archive/ci-cd-history/README-CI-CD.md` | Same |
| `SETUP-CI-CD.md` | `archive/ci-cd-history/SETUP-CI-CD.md` | Same |
| `CI_CD_FINAL_STATUS_REPORT.md` | `archive/ci-cd-history/CI_CD_FINAL_STATUS_REPORT.md` | Same |
| `MASTER_TODO_LIST.md` | `archive/setup-guides/MASTER_TODO_LIST.md` | Stale TODO list — check GitHub Issues instead |
| `PROJECT_GAPS.md` | `archive/reports/PROJECT_GAPS.md` | Status as of audit; current gaps in GitHub Issues |
| `AUDIT_REPORT.md` | `archive/reports/AUDIT_REPORT.md` | One-time audit, not living doc |
| `FINAL_PROJECT_COMPLETION_REPORT.md` | `archive/reports/FINAL_PROJECT_COMPLETION_REPORT.md` | Phase-completion snapshot |

## Canonical docs (kept at repo root)

| File | Purpose |
|---|---|
| `README.md` | Project overview, setup, run |
| `CHANGELOG.md` | Release history (manual) |
| `SECURITY.md` | Security policy, vuln reporting |
| `AGENTS.md` | AI agent rules (Codex/Cursor/generic) |
| `CLAUDE.md` | Claude Code-specific instructions |
| `MIGRATIONS.md` | Alembic migration conventions |

Plus `docs/ci-cd.md` (canonical CI/CD reference, added in P0.5).
