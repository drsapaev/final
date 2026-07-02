# Wave 2C Next Execution Unit

Date: 2026-03-07
Mode: analysis-first, docs-only
Status: `SAFE_NEXT_STEP_IDENTIFIED`

## Recommended Unit

Execution unit:

- `W2C-HR-001`
- type: characterization-test pass
- target family: confirmation split-flow

## Scope

Add a narrow characterization suite for:

- `backend/app/services/visit_confirmation_service.py`
- `backend/app/api/v1/endpoints/visit_confirmation.py`

Likely test file:

- `backend/tests/characterization/test_visit_confirmation_allocator_characterization.py`

## Why this is the safest next step

- The family already allocates through shared `queue_service` helpers.
- It does not use direct SQL `MAX(number)+1`.
- It does not depend on `OnlineDay`.
- It is closer to a later boundary migration than registrar wizard, force
  majeure, or `qr_queue.py`.

## What the pass should lock down

- same-day confirmation creates queue entries with `source="confirmation"`
- newly created queue rows use current runtime `status` and `queue_time`
  semantics
- multi-queue-tag confirmation behavior is stable
- replay or repeated confirmation behavior is explicitly captured
- `visit.doctor_id` fallback behavior between `doctor.id` and `user.id` is
  captured

## What this pass must not do

- no allocator migration
- no change to numbering algorithm
- no change to duplicate policy
- no change to visit confirmation runtime behavior

## Stop Conditions

Stop if:

- current confirmation behavior is ambiguous across channels
- replay behavior is nondeterministic
- confirmation tests require changing queue mutation logic to pass

## Why other candidates were not selected

- registrar family still needs a family split before the next safe unit
- `qr_queue.py` family is blocked by transaction-model complexity
- force majeure is blocked by transfer transaction semantics
- `OnlineDay` remains a separate legacy decision track
