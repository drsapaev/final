# W2D Open / Close Runtime Conflicts

This document compares current runtime behavior with the recommended target direction: "keep for now, but reframe as operational admin lifecycle actions."

## What Already Matches

- The routes already behave more like operational admin actions than queue-domain actions.
- They operate on department/day legacy state, not patient queue entries.
- They still belong to the OnlineDay island, not the SSOT allocator track.

## What Conflicts

### 1. `open_day` and `close_day` are asymmetric

Current runtime:

- `open_day` writes legacy `Setting(...)` keys for `open` and `start_number`
- `close_day` writes `OnlineDay.is_open = False`

Conflict type:

- runtime contract drift

Why it matters:

- the pair does not clearly mutate the same canonical state source

### 2. `open_day` response can overstate canonical state

Current runtime:

- `open_day` returns `is_open=True` and the requested `start_number`
- but it does not explicitly set `OnlineDay.is_open=True` or `OnlineDay.start_number`

Conflict type:

- likely bug or naming/contract drift inside the legacy island

Why it matters:

- the response may present a stronger state guarantee than the underlying OnlineDay row actually carries

### 3. `close_day` has no matching broadcast behavior

Current runtime:

- `open_day` attempts `_broadcast(...)`
- `close_day` does not

Conflict type:

- inconsistent side-effect behavior

Why it matters:

- if the routes are meant to be a paired operational lifecycle, their downstream notification semantics are currently uneven

### 4. Consumer ownership is unresolved

Current runtime:

- no confirmed in-repo live frontend caller
- mounted admin routes remain public to authenticated admin usage

Conflict type:

- unresolved compatibility risk

Why it matters:

- safe deprecation or replacement still depends on whether real external/manual consumers exist

## What Must Happen Before Code Change

1. characterize the current runtime behavior explicitly
2. lock in whether external/manual use exists or must be assumed
3. decide whether asymmetry in `open_day` vs `close_day` is acceptable legacy behavior or a bug to correct later
