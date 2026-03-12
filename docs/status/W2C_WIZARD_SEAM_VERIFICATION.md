# Wave 2C Wizard Seam Verification

Date: 2026-03-09
Mode: readiness review, docs-only
Status: `verified`

## Runtime Files Reviewed

- `backend/app/api/v1/endpoints/registrar_wizard.py`
- `backend/app/services/registrar_wizard_queue_assignment_service.py`
- `backend/app/services/morning_assignment.py`
- `backend/app/services/queue_service.py`

## What Is Verified

### 1. The mounted endpoint no longer owns the allocator call inline

`/registrar/cart` now hands same-day queue assignment to:

- `RegistrarWizardQueueAssignmentService.assign_same_day_queue_numbers(...)`

So invoice/cart orchestration no longer performs the queue-assignment loop
inline in the endpoint body.

### 2. The new seam is wizard-specific

The extracted seam is local to mounted wizard-family runtime, not to batch,
confirmation, QR, or legacy `OnlineDay` families.

### 3. A clear migration point now exists

The new explicit handoff point is:

- `RegistrarWizardQueueAssignmentService.assign_same_day_queue_numbers(...)`

That is the correct outer seam for any future wizard-family boundary migration.

## What Is Not Yet Isolated

The seam still delegates the full create/reuse branch to shared
`MorningAssignmentService._assign_queues_for_visit(...)`.

Inside that shared path, the exact create-branch handoff remains bundled with:

- queue claim resolution
- active-entry reuse checks
- payload assembly
- direct `queue_service.create_queue_entry(...)`

## Verification Verdict

Allocator surface is now isolated enough at the outer seam level.

It is not yet isolated enough at the exact create-branch replacement point.
