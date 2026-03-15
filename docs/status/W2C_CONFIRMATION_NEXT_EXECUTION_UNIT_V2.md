# Wave 2C Confirmation Next Execution Unit V2

Date: 2026-03-07
Mode: post-correction planning

## Recommended Next Step

`confirmation boundary migration slice`

## Why This Is The Right Next Unit

The reuse-existing-entry correction is complete for the mounted confirmation
family.

The next narrow step can focus on plumbing, not contract repair:

- keep the corrected reuse/ambiguity semantics
- route the creation branch through `QueueDomainService.allocate_ticket()`
- preserve legacy numbering behavior inside the boundary
- avoid touching `qr_queue`, `OnlineDay`, or unrelated allocator families

## Why This Is Safe Now

The main blocker was the duplicate-creating confirmation drift.
That blocker has now been removed and regression-tested.

## Suggested Scope For The Next Unit

- `backend/app/services/visit_confirmation_service.py`
- the confirmation branch in `backend/app/api/v1/endpoints/registrar_wizard.py`
- no allocator algorithm change
- no broader registrar migration
- no queue-policy redesign outside confirmation

## Status

`SAFE_NEXT_STEP_IDENTIFIED`
