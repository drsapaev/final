# Wave 2C Queue Fairness Analysis

Date: 2026-03-07
Mode: analysis-first, docs-only

## Executive Summary

Runtime fairness is primarily driven by:

- `priority DESC`
- `queue_time ASC`

Queue number is important as a ticket label and for some operator-facing views,
but it is not the authoritative fairness key across the whole system.

This partly matches the design intent in
`docs/ONLINE_QUEUE_SYSTEM_IMPLEMENTATION.md`, but runtime behavior contains
explicit exceptions and alternate orderings.

## Evidence Matrix

| Evidence | Runtime behavior | Fairness implication |
|---|---|---|
| `backend/app/repositories/queue_position_api_repository.py` | `list_position_entries()` orders by `priority.desc(), queue_time` | Patient-facing queue position honors fairness timestamp first, then priority |
| `backend/app/services/queue_position_notifications.py` | `_count_people_ahead()` compares higher `priority` first, then earlier `queue_time` | Notifications follow fairness timestamp, not ticket number |
| `backend/app/api/v1/endpoints/registrar_integration.py` | registrar read model explicitly sorts by `queue_time.asc(), id.asc()` | Registrar view in at least one major read path treats older registration time as authoritative |
| `backend/app/api/v1/endpoints/qr_queue.py` | `restore_entry_to_next()` sets `priority = 1` and status back to `waiting` | A restored entry can move ahead without changing `number` |
| `backend/app/repositories/queue_reorder_api_repository.py` | `list_active_entries()` orders by `number` | Reorder tooling still uses ticket number as the active ordering baseline |
| `backend/app/services/qr_queue_service.py` | current queue summary finds `last_served` by highest `number` among `called/served` | Some operator read models still think in ticket-number order |

## Fairness Model by Concern

| Concern | Runtime source of truth | Notes |
|---|---|---|
| "Who is ahead of me?" | `priority`, then `queue_time` | This is the clearest fairness implementation |
| "Which waiting row should the patient-facing position API show first?" | `priority`, then `queue_time` | Aligned with design intent |
| Registrar list of active waiting rows | `queue_time` in inspected flow | Mostly aligned |
| Reorder admin tooling | `number` | Not fully aligned with queue-time fairness |
| Restored or force-majeure entries | `priority` override | Explicit policy exception to pure queue-time ordering |

## Validation Against Design Intent

### Preserved

- `queue_time` is treated as a fairness timestamp in position-oriented flows.
- New queue entries in batch / assignment flows explicitly set current business
  time rather than backfilling an earlier timestamp.
- QR edit flows preserve original time for unchanged services and assign current
  time to newly added services.

### Drift / Ambiguity

- Queue number and visible queue position can diverge.
- Reorder tooling still anchors on `number`, not `queue_time`.
- `restore_entry_to_next()` intentionally bypasses raw ticket-order fairness via
  `priority = 1`.
- Some legacy or summary views still use `number` or highest-number heuristics.

## Fairness Risks

1. Ticket number can imply one order while patient-facing fairness logic uses
   another.
2. Restore/reorder flows can move entries without reassigning numbers.
3. Duplicate-policy gaps can let the same patient obtain multiple active rows,
   which indirectly weakens fairness.

## Verdict

Fairness is only partially centralized.

The runtime system already treats:

- `queue_time` as fairness intent
- `priority` as a policy override
- `number` as a ticket and operator-ordering key

Because of that, `W2C-MS-005` cannot be treated as "just extract the number
allocator". Any numbering refactor must first preserve or redefine how ticket
number relates to:

- patient-visible fairness
- reorder behavior
- restore-as-next behavior
- force-majeure priority behavior
