# Wave 2C Wizard Allocator Extraction Plan

Date: 2026-03-08
Mode: behavior-preserving decomposition

## Current Call Site

Mounted `/registrar/cart` currently mixes same-day queue assignment directly
inside billing-heavy cart orchestration:

- `backend/app/api/v1/endpoints/registrar_wizard.py`

Old inlined queue-assignment block:

- loop over `created_visits`
- call `MorningAssignmentService._assign_queues_for_visit(...)`
- update `visit.status`
- collect `queue_numbers`
- handle queue warnings inline

## Extraction Target

Extract only the mounted same-day wizard allocator surface into a dedicated
wizard-family seam.

New seam target:

- `RegistrarWizardQueueAssignmentService.assign_same_day_queue_numbers(...)`

## Why This Is Behavior-Preserving

- it keeps `MorningAssignmentService` as the underlying allocator owner
- it keeps the same `source="desk"` semantics
- it keeps same-day-only assignment behavior
- it keeps the same `visit.status = "open"` transition when queue assignments
  exist
- it keeps warning-and-continue behavior on assignment failures
- it does not change numbering, `queue_time`, or fairness

## What Remains Coupled To Billing

The mounted `/registrar/cart` owner still keeps:

- visit creation
- invoice creation
- invoice-visit linking
- billing total calculation
- final response shaping

This slice does not refactor those concerns.

## What Becomes The Allocator Seam

The extracted seam owns only:

- same-day confirmed-visit filtering
- handoff into queue-assignment logic
- queue-number aggregation for the mounted wizard response
- local warning handling for queue assignment failures
