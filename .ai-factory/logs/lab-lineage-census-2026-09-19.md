# Lab lineage production census — 2026-09-19 (stage 4, data step)

Status: operator-run READ ONLY census; reported numbers are **not
independently GitHub-verifiable** (the production database is not a repo
artifact). The census script is now committed at
`scripts/ops/lab_results_lineage_census.py` so any reviewer can re-run it
against the production DSN and reproduce these numbers.

Protocol: `SET TRANSACTION READ ONLY` + `statement_timeout = 20s` +
ROLLBACK at the end; aggregates and technical identifiers only (no
patient PII); the DSN is never printed.

## Environment at census time

- Code on `main`: `eaaa08f8961a5100697d96560ce16546a17b5b0a` (A+ runtime, #3332)
- Production `alembic_version`: `0069_sentinel_pair_retirement` → migration `0070_lab_results_lineage` NOT yet applied (deployment is operator-owned)

## Results

| Check | Value |
| --- | --- |
| lineage columns in schema | 0 of 2 (consistent with 0069) |
| `lab_results` total rows | **0** |
| FINALIZED/PRINTED lab instances | **0** |
| distinct orders with finalized instances | **0** |
| managed (lineage) rows | n/a (columns absent) |
| orders with >1 finalized blanks (`ambiguous_shared_order` class) | **0** |
| shared orders with legacy rows / without | 0 / 0 |
| duplicate `(order_id, test_code)` groups | **0** |
| orders finalizing both colliding templates (`biochem_panel` × `urinalysis_oam`) | **0** |

## Reading

Production is a **greenfield** environment for the lab lineage program:
the structured-blank workflow has no finalized production usage yet and
the legacy `lab_results` table is empty. Consequences per the owner
contract:

- there are NO ambiguous historical rows to attribute and NO #3235
  overwrite victims to repair — no history-repair decision is required;
- the backfill script has no input data and stays dormant;
- applying `0070` during the operator deployment window carries no
  historical-data risk (additive DDL over an empty projection table);
- the remaining stage-4 steps are: staging validation (incl.
  `scripts/smoke_test_staging.sh`), operator deployment, then the
  lineage-specific post-deploy smoke
  (`scripts/ops/lab_lineage_post_deploy_smoke.py`).
