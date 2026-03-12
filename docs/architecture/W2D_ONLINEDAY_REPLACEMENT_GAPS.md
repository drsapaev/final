# Wave 2D OnlineDay Replacement Gaps

Date: 2026-03-09
Mode: analysis-first, docs-only

## Gap matrix

| Surface | Main replacement gap | Why it blocks replacement now |
|---|---|---|
| `appointments.open_day()` | No SSOT equivalent for department/day intake control with `start_number` ownership | Existing SSOT queue paths are specialist/day oriented and do not model legacy department-level open/close semantics. |
| `appointments.stats()` | No confirmed consumer decision: retire vs redirect | Replacing a duplicate endpoint before deciding whether it can be retired would create unnecessary surface churn. |
| `appointments.close_day()` | No SSOT equivalent for department/day intake closure | Current `OnlineDay.is_open` semantics do not map 1:1 to SSOT `DailyQueue.opened_at`. |
| `queues.stats()` | No department/day read-model endpoint over SSOT data | Existing SSOT surfaces expose per-queue or per-specialist/day state, not legacy department/day counters. |
| `queues.next_ticket()` | No supported SSOT front-desk ticket issuer | Main queue allocator track covers queue entries, not legacy `last_ticket` counter issuance for department/day workflow. |
| `board.state()` | No board-specific SSOT projection replacing legacy counters | Existing repositories can read queue entries, but no dedicated board-compatible projection is defined yet. |
| `online_queue.py` service | Responsibilities are not decomposed into future owners yet | Service mixes counters, day-state, identity memory, and websocket broadcast. |
| `OnlineDay` model | Live mounted surfaces still read/write it indirectly | Model cannot be deprecated until all mounted consumers are gone. |

## Cross-cutting gaps

### 1. Department/day vs specialist/day mismatch

OnlineDay surfaces are department/day based.

SSOT queue architecture is centered on:

- `DailyQueue`
- `OnlineQueueEntry`
- specialist/day identity

Any replacement for legacy stats or board surfaces needs an adapter/read model
that can aggregate SSOT queue state back into department/day form.

### 2. Legacy counter semantics have no direct SSOT owner

Legacy OnlineDay still owns:

- `start_number`
- `last_ticket`
- `waiting/serving/done` counters

Main queue allocator track intentionally did not absorb this counter model.

### 3. Open/close day semantics are not yet represented in SSOT

Current SSOT queue world exposes queue opening (`opened_at`) and availability
signals, but not the exact legacy semantics of:

- manual morning intake opening
- manual intake closure
- department/day administrative state

### 4. Consumer uncertainty remains

Live surfaces can only be replaced safely after explicit mapping of who still
consumes:

- `appointments.stats()`
- `queues.stats()`
- `board.state()`
- `queues.next_ticket()`

## Gap verdict

The next safe work should target read surfaces first, because their blockers are
mostly projection/owner-definition gaps.

Write surfaces (`open_day`, `close_day`, `next_ticket`) remain blocked by
domain/operational gaps, not by simple missing code seams.
