# W2D next_ticket Domain Meaning

## Short verdict

`next_ticket` is a legacy operational ticket-issuing action for the OnlineDay island.

It is not:

- a SSOT queue-entry allocation flow
- a patient call-next flow
- a `waiting -> serving` transition

## Actual state transition

For `department + date` the route performs this legacy transition:

- ensure `OnlineDay` exists
- increment `last_ticket`
- increment `waiting`
- broadcast updated legacy stats

No queue entry is created and no patient record is selected or advanced.

## What entities are touched

Touched:

- `OnlineDay`
- `Setting(category="queue")` counters

Not touched:

- `DailyQueue`
- `OnlineQueueEntry`
- visit status
- doctor queue ordering in SSOT

## Domain classification

The current action is best described as:

- legacy kiosk/admin counter issuance
- department/day operational action
- board-facing stats mutation

It is not a clean queue-domain action in the modern SSOT sense.

## Queue-domain or board-domain?

It sits between the two, but the better label is:

- operational admin action inside a legacy queue-counter island

Reason:

- it mutates queue counters
- it does so only in the old department/day counter model
- its visible downstream effect is mostly board/stats oriented

## Clean SSOT equivalent?

No confirmed clean SSOT equivalent exists today.

Why:

- SSOT queue flows operate on concrete queues, entries, and statuses
- `next_ticket` issues a naked department/day counter number
- there is no proven modern operation that means “increment legacy department/day ticket and waiting count” without also entering queue-entry lifecycle semantics

## Practical meaning for replacement planning

A future replacement should not assume this route maps directly to:

- `QueueDomainService.allocate_ticket()`
- QR join
- doctor call-next
- queue-entry status transitions

If this behavior is still product-relevant, it likely needs either:

- an operational adapter over modern read/write surfaces
- or a deliberate decision to keep/retire the legacy action
