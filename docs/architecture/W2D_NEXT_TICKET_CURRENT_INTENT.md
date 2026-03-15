# W2D next_ticket Current Intent

## What problem the route solves today

Today `POST /api/v1/queues/next-ticket` solves a narrow legacy problem:

- issue the next visible department/day ticket number
- bump the legacy waiting count
- refresh the same legacy stats surface used by board/stats views

It belongs to the OnlineDay island, not to the main SSOT queue allocator track.

## What it is not

It is not a modern queue progression action.

Specifically, current runtime does not:

- choose the next waiting patient
- move any patient from `waiting` to `serving`
- create a SSOT queue entry
- update doctor-facing queue order

## Real semantic meaning

The current route is best understood as:

- legacy ticket issuance for a department/day counter world
- operational admin or kiosk-facing counter mutation
- board/stats-facing counter refresh trigger

## Is it truly queue progression?

No.

Its current name suggests queue progression, but its behavior is just ticket issuance plus counter mutation.

That makes the name misleading relative to runtime semantics.

## Why the name is misleading

`next_ticket` sounds like:

- “advance to the next patient”
- or “serve the next waiting number”

But actual behavior is:

- increment `last_ticket`
- increment `waiting`
- leave `serving` and `done` untouched

So the route currently means “issue another legacy ticket”, not “progress the queue”.

## Current intent verdict

The safest interpretation is:

- legacy counter-issuance action
- mounted for backward compatibility
- not a core queue-domain operation in target architecture
