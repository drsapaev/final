## Decision

Chosen next step:

`A) switch DisplayBoardUnified.jsx to new adapter with compatibility fallback`

## Why This Is Now the Safest Next Step

The adapter layer now exists and is test-covered.

That means the next slice can stay narrow:

- keep the legacy route mounted
- switch only `DisplayBoardUnified.jsx`
- consume only the clean metadata fields from the new adapter
- preserve unresolved fields through compatibility fallback

## Why Not Choose a Larger Move

### Not `B) add one more frontend normalization/fallback helper`

The current adapter is already narrow enough for the first page switch.
Adding another prep-only layer now would delay the actual migration without removing a meaningful blocker.

### Not `C) human review needed`

No new architectural ambiguity remains for the first consumer switch.
The remaining work is implementation-scoped, not decision-scoped.

### Not `D) stop board frontend migration for now`

The backend endpoint exists, the adapter exists, and the migration path is now staged and reversible.

## Recommended Next Scope

The next slice should:

- update only `DisplayBoardUnified.jsx`
- keep `/board/state` as fallback compatibility source where needed
- avoid touching websocket or queue counter logic
- preserve rollback simplicity by keeping the old code path easy to restore
