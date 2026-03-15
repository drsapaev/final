## Wave 2D Open/Close Postgres Pilot Results

Date: 2026-03-10
Mode: pilot-extension, evidence-based

## Commands used

SQLite lane:

```powershell
cd backend
pytest tests/characterization/test_open_close_day_characterization.py -q -c pytest.ini
```

Postgres lane:

```powershell
cd backend
pytest tests/characterization/test_open_close_day_characterization.py -q -c pytest.ini --db-backend=postgres
```

OpenAPI verification:

```powershell
cd backend
pytest tests/test_openapi_contract.py -q
```

## Results

- SQLite lane: `3 passed`
- Postgres lane: `3 passed`
- OpenAPI verification: `10 passed`

## Observed drift

No SQLite-vs-Postgres drift was observed in this family.

The already-characterized legacy behavior remained stable in both lanes:

- `open_day` writes queue settings and broadcasts
- `close_day` closes through `OnlineDay.is_open` and does not broadcast
- the split-state behavior between `Setting(category="queue")` and
  `OnlineDay.is_open` remains visible and is reproduced the same way in both
  lanes

## Drift classification

This family did not surface:

- new schema drift
- new harness/session drift
- new Postgres-only transactional drift

The remaining behavior is legacy operational behavior, but it is now proven to
be reproduced consistently under both SQLite and Postgres in the current pilot
setup.

## What this means

- the pilot extension succeeded without additional harness changes
- the dual-lane strategy is now validated on more than one queue-sensitive
  family
- it is now safer to continue to another legacy/queue-sensitive family rather
  than pause immediately
