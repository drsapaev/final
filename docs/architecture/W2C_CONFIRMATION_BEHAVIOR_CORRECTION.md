# Wave 2C Confirmation Behavior Correction

Date: 2026-05-05
Mode: current-main replacement for stale PR #74

## Scope

This slice preserves the useful behavior from old PR #74 on current `main` after
replacement parent PR #261 superseded the old confirmation contract branch.

Included:

- `VisitConfirmationService` active-entry reuse before fresh queue allocation
- registrar confirmation bridge delegation to `VisitConfirmationService`
- explicit `409` domain conflict for ambiguous active queue ownership
- focused characterization/unit coverage for reuse and ambiguity

Excluded:

- allocator algorithm redesign
- RBAC changes
- frontend changes
- notification/realtime changes
- migrations or queue schema changes

## Corrected behavior

When same-day confirmation resolves a queue/day claim, it first checks active
entries in the same queue using canonical active statuses:

- `waiting`
- `called`
- `in_service`
- `diagnostics`

If one compatible entry matches by patient, normalized phone, or Telegram id,
confirmation reuses it. Reuse preserves the existing number and queue_time, and
links the row to the confirmed visit when `visit_id` is still empty.

If no compatible active row exists, the existing legacy allocation path still
creates a fresh confirmation queue entry.

If multiple compatible rows exist, or the matched row belongs to another visit
or patient, confirmation raises an explicit domain conflict instead of silently
allocating another active row.

## Compatibility decision

Direct merge of old PR #74 is unsafe because its base branch is stale. This
replacement keeps the behavior contract while avoiding stale parent runtime and
docs context.