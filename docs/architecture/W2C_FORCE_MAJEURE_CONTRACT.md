# Wave 2C Force Majeure Contract

Date: 2026-03-09
Mode: contract-review

## Domain Meaning

Force majeure is not a normal allocator caller.

It is an exceptional operational transfer domain used when the clinic cannot
finish the current-day queue under normal conditions and must either:

- transfer pending patients to tomorrow
- or cancel the queue and trigger refund/deposit consequences

## Canonical Target Behavior

### Transfer meaning

Transfer means:

- the current-day queue claim is terminated
- a new tomorrow-queue claim is created for the same specialist queue family
- the new claim is marked as an exceptional transfer

### Queue scope

Tomorrow transfer is queue-local first, not visit-local first.

That means the target row belongs to:

- the target `DailyQueue`
- the target queue/day numbering space

while still carrying `visit_id` when present.

## Target Contract By Policy Area

### Numbering

- allocate a new queue-local number on the target queue/day
- number must still remain monotonic within that target queue/day
- historical cancelled rows must still count for monotonicity

### Duplicate behavior

- duplicate prevention should apply on the target queue/day
- if the same patient already has an active target-queue claim, transfer should
  not silently create another row
- the safe target behavior is explicit conflict, not silent duplicate creation

### `queue_time`

- transferred rows should get a new transfer-time timestamp
- the old queue's timestamp should not be preserved onto the new row
- within a transfer batch, ordering should remain deterministic

### Fairness / priority

- force majeure intentionally overrides ordinary fairness by raising priority
- this override should remain explicit and isolated to the family
- transferred rows should remain distinguishable from ordinary rows

### Source semantics

- target row should keep a distinct source:
  `force_majeure_transfer`

### Visit linkage

- `visit_id` should be preserved when available
- cancelling the source row must not silently detach the transfer from the
  visit/payment context

## Relationship To General Queue Contracts

Force majeure intentionally overrides normal queue rules for:

- priority
- `queue_time` preservation
- source semantics

Force majeure should still obey general queue rules for:

- target-queue numbering monotonicity
- no silent duplicate active row in the same target queue/day
- explicit visit linkage

## Track Position

This family should be treated as an exceptional domain with its own contract.

It may later reuse lower-level queue helpers, but it should not be forced into
the ordinary allocator-boundary track as if it were just another create caller.
