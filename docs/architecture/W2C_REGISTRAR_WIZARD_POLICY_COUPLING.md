# Wave 2C Registrar Wizard Policy Coupling

Date: 2026-03-08
Mode: characterization-only

## Numbering

- same-day mounted wizard flow allocates through
  `MorningAssignmentService._assign_single_queue()`
- numbering is still delegated to `queue_service.create_queue_entry(auto_number=True)`
- the wizard family does not own a separate numbering algorithm, but it does own
  the decision of when queue allocation happens inside the cart request

## Duplicate Policy

- duplicate behavior is queue-local, not canonical specialist-day based
- `_assign_single_queue()` checks for any existing `OnlineQueueEntry` matching the
  resolved `DailyQueue` and `patient_id`
- no explicit status filter is applied in this duplicate gate
- result: wizard reuse semantics are broader than the active-entry contract and
  tied to queue resolution details

## Active Entry Semantics

- the current runtime does not use the canonical active-status contract directly
- it reuses the first queue row found in the resolved queue for the patient
- this creates a contract gap versus the canonical active-entry set already
  defined for Wave 2C

## Queue Claim Model

- observed wizard claim model is `queue_tag`-driven
- one visit can fan out into multiple queue claims when its services map to
  multiple `queue_tag` values
- this differs from the mounted registrar batch-only family, which was clarified
  around a specialist-level claim

## Visit Lifecycle

- registrar cart creates visits as `confirmed`
- same-day queue assignment upgrades the visit to `open`
- future-day visits remain `confirmed` and defer queue allocation
- reused queue rows do not imply that row ownership or `visit_id` is updated

## Billing And Payment Coupling

- invoice creation happens in the same request as visit creation and queue
  assignment
- queue allocation is therefore coupled to billing/invoice orchestration
- failures in queue assignment are logged and do not necessarily abort visit or
  invoice creation
- this is the main reason the family is not yet a clean boundary-migration target

## Source Ownership

- new wizard-created queue rows use `source="desk"`
- reused rows preserve their existing `source`
- this means the wizard family does not fully own `source` semantics once reuse is
  involved

## Fairness And Queue Time

- new wizard-created rows receive a fresh `queue_time`
- reused rows preserve the existing `queue_time`
- this is behavior-preserving and consistent with fairness intent, but it is still
  embedded in the mixed cart/billing flow

## Coupling Verdict

The mounted registrar wizard family is primarily blocked by two things:

1. billing/invoice orchestration in the same request
2. unresolved claim-model semantics between queue-tag expansion and the broader
   Wave 2C contracts
