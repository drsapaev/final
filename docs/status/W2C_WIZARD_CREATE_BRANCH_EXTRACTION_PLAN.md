# Wave 2C Wizard Create Branch Extraction Plan

Date: 2026-05-06

## Slice

1. Add prepared assignment dataclasses to `MorningAssignmentService`.
2. Refactor `_assign_single_queue(...)` to materialize a prepared assignment.
3. Let `RegistrarWizardQueueAssignmentService` materialize create handoffs explicitly.
4. Add unit coverage for reuse payload and create-handoff paths.

## Denied Scope

- frontend changes
- migrations
- CI changes
- queue numbering redesign
- billing/invoice orchestration
