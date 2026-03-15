# W2D board legacy fallback decision

## Verdict

`KEEP_AS_COMPATIBILITY_FALLBACK`

## Why

The remaining legacy board tail is now narrow and well-understood:

- `DisplayBoardUnified.jsx` is mostly off `/board/state`
- the migrated metadata already comes from the new board-display endpoint
- the blocked flags `is_paused` / `is_closed` are not actually owned by the
  mounted legacy route

So the route should no longer be treated as a primary board-state source.

At the same time, it should not be removed yet, because it still serves as:

- compatibility fallback
- rollback path
- legacy snapshot source when the new endpoint is unavailable

## What is actionable now

Actionable:

- deprecation-prep for the legacy `/board/state` route
- explicit documentation that the route is compatibility-only
- keeping rollback behavior intact while semantics remain unresolved

## What is still blocked

Blocked:

- migration/removal of `is_paused`
- migration/removal of `is_closed`
- full elimination of `/board/state` fetches from the board page

Reason:

- those steps would force unresolved product semantics or remove rollback safety
  too early

## Practical takeaway

The board thread no longer needs another implementation-sized metadata slice.
The correct next step is a narrow compatibility/deprecation-prep move, not
another attempt to "finish" the board tail by guessing semantics.
