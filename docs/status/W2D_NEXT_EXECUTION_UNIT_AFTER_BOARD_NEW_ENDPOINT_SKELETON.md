# W2D next execution unit after board new endpoint skeleton

## Chosen next step

`B) frontend consumer audit/prep for staged migration`

## Why this is the safest next step

- the new endpoint skeleton is already mounted
- confirmed metadata fields are already wired
- the biggest remaining risk is no longer backend route creation
- the next bounded question is whether the live board UI can migrate to this
  metadata-only v1 without pulling unresolved fields into the same slice

## Why broader migration is not chosen yet

- the live UI still expects some unresolved fields
- no frontend switch should happen before those expectations are mapped
- queue-state should remain a separate later track, not get folded into this
  migration by accident

## What the next prep should answer

- which `DisplayBoardUnified.jsx` fields can move to the new endpoint
- which fields still need fallback/default handling
- whether a minimal staged frontend migration is possible without contract drift
