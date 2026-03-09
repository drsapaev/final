# Wave 2C Wizard Seam Verification V2

Date: 2026-03-09
Mode: readiness review, docs-only

## Files Checked

- `backend/app/api/v1/endpoints/registrar_wizard.py`
- `backend/app/services/registrar_wizard_queue_assignment_service.py`
- `backend/app/services/morning_assignment.py`
- `backend/app/services/queue_service.py`

## Verification Results

### 1. Mounted `/registrar/cart` no longer holds allocator logic inline

Confirmed.

The mounted endpoint now delegates same-day queue assignment to:

- `RegistrarWizardQueueAssignmentService.assign_same_day_queue_numbers(...)`

The endpoint itself no longer loops queue claims or calls the allocator
directly.

### 2. Wizard-family now has both required seams

Confirmed.

Wizard-family now has:

- outer seam:
  `RegistrarWizardQueueAssignmentService.assign_same_day_queue_numbers(...)`
- create-branch handoff seam:
  `MorningAssignmentService.prepare_wizard_queue_assignment(...)` +
  `MorningAssignmentCreateBranchHandoff` +
  `RegistrarWizardQueueAssignmentService._allocate_create_branch_handoff(...)`

### 3. Shared `MorningAssignmentService` no longer hides wizard-local create point

Confirmed for the mounted wizard-family path.

Shared morning-assignment code still prepares create-entry kwargs, but the
wizard-family create materialization point is now explicit and local to the
wizard seam.

### 4. Remaining hidden coupling

No hidden allocator call site remains in mounted wizard-family runtime.

Remaining coupling is explicit, not hidden:

- shared create-kwargs assembly in `MorningAssignmentService`
- same request transaction still contains billing/invoice + queue assignment

## Seam Verdict

The seams are now explicit enough to support a direct boundary-readiness
decision.
