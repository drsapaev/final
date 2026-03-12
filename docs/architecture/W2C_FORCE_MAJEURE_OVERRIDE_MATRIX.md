# Wave 2C Force Majeure Override Matrix

Date: 2026-03-09
Mode: contract-review

| Aspect | Current runtime behavior | Base queue contract | Intentional override | Justification | Risk if left unchanged |
|---|---|---|---|---|---|
| Numbering | New row on tomorrow queue gets next number from `_get_next_queue_number()`, but cancelled rows are excluded from the max calculation | Monotonic, queue-local, day-scoped, no historical reuse | Partial | New target-queue number is intentional; ignoring cancelled rows is not justified | High: possible number reuse within target queue/day |
| Duplicate policy | No canonical target-queue duplicate gate; transfer can create a second active tomorrow row for the same patient | One active entry per identity + queue + day unless explicit override | No | No business rationale found for same-target duplicate creation | High: duplicate active claims on tomorrow queue |
| `queue_time` | New row gets fresh `datetime.utcnow()` | Normal queue claim keeps immutable fairness timestamp | Yes | Transfer creates a new exceptional tomorrow claim | Medium: acceptable only if isolated as exceptional policy |
| Fairness / priority | `priority=2` forces transferred rows to the front | Normal fairness = `priority DESC`, `queue_time ASC` with ordinary priorities | Yes | Transfer is meant to push patients to the front next day | Medium: safe only as explicit exceptional policy |
| Active-entry rules | Runtime pending selector uses only `waiting` and `called`; service docstring claims broader set | Canonical active set = `waiting`, `called`, `in_service`, `diagnostics` | Partial | Narrow transfer-eligibility may be intentional, but docs/runtime mismatch is not | Medium: operator confusion and unclear eligibility semantics |
| Source semantics | New rows use `force_majeure_transfer` | Normal sources are `online`, `desk`, `morning_assignment`, etc. | Yes | Important audit trail for exceptional transfer | Low |
| Visit linkage | `visit_id` is copied to the new row | Visit linkage should remain explicit and consistent | Yes | Transfer should keep linkage to the same visit context | Low |

## Summary

Intentional overrides:

- new target-queue number
- new target `queue_time`
- priority override
- exceptional `source`
- visit linkage preservation

Likely drift or bug:

- no duplicate gate on the target queue/day
- cancelled rows excluded from target numbering history
- active-eligibility docs/runtime mismatch
