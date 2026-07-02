# Wave 2C Registrar Wizard Claim Contract Check

Date: 2026-03-08
Mode: readiness recheck, docs-only
Status: `validated`

## Contract Under Review

Source contract:

- `docs/architecture/W2C_REGISTRAR_WIZARD_CLAIM_CONTRACT.md`

Target claim identity:

- patient identity
- `queue_tag`
- queue day

Explicit non-goal:

- specialist-level claim ownership for wizard-family

## Runtime Evidence

Mounted `/registrar/cart` does not resolve wizard queue reuse by specialist.

Runtime path:

1. `backend/app/api/v1/endpoints/registrar_wizard.py` creates visits and then
   calls `MorningAssignmentService._assign_queues_for_visit(...)`.
2. `backend/app/services/morning_assignment.py::_assign_single_queue(...)`
   resolves queue ownership through:
   - `patient_id`
   - `target_date`
   - `queue_tag`
3. `_resolve_existing_queue_claim_or_raise(...)` queries active `DailyQueue`
   rows by:
   - `DailyQueue.day == target_date`
   - `DailyQueue.queue_tag == queue_tag`
   - `DailyQueue.active == True`
4. It then looks for active `OnlineQueueEntry` rows by:
   - `patient_id`
   - queue ids from that `queue_tag` set

That means the mounted wizard-family runtime is now queue-tag-level and
day-scoped.

## Verdict

Claim model is confirmed as:

- `patient identity + queue_tag + queue_day`

It is not specialist-level.

## Readiness Implication

Claim ambiguity is no longer the main blocker for wizard-family migration.

The remaining blockers are outside claim identity itself:

- shared allocator surface in `MorningAssignmentService`
- billing-heavy mounted `/registrar/cart` owner
