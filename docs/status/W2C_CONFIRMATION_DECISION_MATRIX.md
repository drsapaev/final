# Wave 2C Confirmation Decision Matrix

Date: 2026-03-07
Mode: analysis-first, docs-only

## Compared Baselines

- design source: `docs/ONLINE_QUEUE_SYSTEM_IMPLEMENTATION.md`
- target contracts:
  - `docs/architecture/W2C_QUEUE_NUMBERING_CONTRACT.md`
  - `docs/architecture/W2C_DUPLICATE_POLICY_CONTRACT.md`
  - `docs/architecture/W2C_ACTIVE_ENTRY_CONTRACT.md`
- runtime reality:
  - `docs/architecture/W2C_CONFIRMATION_RUNTIME_BEHAVIOR.md`

## Matrix

| Option | Design alignment | Contract alignment | Runtime alignment | Verdict |
|---|---|---|---|---|
| Current runtime: create new row on same-day confirmation | Partial | No | Yes | architectural drift |
| A. Reuse existing active row | Yes | Yes | No | preferred target intent |
| B. Always create a new row | No | No | Yes | reject |
| C. Error if active row exists | Partial | Mostly yes | No | fallback for ambiguous conflicts, not primary intent |

## Current Code Correct Or Drift?

Current confirmation code is **architectural drift**.

Reason:

- it matches current runtime behavior
- but it does not match the clarified domain contracts
- and it is not clearly justified by the design document

## Practical Reading Of The Matrix

- runtime behavior is implemented and characterized
- design and contract review do not support preserving duplicate creation as the
  target domain rule
- the preferred target behavior is reuse-first, not duplicate-first

## Outcome

The confirmation family should not move straight into boundary migration.

It first needs a narrow domain-correction slice that resolves the
duplicate-versus-reuse rule explicitly.
