## Decision

Fix the newly surfaced confirmation-family schema drift before CI wiring.

## First execution unit

Narrow drift fix for:

- `Visit.status` length vs `pending_confirmation`

in the confirmation split-flow concurrency family.

## Why this is the safest next step

- the marker layer itself is already successful
- the aggregated Postgres pilot run exposed one bounded blocker
- fixing that blocker keeps the rollout sequence honest and incremental
- promoting a knowingly red Postgres pilot lane into CI would create noisy
  feedback too early

## Why broader steps are not chosen yet

- CI wiring is premature while the marker-driven Postgres lane still has a real
  schema blocker
- broad fixture migration remains unjustified
- the right move is still one-drift-at-a-time progress
