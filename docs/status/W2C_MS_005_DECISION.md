# Wave 2C MS-005 Decision

Date: 2026-03-07
Mode: analysis-first, docs-only
Target slice: `W2C-MS-005` number allocation boundary extraction

## Decision

`REQUIRES_DOMAIN_REFACTOR`

## Why This Is The Decision

`W2C-MS-005` is not safe as a bounded Phase 1 refactor because queue numbering
is not just a repository concern.

The review found four blocking realities:

1. Multiple live numbering sources exist:
   - `queue_service.get_next_queue_number()`
   - direct SQL `MAX(number)+1` in `qr_queue.py`
   - registrar `start_number + current_count`
   - force-majeure allocator
   - legacy `OnlineDay` / `last_ticket`
2. Duplicate policy is inconsistent across source paths.
3. Fairness is driven by `priority + queue_time`, not by `number` alone.
4. Legacy queue counters still exist and keep start-number semantics alive
   outside the SSOT queue-entry model.

## Why This Is Not `SAFE_TO_EXECUTE`

Because execution would require choosing one or more of these policy answers:

- Is there exactly one legal allocator API?
- May callers still ask for a number separately from entry creation?
- Which statuses count as active for duplicate prevention?
- Are trusted sources allowed to bypass duplicate checks permanently?
- Is ticket number authoritative for operator ordering, or only for display?
- How should restore/reorder/transfer flows preserve or override fairness?

Those are domain-model questions, not mechanical extraction questions.

## Why This Is Not `BLOCKED_BY_LEGACY`

Legacy contributes to the risk, but it is not the only blocker.

Even if legacy `OnlineDay` paths were frozen, the modern runtime still contains:

- mixed allocators
- split creation flows
- inconsistent duplicate rules
- fairness overrides via `priority`

So the slice is blocked by domain ambiguity first, legacy second.

## Preconditions Before Any Execution Attempt

1. Name one canonical allocator owner for SSOT queue entries.
2. Define canonical duplicate policy by source:
   - online
   - telegram
   - desk
   - morning assignment
   - confirmation
3. Define canonical active-status set for:
   - duplicate prevention
   - session reuse
   - reorder
   - fairness reads
4. Decide whether number is:
   - a historical ticket label only
   - or also the operator-ordering baseline
5. Freeze or isolate legacy `OnlineDay` semantics for the migration window.

## Safe Follow-Up Work

Allowed before any future `W2C-MS-005` execution:

- add queue-numbering characterization tests
- add fairness characterization tests around restore/reorder/transfer
- document one proposed allocator contract in `QueueDomainService`
- classify which callers must keep split `get_next_queue_number()` behavior and
  which must move to `create_queue_entry(auto_number=True)`

## Not Allowed Yet

- replacing direct QR SQL allocators with a shared helper
- changing numbering in registrar flows
- changing duplicate policy
- changing restore/reorder semantics
- changing legacy `OnlineDay` counter behavior

## Supporting Artifacts

- `docs/architecture/W2C_QUEUE_NUMBERING_DISCOVERY.md`
- `docs/architecture/W2C_QUEUE_NUMBERING_FLOWS.md`
- `docs/architecture/W2C_QUEUE_FAIRNESS_ANALYSIS.md`
- `docs/architecture/W2C_QUEUE_DUPLICATE_POLICY.md`
- `docs/architecture/W2C_QUEUE_NUMBERING_CONSISTENCY.md`
- `docs/architecture/W2C_QUEUE_LEGACY_INTERACTION.md`
- `docs/architecture/W2C_QUEUE_NUMBERING_RISK_MATRIX.md`
