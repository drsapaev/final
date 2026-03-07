# Wave 2C Confirmation Domain Intent

Date: 2026-03-07
Mode: analysis-first, docs-only

## Inputs

- `docs/architecture/W2C_CONFIRMATION_DESIGN_INTENT.md`
- `docs/architecture/W2C_CONFIRMATION_CONTRACT_CONFLICT.md`
- `docs/architecture/W2C_CONFIRMATION_RUNTIME_BEHAVIOR.md`

## Question

What should the confirmation family do when queue materialization is requested
for a confirmed visit?

## Evaluated Options

### Option A

Confirmation should reuse an existing active queue entry for the same canonical
queue claim.

### Option B

Confirmation should always create a new queue entry.

### Option C

Confirmation should return an error whenever an active queue entry already
exists.

## Recommended Domain Intent

Primary intent: **Option A**.

Secondary safeguard: **Option C** for ambiguous conflicts.

## Why Option A Is The Best Fit

### It matches the design source better

The design document allows multiple queue rows across different queue claims,
not duplicate active rows in the same queue/day for the same claim.

Reusing the existing active row preserves that model.

### It matches the duplicate-policy contract

The duplicate-policy contract requires:

- one active row per identity per queue/day
- duplicate check before new allocation

Reusing an existing row satisfies that contract without inventing a source-based
exception.

### It preserves fairness better than a new allocation

If the queue claim already exists, allocating a fresh ticket creates an extra
historical number and may create a second live claim for the same patient in the
same queue.

Reuse avoids that drift.

## Why Option B Is Rejected

Always creating a new row:

- conflicts with the duplicate-policy contract
- conflicts with the inferred design intent
- normalizes the current drift instead of correcting it

## Why Option C Alone Is Too Strict

An unconditional error is safe from a duplicate-policy perspective, but it is
not the best primary intent because confirmation may encounter a legitimate
pre-existing queue row that already represents the visit's queue claim.

In that case, the right business outcome is not necessarily failure. It is
usually reconciliation with the existing row.

## Proposed Contract Statement

The clarified domain intent is:

1. confirmation may materialize the first queue row for a confirmed visit
2. if the canonical queue claim already has an active row, confirmation should
   reuse that row instead of allocating another one
3. if the runtime cannot safely determine ownership of the existing row,
   confirmation should fail explicitly rather than allocate a second active row

## Scope Note

This document defines the target contract only.

It does not claim the current runtime already follows it.
