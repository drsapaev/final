# Wave 2C Queue Numbering Consistency

Date: 2026-03-07
Mode: analysis-first, docs-only

## Executive Summary

`queue_number`, `queue_time`, `priority`, and queue status transitions are not
one tightly coupled concept in runtime.

That is partly intentional:

- `number` is a ticket label
- `queue_time` is the fairness timestamp
- `priority` is an explicit policy override
- status transitions decide whether the row still participates in ordering

The result is workable, but it means numbering consistency is conditional rather
than absolute.

## Consistency Matrix

| Scenario | `number` behavior | `queue_time` behavior | `priority` behavior | Consistency risk |
|---|---|---|---|---|
| Normal SSOT create | Monotonic within one queue via `max(number)+1` | Set at creation time | Defaults to `0` | Low to medium |
| Registrar batch create | Monotonic when routed through `create_queue_entry()` | Explicit `current_time` passed in | Defaults to `0` | Medium, because duplicate rules differ |
| QR full update adding a new service | New row gets next available number | New service gets current edit time | Defaults to `0` | High, because allocator implementation varies by branch |
| Cancel / no-show | Number is not compacted or reused immediately | Existing timestamp remains historical | Priority usually unchanged | Low if treated as history; medium if operator expects compact numbering |
| Restore as next | Number stays unchanged | Timestamp stays unchanged | `priority = 1` moves entry ahead | High mismatch between number and actual order |
| Reorder | Active-entry list is number-based in reorder repository | Queue-time fairness is not the baseline in reorder path | May interact with manual movement semantics | High ambiguity |
| Reschedule from visit flows | Queue row is moved to `rescheduled` by direct SQL in visit paths | Timestamp is not used to preserve place; row exits active flow | No priority change in inspected path | Medium |
| Force majeure transfer to tomorrow | New number is allocated in target queue | New queue/day context implies new ordering baseline | Transfer priority is elevated | High policy sensitivity |

## What Can Drift

### 1. Number vs. actual queue order

This already happens in runtime:

- `restore_entry_to_next()` keeps the old number and raises `priority`
- patient-facing fairness is based on `priority` and `queue_time`
- reorder tooling still reads active rows ordered by `number`

### 2. Number vs. duplicate policy

Two callers can ask for the "next number", but whether a new row is actually
allowed depends on source-specific duplicate logic.

### 3. Number vs. status transition semantics

Rows that become `cancelled`, `no_show`, `served`, or `rescheduled` leave or
change their participation in active ordering, but their number remains in
history.

### 4. Number vs. legacy counters

The legacy `OnlineDay` system tracks its own `last_ticket` counters, which do
not automatically reconcile with `OnlineQueueEntry.number`.

## Specific Drift Triggers Requested in This Review

### Cancel

- Cancelling an entry does not renumber the rest of the queue.
- This is acceptable if numbers are treated as historical tickets, not as a
  compact fairness index.

### Reschedule

- Visit flows can mark related queue rows as `rescheduled`.
- The number remains attached to the old row; the rescheduled visit may later
  receive a new number in a new flow.

### `restore_as_next`

- This is the strongest proof that ticket number is not the final ordering key.
- The row is restored to `waiting` and moved ahead using `priority = 1`.

### Reorder

- Reorder repository uses `number`-ordered active rows.
- If manual reorder changes the effective service order, ticket number and
  fairness-time semantics may diverge further.

## Verdict

Numbering consistency today is "best effort under multiple policies", not one
strict invariant.

That is enough reason to keep `W2C-MS-005` out of Phase 1 execution until the
project explicitly decides:

- whether `number` is only historical labeling
- whether `number` is also the operator-ordering key
- how restore/reorder/transfer flows should interact with fairness
