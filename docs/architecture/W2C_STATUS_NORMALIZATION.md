# Wave 2C Status Normalization

Date: 2026-03-07
Mode: phase-1 design baseline

## Goal

Introduce a central status vocabulary layer without changing persisted queue data or
external API behavior.

## Raw Statuses Found In Runtime Code

### Normative statuses from `ONLINE_QUEUE_SYSTEM_IMPLEMENTATION.md`

- `waiting`
- `called`
- `completed`
- `cancelled`

### Additional statuses already present in code

- `in_service`
- `diagnostics`
- `served`
- `incomplete`
- `no_show`
- `canceled`
- `rescheduled`
- `in_progress`

## Canonical Statuses For Internal Comparison

Phase 1 canonical status set:

- `waiting`
- `called`
- `in_service`
- `diagnostics`
- `served`
- `incomplete`
- `no_show`
- `cancelled`
- `rescheduled`

## Alias Map

| Raw status | Canonical status | Reason |
|---|---|---|
| `canceled` | `cancelled` | spelling drift only |
| `in_progress` | `in_service` | queue row is in doctor-facing active treatment state |
| `completed` | `served` | terminal queue semantics drift between doc and runtime code |

## Compatibility Strategy

1. Keep raw stored statuses untouched.
2. Keep external API payloads untouched in Phase 1.
3. Use central raw-status groups for read-only queries, matching current behavior exactly.
4. Use canonicalization only for internal comparisons and documentation.
5. Do not backfill historical records.

## Central Raw-Status Groups To Preserve Current Behavior

These groups are intentionally not identical. They reflect current runtime behavior.

- duplicate and queue-limit active statuses:
  - `waiting`, `called`
- reorder active statuses:
  - `waiting`, `called`
- queue position visible statuses:
  - `waiting`, `called`, `in_service`, `diagnostics`
- session reuse statuses:
  - `waiting`, `called`, `in_service`

## Unresolved Ambiguities

1. `served` vs `completed`
2. `in_service` vs `in_progress`
3. whether `rescheduled` is a queue terminal state or only a visit-link marker
4. whether position reads should eventually include `in_progress` as an alias for `in_service`

## Human Review Threshold

If Phase 2 or later wants to change persisted queue status values, query filters, or
public status payloads based on this normalization layer, that change requires human review.

## Phase 1 Implementation

Implemented in:

- `backend/app/services/queue_status.py`
- `backend/app/repositories/queue_position_api_repository.py`
- `backend/app/repositories/queue_reorder_api_repository.py`

Current code usage:

- `POSITION_VISIBLE_RAW_STATUSES` powers queue-position read filtering
- `REORDER_ACTIVE_RAW_STATUSES` powers reorder active-entry filtering
- `normalize_queue_status()` is available for internal alias comparison and tests

What Phase 1 intentionally does not do:

- expand read filters to include alias values automatically
- rewrite existing database rows
- alter endpoint response payloads
