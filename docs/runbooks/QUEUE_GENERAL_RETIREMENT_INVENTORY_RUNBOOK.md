# Queue Stage E — `general` Retirement Inventory Runbook (RQ-15.a)

## Purpose

- Produce the **read-only production/staging inventory** required before
  any Stage E work: the RQ-15.b catalog/runtime cutover, the RQ-15.c
  historical-owner conversion and the RQ-15.d exact paired deletion
  (ADR-001 "Stage E `general` decision", owner decision D-08, 2026-09-12).
- Emit the **operator map** — the fillable decision list for every active
  `general` service / profile / queue. D-08 forbids inference from service
  names: each surface gets an explicit operator decision or blocks RQ-15.b.
- Prove the ADR production-gate facts from the LIVE database, not from a
  green CI database: alembic head + the two 0063 constraints, the exact
  0055 synthetic pairs, every inbound foreign-key reference to them, the
  sentinel-Doctor population that must never be deleted, and the
  live-entry queues that block the cutover.

This runbook performs NO writes, NO migrations, NO runtime changes. The
inventory script (`backend/scripts/inventory_general_retirement.py`) is
enforced read-only at the driver level (SQLite `PRAGMA query_only`,
PostgreSQL `SET default_transaction_read_only`).

## Preconditions

- Target database is production or staging, with a **pre-D backup
  retained** (the ADR D-gate requires the D inventory/backup/restore
  evidence to be kept).
- Backend working copy is on the deployed commit (or newer) — the script
  is standalone and does not need the app server.
- Python environment with `sqlalchemy` available (the backend venv is
  enough).
- The database URL at hand (same `DATABASE_URL` the deployment uses).

## Inventory Command

Run from the repository root (Windows PowerShell or bash):

```bash
cd backend
python scripts/inventory_general_retirement.py \
    --database-url "postgresql+psycopg://user:pass@host:5432/clinic" \
    --json ../evidence/stage_e_inventory_$(date +%Y%m%d).json \
    --operator-map ../evidence/stage_e_operator_map_$(date +%Y%m%d).json
```

PowerShell variant:

```powershell
cd backend
. .\.venv\Scripts\Activate.ps1
$stamp = Get-Date -Format 'yyyyMMdd'
python scripts\inventory_general_retirement.py `
    --database-url $env:DATABASE_URL `
    --json ("..\evidence\stage_e_inventory_" + $stamp + ".json") `
    --operator-map ("..\evidence\stage_e_operator_map_" + $stamp + ".json")
```

`--database-url` may be omitted when `DATABASE_URL` is exported. `--pretty`
additionally prints the full JSON to stdout. The script connects, disables
writes on its connection, runs only SELECT/introspection, prints a
human summary and exits.

## Exit Codes

| Code | Meaning | Next action |
|------|--------|-------------|
| 0 | No blockers, no open decisions | RQ-15.b may start after the owner confirms |
| 1 | Inventory complete; blockers and/or open operator decisions exist | **Expected on production.** Complete the operator map, resolve the blockers, re-run until the report reflects the decisions |
| 2 | Stage D prerequisites missing (alembic head below 0063, missing `ck_daily_queues_owner_xor` / `uq_daily_queues_active_resource_day`, XOR violations, ACTIVE resource duplicates) | Deploy QD-2D first (`alembic upgrade head`), then re-run |

Exit code 1 is NOT a failure of the run — it is the inventory doing its
job. Stage E continues only after the operator has resolved what exit
code 1 reported.

## Reading the Report

The JSON report (`report_version` 1) has one section per ADR
production-gate item:

- `schema_contract` — alembic version, both constraint names present or
  not, owner-XOR violation count, ACTIVE `(day, queue_resource_id)`
  duplicate groups. Anything non-zero here means the D contract is not
  in place.
- `synthetic_pairs` — the exact three 0055 identities
  (`ecg_resource` / `lab_resource` / `general_resource`): user id,
  linked doctor id, specialty, drift notes (wrong count, wrong
  specialty, inactive rows, missing disabled-password marker).
- `inbound_references` — for EVERY foreign key in the schema referencing
  `doctors` or `users`: how many rows point at each synthetic id (plus
  sample ids). This is the exact-ID dry-run deletion proof. `daily_queues
  .specialist_id` references are expected for `general_resource` until
  RQ-15.c; every OTHER surface with a non-zero count is a blocker.
- `routing_surfaces` — services still routing onto `general` (fallback
  queue_tags `general` / `cardiology_common` / `dermatology` /
  `procedures`, `department_key='general'`, or a synthetic `doctor_id`),
  queue profiles whose `queue_tags` contain `general`, the `general`
  department row, and any `medical_specialties` `general` row (a drift —
  the catalog never stores the sentinel).
- `general_queues` — every daily queue tagged `general` or owned by a
  synthetic Doctor, with entry totals and live-entry counts
  (`waiting`/`called`/`in_service`/`diagnostics`), classified as
  `active_live_blocker` / `active_empty` / `inactive_historical`.
- `sentinel_doctors` — doctors with specialty `general` EXCLUDING the
  synthetic pair: the incomplete-onboarding population RQ-15.d must
  NEVER delete.
- `registry` — `queue_resources` rows; a `general` row is drift until
  RQ-15.c creates the deliberate archival row.
- `blockers` — the consolidated list (kind + detail) of what blocks
  RQ-15.b.
- `operator_map_items` — how many decisions the operator map carries.

## Completing the Operator Map

The `--operator-map` file lists every item needing a decision:

- `surface=service` — every ACTIVE service on a general-fallback tag,
  `department_key='general'` or a synthetic doctor. Decision options:
  `assign_doctor` (fill `target_doctor_id`), `retag_resource` (fill
  `target_queue_tag` — an exact ACTIVE resource tag), `disable_service`.
- `surface=daily_queue` — every ACTIVE general-surface queue (live-entry
  blockers first). Decision options: `resolve_entries_then_deactivate`,
  `deactivate`.
- `surface=queue_profile` — every ACTIVE profile containing the
  `general` tag. Decision options: `retire_profile`, `keep_profile`.

Fill each `decision` (null until completed). No inference from service
names/codes is allowed (D-08) — when in doubt, ask the owner. Retain the
completed map as the RQ-15.b input artifact; RQ-15.b implements exactly
what the map says, nothing more.

## Evidence Retention

- Keep the JSON report, the operator map (original + completed) and the
  command line used, next to the pre-D backup evidence (ADR gate 2:
  "the D inventory/backup/restore evidence is retained").
- Re-run the inventory after each operator intervention (service
  retagging, queue resolution) — the report is cheap and the final
  pre-cutover run is the proof that no active `general` surface remains.

## Rollback

Not applicable — the inventory is read-only and changes nothing. The
evidence files are plain JSON; delete them if the run is discarded.

## Stage E continuation (for the coordinating agent)

1. RQ-15.a (this runbook): production inventory + completed operator map.
2. RQ-15.b: catalog/runtime fail-closed cutover implementing the map
   (no new `general` routes, explicit Doctor/QueueResource owners,
   unknown owner = configuration error; no `general_resource` fallback).
3. RQ-15.c: inactive history onto the inactive archival resource;
   zero live synthetic references proven.
4. RQ-15.d: the separate Alembic revision deleting EXACTLY the three
   0055 pairs plus the username/fallback/bridge vocabulary, after the
   production gates hold (dry-run zero inbound references included in
   the report above).
