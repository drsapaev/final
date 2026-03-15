## Next Execution Unit After Postgres Pilot CI

## Decision

Chosen next step:

- `C) return to legacy/deprecation track with CI guardrail now in place`

## Why this is the safest next step

- the bounded Postgres-sensitive queue families now have an automated guardrail
- SQLite remains the fast general baseline
- the main goal of the pilot track has been achieved
- further immediate pilot expansion would give less value than returning to the
  remaining post-W2C legacy tails

## Why other options are not chosen yet

- `A) extend postgres_pilot marker to one more validated family or keep current set`
  is no longer the highest-value default because the current guardrail already
  covers a broad enough surface
- `B) add a second lighter/heavier schedule for the pilot lane` is a reasonable
  later optimization, but it is not required to make the guardrail useful today
- `D) pause and consolidate` is partially achieved already by the alignment
  review and CI wiring docs; the project is ready to move forward again

## Recommended track to resume

Resume the broader post-W2C legacy/deprecation track, starting from the already
identified operational or legacy-island tails rather than expanding the pilot
by default.
