## Next Execution Unit After Specialist FK Fix

Date: 2026-03-10

Chosen next step: `A) continue to the session.refresh(user) Postgres-lane issue`

## Why this is the safest next step

- the queue pilot is now past the schema bootstrap blocker
- the `DailyQueue.specialist_id` ownership drift is fixed honestly
- SQLite remains green, so the current slice is stable
- only one isolated Postgres-only blocker remains in the pilot family

## Why not broaden the pilot

- there is no need for a broader schema rewrite now
- the harness is already producing useful signal one blocker at a time
- widening scope would make it harder to tell whether the remaining failure is
  infra, fixture, or real transaction/session drift

## Immediate recommendation

Continue with one more narrow slice focused only on the Postgres-lane
`session.refresh(user)` concurrency failure, then rerun the same pilot family.
