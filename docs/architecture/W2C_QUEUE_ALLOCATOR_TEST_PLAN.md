# Wave 2C Queue Allocator Test Plan

Date: 2026-03-07
Mode: analysis-first, docs-only

## Purpose

This document defines the domain-level tests that must exist before or during
allocator migration.

The goal is to characterize current behavior and protect the future contract.

## Test Categories

### 1. Monotonic numbering

Verify that:

- a queue allocates `1, 2, 3...` or `start_number, start_number + 1...`
- later allocations never reuse a historical number in the same queue/day
- cancellation or terminal states do not cause renumbering

### 2. Queue-local / day-scoped isolation

Verify that:

- two different `queue_id` values can both issue ticket `1`
- the same specialist on different days gets separate numbering scopes
- global cross-queue numbering is never used by the canonical allocator

### 3. Duplicate prevention

Verify that:

- same identity in same queue/day returns duplicate, not a new ticket
- `patient_id` wins over phone/telegram fallback when present
- phone fallback works for unauthenticated/public join
- telegram fallback works when phone is missing
- explicit override requires an audit reason

### 4. Active-status blocking

Verify that duplicate blocking applies to the proposed canonical active set:

- `waiting`
- `called`
- `in_service`
- `diagnostics`

And does not block when the existing row is:

- `served`
- `cancelled`
- `no_show`
- `incomplete`
- `rescheduled`

### 5. Fairness preservation

Verify that:

- allocation does not rewrite historical `queue_time`
- new entries receive current business `queue_time` when required
- restore/reorder flows may change effective position without rewriting ticket
  numbers
- ticket number and fairness ordering remain distinct concepts

### 6. Concurrency / race protection

Verify that:

- two concurrent allocations in the same queue/day cannot get the same ticket
- one transaction retries or fails cleanly if another wins the lock
- the resulting ticket series stays gap-aware and monotonic under contention

### 7. Compatibility characterization

Before migration, add characterization tests for:

- `queue_service` current SSOT-style allocation
- QR full-update direct allocator behavior
- registrar batch flow
- force-majeure transfer allocator
- legacy `OnlineDay` counter behavior

These tests should document runtime truth, not normalize it prematurely.

## Suggested Test Cases

| Test ID | Scenario | Expected result |
|---|---|---|
| `alloc-001` | first ticket in empty queue | first valid number allocated |
| `alloc-002` | second ticket in same queue/day | next number is previous + 1 |
| `alloc-003` | same patient replays same queue join | duplicate result, no new ticket |
| `alloc-004` | patient active in `in_service` | duplicate blocked |
| `alloc-005` | patient row is `served` | new allocation allowed |
| `alloc-006` | two queues allocate concurrently | numbers isolated by queue |
| `alloc-007` | same queue concurrent allocation | unique monotonic tickets |
| `alloc-008` | restore-as-next existing entry | no new ticket allocation |
| `alloc-009` | reorder active entries | no renumbering |
| `alloc-010` | legacy queue path still active | contract adapter test documents separation |

## Execution Guidance

These tests should be added in two layers:

1. characterization tests for current runtime behavior
2. contract tests for the future allocator owner

That sequence avoids silently changing behavior while introducing the new
boundary.
