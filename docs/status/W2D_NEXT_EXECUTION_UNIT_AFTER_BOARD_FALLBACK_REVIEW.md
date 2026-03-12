# W2D next execution unit after board fallback review

## Recommended next slice

`legacy /board/state deprecation-prep slice`

## Why this is the safest next step

This is now the smallest board-related step that still creates real value:

- it matches the actual current role of `/board/state`
- it does not force unresolved `is_paused` / `is_closed` semantics
- it preserves rollback safety
- it avoids wasting another slice on board wiring that has already been done

## Intended scope

The slice should stay narrow:

- keep `/board/state` mounted
- keep current runtime behavior unchanged
- mark the route as deprecated / compatibility-only in contract-facing docs and
  OpenAPI if safe
- document that new board metadata should come from the additive
  board-display endpoint

## Why not remove the route now

Not yet, because:

- `DisplayBoardUnified.jsx` still uses the route as a compatibility fallback
- the remaining blocked board flags are unresolved
- rollback simplicity still matters more than route purity

## Why not stay on the board tail after that

Once deprecation-prep is done, the board thread should likely pause again until
either:

- product semantics for `is_paused` / `is_closed` are clarified, or
- the team explicitly decides to remove rollback compatibility
