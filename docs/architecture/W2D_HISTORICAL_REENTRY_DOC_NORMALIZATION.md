# W2D Historical Re-Entry Doc Normalization

## Summary

The current W2D status stack already had:

- a canonical master plan
- an aligned backlog
- a dedicated navigation landing page

The remaining navigation risk sat in three older re-entry docs that still read
like current entry points when opened directly.

This pass kept those files as historical records but added short framing that
redirects readers to the live SSOT.

## Normalized docs

- `docs/status/W2D_THREAD_HANDOFF.md`
- `docs/status/OPENHANDS_FIRST_10_TASKS.md`
- `docs/status/AI_FACTORY_OPENHANDS_PRECHECK.md`

## Decision

Older re-entry docs should remain in the repo as execution history, but they
must not compete with:

- `docs/status/W2D_STATUS_NAVIGATION_INDEX.md`
- `docs/status/AI_FACTORY_OPENHANDS_MASTER_PLAN.md`
- `docs/status/OPENHANDS_TASK_BACKLOG.md`

## Recommended next step

Move out of status-navigation cleanup and into broader docs-vs-code verification
outside the status stack, starting with `docs/API_REFERENCE.md`.
