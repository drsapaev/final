## Status

Completed and ready for CI promotion.

## What worked

- `postgres_pilot` marker added successfully
- SQLite marker lane is green
- Postgres marker lane runs safely through the shared pilot harness
- the marker is usable as a single source of truth for validated pilot families

## Observed result

- SQLite marker lane: `28 passed, 761 deselected`
- narrow visit-status schema test: `1 passed`
- narrow confirmation datetime test: `2 passed`
- Postgres marker lane: `28 passed, 764 deselected`
- SQLite marker lane: `28 passed, 764 deselected`
- OpenAPI: `10 passed`

## Newly surfaced blocker

The failing family is:

- [test_confirmation_split_flow_concurrency.py](C:/final/backend/tests/characterization/test_confirmation_split_flow_concurrency.py)

Fixed bounded drifts included:

- `Visit.status -> String(16)` cannot store `pending_confirmation`
- confirmation-family naive-vs-aware datetime comparison during
  token-expiry validation

## Conclusion

The marker layer is good and should stay.

Its immediate rollout goal is now completed:

- CI now has a dedicated `postgres_pilot` job

The marker remains the source of truth for what that job runs.
