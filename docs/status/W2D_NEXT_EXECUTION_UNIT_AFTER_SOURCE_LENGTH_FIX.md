## Next Execution Unit After Source Length Fix

Date: 2026-03-10

Chosen next step: `A) continue to the next schema drift (DailyQueue.specialist_id)`

## Why this is the safest next move

- The Postgres pilot is still doing its job: it exposes one honest blocker at a
  time.
- The `queue_entries.source` mismatch is now resolved and the pilot progressed
  further, so the next highest-value blocker is the strict FK failure on
  `DailyQueue.specialist_id`.
- That blocker is still in the same pilot family and still looks like concrete
  DB/schema drift, not a broad infrastructure problem.

## Why not the session/refresh issue first

- The `session.refresh(user)` failure is real, but it currently looks more like
  a session/transaction behavior issue than a schema contract problem.
- The `DailyQueue.specialist_id` failure is more foundational because it blocks
  a full characterization path earlier and is easier to isolate as the next
  narrow drift fix.

## Pilot continuation recommendation

Continue immediately with one more narrow schema-drift slice for the
`DailyQueue.specialist_id` path, then rerun the same SQLite/Postgres pilot
family again.
