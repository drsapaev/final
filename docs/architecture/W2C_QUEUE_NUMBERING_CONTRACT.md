# Wave 2C Queue Numbering Contract

Date: 2026-03-07
Mode: analysis-first, docs-only

## Purpose

This document defines the target numbering contract for SSOT queue entries.

It does not modify runtime allocators. It states the contract that future
migration work must implement.

## Contract Summary

Queue numbering must be:

- monotonic
- queue-local
- day-scoped
- allocated by a single domain owner
- transactionally coupled to queue-entry creation

## Allocator Owner

Public owner:

- `QueueDomainService`

Internal persistence collaborators:

- `QueueRepository` or a dedicated allocator repository
- duplicate-policy lookup helpers
- unit-of-work / transaction boundary

## Numbering Algorithm Contract

### Core rule

For a concrete `DailyQueue`, the next ticket number is:

- greater than every already allocated historical number in that queue/day
- never reused within the same queue/day
- derived from the queue's start-number baseline when applicable

### Scope

- queue-local: numbering is per `DailyQueue`
- day-scoped: because `DailyQueue` is already scoped by day
- not global across all queues

### Monotonicity

The allocator must guarantee:

- `N + 1` is never lower than a previously allocated ticket in the same queue
- cancellation, restore, reorder, or reschedule do not renumber historical rows

## Ticket Number vs. `queue_time`

### Ticket number

- historical queue-local label
- monotonic allocation token
- useful for operator workflows and display

### `queue_time`

- fairness timestamp
- must stay independent from ticket number
- determines ordering together with `priority`

### Contract implication

`ticket_number` must **not** be treated as the only fairness signal.

Fairness remains:

- `priority DESC`
- `queue_time ASC`

## Transaction Boundary Contract

The future allocator must not support free-floating public calls that reserve a
number without also governing the queue-entry creation decision.

### Required rule

Allocation and queue-entry creation must occur in the same domain-controlled
transaction boundary.

### Migration implication

Current split flows such as:

1. `get_next_queue_number()`
2. later `create_queue_entry(number=...)`

are migration targets, not the desired end state.

## Race Protection Contract

The current runtime has no explicit unified race-protection mechanism.

The future contract requires serialized allocation per queue/day.

### Acceptable implementation shapes

- row lock on a queue-owned counter record
- row lock on the queue aggregate plus deterministic next-number computation
- dedicated allocator table with unique constraint and retry

### What matters at contract level

- one queue/day must not produce the same ticket twice
- concurrent allocation must either serialize or fail/retry safely

## Duplicate Relationship Contract

The allocator must not issue a new ticket before the canonical duplicate policy
has been checked for the same queue/day and identity.

That means numbering policy depends on:

- active-entry contract
- duplicate-policy contract

## Compatibility With Existing Special Flows

The numbering contract allows special lifecycle flows such as:

- restore-as-next
- reorder
- force-majeure transfer

but those flows must preserve the rule that ticket numbers are historical
allocations, not a mutable fairness index.

## Non-Goals

This contract does not define:

- visit lifecycle transitions
- payment or registrar orchestration
- legacy `OnlineDay` replacement

Those remain separate migration concerns.
