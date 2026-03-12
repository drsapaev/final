# W2D Next Execution Unit After Legacy Re-entry

## Recommended first slice

`appointments.stats consumer / retirement-prep pass`

## Why this is the right first slice

`appointments.stats()` is the best bounded re-entry surface because it is:

- still mounted
- read-only
- part of the OnlineDay legacy island
- lower-risk than `open_day`, `close_day`, or `next_ticket`
- apparently lacking a confirmed live frontend runtime consumer in current repo
  usage

This makes it a strong candidate for either:

- retirement prep, or
- a redirect/replacement decision with low blast radius

without reopening blocked operational semantics.

## Intended scope of that slice

The slice should answer:

1. Is `GET /api/v1/appointments/stats` actually used by any live consumer?
2. Is it duplicative with `queues.stats()` or another already-supported read
   surface?
3. Is it safer to retire, redirect later, or preserve as compatibility?
4. Can this shrink the OnlineDay island without touching blocked admin routes?

## Why not start with `open_day` / `close_day` again

Those routes are still blocked by possible manual/external usage risk.

## Why not start with board tail again

The remaining board blocker is semantic (`is_paused` / `is_closed`), not
engineering.
