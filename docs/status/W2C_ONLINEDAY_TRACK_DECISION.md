# Wave 2C OnlineDay Track Decision

Date: 2026-03-09
Mode: analysis-first, docs-only

## Decision

`SEPARATE_LEGACY_ISLAND`

## Why

- The family still has a small mounted production surface.
- It still affects production-visible queue counters and board/status outputs.
- It has no runtime bridge into the SSOT `DailyQueue` / `OnlineQueueEntry`
  model.
- Its numbering, duplicate, fairness, and identity assumptions are a separate
  worldview from the main queue domain contracts.

## Why it should not remain in the main queue track

The main queue track has already converged around:

- `QueueDomainService.allocate_ticket()`
- `DailyQueue`
- `OnlineQueueEntry`
- queue-local numbering
- canonical active-entry and duplicate semantics

OnlineDay does not fit that model without a dedicated legacy decision or
retirement strategy.

## Why it is not dead-code cleanup only

- `appointments` legacy admin paths are still mounted
- `queues.next-ticket` is still mounted and writes legacy counter state
- `board.state` still reads the legacy counter state

So the family cannot be treated as dead code yet.

## Isolation update

This decision is now confirmed by the explicit isolation pass:

- main migrated queue families do not depend on OnlineDay
- OnlineDay boundaries are documented as a separate legacy island
- future work should target legacy isolation / retirement, not SSOT migration
