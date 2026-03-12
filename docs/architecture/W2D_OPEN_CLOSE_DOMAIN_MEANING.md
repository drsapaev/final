# W2D Open / Close Domain Meaning

## What These Routes Mean Today

`open_day` and `close_day` are not queue-progression operations. They are best understood as **legacy operational admin lifecycle actions** for the OnlineDay department/day intake window.

## `open_day`

Practical meaning today:

- starts or re-enables a legacy department/day ticket-issuance window
- seeds the legacy `start_number`
- makes the legacy board/stats world look "open"

It is **not**:

- calling the next patient
- assigning a patient into the SSOT queue system
- modifying `DailyQueue` / `OnlineQueueEntry`

## `close_day`

Practical meaning today:

- closes the legacy department/day intake window
- marks the `OnlineDay` row as not open
- affects board/stat visibility through the legacy day-state

It is **not**:

- queue completion
- specialist queue shutdown in the SSOT world
- a patient-level workflow transition

## Are These Queue-Domain Concepts?

No, not in the post-W2C architecture.

They are closer to:

- operational admin lifecycle actions
- legacy intake-window controls
- department/day compatibility behavior

## Do They Have A Clean SSOT Equivalent?

No.

The current SSOT queue architecture is based on:

- `DailyQueue`
- `OnlineQueueEntry`
- specialist-based queue ownership

`open_day` / `close_day` instead operate on:

- department/day semantics
- OnlineDay state
- legacy `Setting(category="queue")` counters

So the clean target framing is:

> not queue-domain operations, but operational admin actions that may need a dedicated compatibility/admin owner if they survive.
