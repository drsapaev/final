# Wave 2C Next Execution Unit After Confirmation

Date: 2026-03-07
Status: `SAFE_NEXT_STEP_IDENTIFIED`

## Recommended Next Step

`registrar batch-only characterization`

## Why This Is The Next Step

- mounted confirmation family is now migrated and no longer the closest queue
  allocator target
- registrar batch path is the next family most likely to still be queue-service
  backed rather than direct SQL
- it is narrower and safer to characterize than `qr_queue.py` direct SQL
  allocator branches
- it avoids mixing this track with `OnlineDay` legacy isolation too early

## Why Other Options Were Not Chosen

### `qr_queue direct SQL characterization`

Still valid later, but not the next best slice because:

- it is the highest-risk live family
- it is more tightly coupled to mutation, fairness, and transaction semantics

### `legacy OnlineDay isolation review`

Still needed, but it is a separate legacy track and not the best immediate
follow-up after the mounted confirmation migration.

### `defer pending human decision`

Not necessary yet. The repo already has enough evidence to continue with one
more narrow analysis-first unit.

## Execution Constraint

The next step should remain characterization/review-first.

Do not attempt registrar batch allocator migration before dedicated
characterization proves current numbering, duplicate, and operator-visible
batch behavior.
