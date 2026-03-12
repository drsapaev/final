# W2D next execution unit after board.state deprecation prep

## Recommended next slice

`pause the board tail and return to another actionable OnlineDay legacy slice`

## Why this is the safest next step

The board tail has now reached a clean engineering boundary:

- migrated metadata already lives on the additive endpoint
- legacy `/board/state` is explicitly marked as deprecated
- the remaining unresolved work is semantic, not implementation-sized

That means more board work now would mostly burn effort against blocked
semantics instead of shrinking the legacy island further.

## Practical next move

Return to another actionable OnlineDay/legacy-deprecation slice outside the
board tail.

The strongest current candidate remains:

- bounded `queues.stats` compatibility-tail follow-up or
- another small OnlineDay legacy-surface retirement-prep pass

## Why not continue board reduction immediately

Because the remaining blockers are still:

- `is_paused`
- `is_closed`
- rollback compatibility concerns

Those are not ready for another narrow engineering-only move.
