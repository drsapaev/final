# Wave 2C Force Majeure Local Contract Ownership

Date: 2026-03-09
Mode: analysis-first, docs-only

## Summary

Force majeure owns its own local contract. It intentionally overrides several
base queue rules, but not every divergence is justified.

## Ownership by policy area

### Numbering override ownership

- Current owner:
  - `backend/app/services/force_majeure_service.py::_get_next_queue_number()`
  - `transfer_entries_to_tomorrow()`
- Current runtime behavior:
  - allocates a new number on the target queue/day
- Intentional:
  - yes, new target-queue number is intentional
- Drift candidate:
  - yes, because the helper ignores cancelled rows for monotonic history

### `queue_time` reset ownership

- Current owner:
  - `transfer_entries_to_tomorrow()`
- Current runtime behavior:
  - assigns fresh `datetime.utcnow()` to the transferred row
- Intentional:
  - yes
- Drift candidate:
  - no, as long as the exceptional contract stays explicit

### Priority override ownership

- Current owner:
  - `ForceMajeureService.TRANSFER_PRIORITY`
  - `transfer_entries_to_tomorrow()`
- Current runtime behavior:
  - sets `priority=2`
- Intentional:
  - yes
- Drift candidate:
  - no, this is the clearest explicit exceptional override

### Source override ownership

- Current owner:
  - `transfer_entries_to_tomorrow()`
- Current runtime behavior:
  - sets `source="force_majeure_transfer"`
- Intentional:
  - yes
- Drift candidate:
  - no

### Visit linkage preservation ownership

- Current owner:
  - `transfer_entries_to_tomorrow()`
- Current runtime behavior:
  - preserves `visit_id`
- Intentional:
  - yes
- Drift candidate:
  - no

### Duplicate behavior on target queue

- Current owner:
  - effectively `transfer_entries_to_tomorrow()`, because no separate gate
    exists before target-row creation
- Current runtime behavior:
  - may create a second active row on the tomorrow queue
- Intentional:
  - no
- Drift candidate:
  - yes, this remains the main later correction candidate

## Ownership verdict

Intentional local overrides:

- new target number
- fresh transfer-time `queue_time`
- explicit priority override
- explicit transfer source
- visit linkage preservation

Still looking like drift candidates:

- missing duplicate gate on target queue/day
- monotonic numbering gap caused by ignoring cancelled rows
