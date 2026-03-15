# W2D next execution unit after board new endpoint prep

## Chosen next step

`A) create adapter-backed endpoint skeleton only`

## Why this is the safest next code step

- it follows the chosen strategy directly
- it keeps the change additive
- it does not mutate legacy `/board/state`
- it lets us lock the new public contract before any frontend migration

## Why larger implementation is not chosen yet

- unresolved metadata ownership still exists for `logo`, `is_paused`,
  `is_closed`, `contrast_default`, and `kiosk_default`
- queue-state does not need to be pulled into the first endpoint version
- frontend migration should remain a later, separate step

## Expected scope of the next code slice

- add a thin endpoint skeleton
- return the agreed metadata-first shape
- keep route mounted but unused by the current UI
- keep legacy `/board/state` unchanged
