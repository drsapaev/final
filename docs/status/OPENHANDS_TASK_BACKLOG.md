# OpenHands Task Backlog

Updated: 2026-03-14
Status: aligned execution index

## How to use this file

This backlog is no longer an early Wave 1 / Wave 2 snapshot.

Use [AI_FACTORY_OPENHANDS_MASTER_PLAN.md](C:/final/docs/status/AI_FACTORY_OPENHANDS_MASTER_PLAN.md)
as the canonical source of truth. This file is now the shorter execution index
for the current post-W2D phase.

For the shortest navigation entry point into the current status/doc stack, use
[W2D_STATUS_NAVIGATION_INDEX.md](C:/final/docs/status/W2D_STATUS_NAVIGATION_INDEX.md).

Current program phase:

`legacy reduction + deprecation continuation + bounded cleanup`

## Status Legend

- `done`
- `active`
- `blocked`
- `pending plan-gate`
- `pending later`

## Active Execution Index

| ID | Title | Track | Risk | Status | Notes |
|---|---|---|---|---|---|
| W2D-T1 | Review-first duplicate cleanup continuation | legacy reduction | low | done | Detached endpoint/service residues removed across admin, analytics, telegram, mobile, reporting, SMS, and support surfaces |
| W2D-T2 | Safe cleanup pool exhaustion audit | legacy reduction | low | done | Remaining non-protected candidates no longer pass blind-cleanup gates |
| W2D-T3 | Master/backlog status sync | docs/status | low | done | Backlog rewritten to match current master plan and execution phase |
| W2D-T4 | Remaining residue strategic inventory | planning | medium | done | Buckets now split the remaining pool into protected and non-candidate lanes |
| W2D-T5 | Mixed-risk non-protected residue follow-up | legacy reduction | medium | done | `settings`, `activation`, and `clinic_management` were resolved through dedicated slices |
| W2D-T6 | Protected-domain residue gates | planning | high | done | Payment, auth, queue, and EMR duplicate candidates are resolved, and the final active `/api/v1/2fa/devices*` parity gate was closed by aligning published OpenAPI to the live runtime/front-end contract without router reordering |
| W2D-T7 | Product/ops-blocked legacy tails | deprecation | high | blocked | `open_day`, `close_day`, `next_ticket`, `is_paused`, `is_closed` remain intentionally blocked |
| W2D-T8 | Broader docs consolidation after residue planning | docs | low | active | Protected residue handling is exhausted; status-navigation cleanup is in good shape, the bounded `API_REFERENCE.md` verification track is effectively complete, both mounted custom API-doc helper routers are aligned, the backend-side production docs plus ops-facing compose docs now read as historical, scoped, or caveated documents, the backend env guide/template plus `ops/docker-compose.yml` and `ops/backend.entrypoint.sh` fallback-path wiring are aligned again, the startup policy decision, `ensure_admin.py` helper contract hardening, and operator command normalization are now all complete, so this lane has reached a coherent low-risk stopping point rather than another active behavior slice |

## Stabilized / Archived Tracks

These are no longer the active day-to-day queue:

| Track | Status | Notes |
|---|---|---|
| AI Factory / OpenHands setup | done | Installed and operationalized |
| Wave 1 stabilization | done / archived | Truth, docs, and baseline audit work completed |
| Wave 2C core queue architecture | done | Main allocator architecture track complete |
| Postgres alignment + `postgres_pilot` guardrail | done / guarded | CI guardrail in place and operational |

## Current Working Rules

- cleanup remains review-first and bounded
- one low-risk candidate at a time
- no broad refactors
- no runtime behavior changes unless a slice is explicitly a narrow drift fix
- no protected-domain cleanup without a separate plan-gate
- if a candidate fails mount/import/diff proof, it becomes inventory, not a deletion

## Current Known Good Verification Signal

- `cd C:\final\backend && pytest tests/test_openapi_contract.py -q` -> `14 passed`
- `cd C:\final\backend && pytest -q` -> `850 passed, 3 skipped`

## Historical Notes

Earlier W1 / W1.5 / W1.75 artifacts remain useful as records, but they are now
historical context rather than the active backlog. Treat their task tables as
archived program history, not the current execution queue.
