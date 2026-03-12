# Wave 2D Next Execution Unit After Deterministic Review

## Chosen Track

`NEXT_TRACK_TEST_INFRA_ALIGNMENT`

## First execution unit

`Postgres-aligned test inventory / migration-prep pass`

## Scope of the first slice

The first slice should stay preparation-first and evidence-first:

1. inventory all queue-sensitive and legacy-island-sensitive tests that still
   run on SQLite
2. identify where SQLite semantics are likely to distort production truth
3. map which tests can remain DB-agnostic and which need Postgres-aligned
   execution later
4. define a staged migration strategy instead of switching the whole suite at
   once

## Why this is the safest first slice

- no runtime behavior needs to change
- no broad CI or infra switch is required immediately
- it produces the evidence needed before touching test execution semantics
- it strengthens every later legacy-reduction track

## Why a larger implementation is not chosen yet

A direct test-infra migration would be too broad without first knowing:

- which tests actually need Postgres parity
- which fixtures depend on SQLite-specific behavior
- where queue and concurrency assertions are most at risk

So the right first move is an inventory and migration-prep slice, not a suite
switch.
