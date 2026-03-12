## Decision

Create a single source of truth for Postgres pilot families.

## First execution unit

Add a narrow `postgres_pilot` manifest/marker layer for the already validated
families.

## Why this is the safest next step

- the pilot itself is now validated strongly enough
- repeating file lists manually is the next likely source of drift
- a marker/manifest is lower risk than going straight to CI wiring
- it keeps SQLite as the default lane and does not require broad fixture
  changes

## Why broader steps are not chosen yet

- full-stack Postgres migration is not justified by current evidence
- adding CI before defining a single source of truth would duplicate lists and
  increase maintenance noise
- expanding the pilot to many more families now is lower value than making the
  validated pilot reusable

## Follow-up after this slice

After the marker/manifest exists, the next likely step is a dedicated CI job
for Postgres pilot families.
