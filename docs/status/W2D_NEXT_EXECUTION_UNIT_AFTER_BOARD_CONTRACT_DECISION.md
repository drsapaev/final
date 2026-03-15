# W2D next execution unit after board contract decision

## Chosen next step

`A) prepare new adapter-backed endpoint contract`

## Why this is the safest next step

- it follows the chosen strategy directly
- it avoids mutating the mounted legacy `/board/state` route
- it lets code move forward without forcing frontend cutover yet
- it creates a testable public contract before any runtime switch

## Why larger replacement is not chosen yet

- the mounted legacy route should remain stable for now
- frontend migration should be staged only after the new endpoint contract is
  explicit
- unresolved fields like `logo`, `is_paused`, `is_closed`,
  `contrast_default`, and `kiosk_default` still need bounded contract prep

## Execution expectation

The next slice should prepare:

- route shape for the new adapter-backed endpoint
- response contract for metadata-first board state
- ownership notes for deferred fields

It should not:

- switch the live UI
- replace `/board/state` in place
- retire the OnlineDay route yet
