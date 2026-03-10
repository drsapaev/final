# W2D next execution unit after queues.stats harness

Chosen next step: `A) narrow queues.stats replacement slice`

## Why this is the safest next step
- strict parity fields already have evidence-backed SSOT equivalence
- the live confirmed consumer mainly needs:
  - `last_ticket`
  - `waiting`
  - `serving`
  - `done`
- no route switch has happened yet, so the next slice can stay narrow and observable

## Why not a larger replacement
- `board_state` remains a separate read-surface with extra display metadata
- `appointments.stats` still looks like a duplicate/retire candidate, not the first replacement target
- `is_open` and `start_number` still need compatibility fallback, so the first code step should stay limited to `queues.stats`
