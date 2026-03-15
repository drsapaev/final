# W2D Next Execution Unit After Legacy Review

## Recommended First Slice

`open_day / close_day contract clarification pass`

## Why This Is The Right First Slice

`next_ticket` already has a contract direction (`DEPRECATE_LATER`). The higher-value unresolved pair is now:

- `POST /api/v1/appointments/open-day`
- `POST /api/v1/appointments/close`

These endpoints:

- are still mounted,
- still mutate OnlineDay-backed legacy state,
- still broadcast legacy queue stats,
- and have not yet been given a clear target meaning in the post-W2C architecture.

Clarifying them first is safer than attempting deprecation or replacement immediately because it answers the key architectural question:

> Should the remaining OnlineDay island still own a future operational day-control concept, or should these routes ultimately be retired?

## Scope Of The Next Slice

The contract clarification pass should answer:

1. What `open-day` and `close-day` actually mean today.
2. Whether they are:
   - operational admin actions that should survive, or
   - legacy scaffolding that should be retired later.
3. What legacy state they still own:
   - `OnlineDay.is_open`
   - `start_number`
   - legacy counter visibility / broadcasts
4. Whether they have any confirmed in-repo or plausible external/manual consumers.

## Why Not Start With `next_ticket` Again

`next_ticket` already has a reviewed target direction. Revisiting it immediately would provide less leverage than clarifying the still-open `open-day` / `close-day` pair.
