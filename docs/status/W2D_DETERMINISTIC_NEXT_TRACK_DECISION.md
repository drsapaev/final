# Wave 2D Deterministic Next Track Decision

## Verdict

`NEXT_TRACK_TEST_INFRA_ALIGNMENT`

## Why this track gives the highest value now

The highest-value deterministic next step is the Postgres-aligned test
infrastructure follow-up.

This track wins because it:

1. is **not blocked** by product or ops semantics
2. addresses a known repo-wide drift between production and test environments
3. improves confidence for every later legacy-reduction slice
4. lowers the chance that future queue or OnlineDay cleanup work will be guided
   by SQLite-only signal

Repo-backed evidence already exists:

- `backend/.env` uses Postgres
- `backend/tests/conftest.py` still provisions SQLite
- `docs/architecture/W2C_POST_CLOSURE_FOLLOWUPS.md` already names
  Postgres-aligned test work as a meaningful post-closure bucket

## Why blocked semantic tails are not chosen

They are still important, but not deterministic enough:

- board finalization is blocked by product semantics for `is_paused` /
  `is_closed`
- `open_day` / `close_day` are blocked by possible external/manual usage
- `next_ticket` is already on a `DEPRECATE_LATER` path

## Why other deterministic tracks are not chosen yet

### `NEXT_TRACK_ONLINEDAY_DEPRECATION_CONTINUATION`

Not chosen because the highest-value remaining parts of that track now run into
semantic and usage blockers.

### `NEXT_TRACK_DOCS_CONSOLIDATION`

Not chosen because it improves clarity, but not runtime confidence.

### `NEXT_TRACK_RESIDUE_CLEANUP`

Not chosen because it is now narrower and lower leverage than reducing DB/test
drift.

### `NEXT_TRACK_FORCE_MAJEURE_FOLLOWUP`

Not chosen because it is isolated and partly blocked by local policy decisions.

### `NEXT_TRACK_FORMALIZE_PAUSE_POINT`

Not chosen because meaningful deterministic work still exists, so a pause point
would be premature.
