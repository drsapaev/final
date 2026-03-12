## Decision

Chosen next step:

`B) add frontend adapter layer first`

## Why This Is the Safest First Frontend Step

`DisplayBoardUnified.jsx` is the only confirmed live consumer that needs migration, but it currently mixes:

- endpoint fetching
- payload normalization
- local storage fallback
- hardcoded defaults

Adding a thin frontend adapter/service first is the smallest safe way to:

- isolate the new endpoint contract
- preserve simple rollback
- keep the eventual page switch reviewable
- avoid a larger direct rewrite inside the display page

## Why Not Choose a Bigger Switch Yet

### Not `A) migrate DisplayBoardUnified to new endpoint with fallback`

That is likely the slice after the adapter is in place, but doing it immediately would combine:

- new endpoint adoption
- field mapping
- fallback behavior
- page-level refactor

That is a wider first switch than necessary.

### Not `C) add board_key resolution/config prep first`

Board key sourcing is already available in `DisplayBoardUnified.jsx` through:

- `?board=...`
- fallback `boardId`

So this is not the primary blocker.

### Not `D) human review needed`

The current evidence is sufficient to continue with a bounded code step.

## Recommended Immediate Scope

The next code slice should add:

- a frontend board-display endpoint wrapper/adapter
- normalization for the cleanly mapped metadata fields
- explicit fallback strategy for unresolved fields

It should still avoid:

- frontend runtime switch in the same slice, unless the adapter is extremely thin and separately reviewable
- changes to counters, websocket, or queue-status reads
