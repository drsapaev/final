# Wave 2C OnlineDay Runtime Conflicts

Date: 2026-03-09
Mode: analysis-first, docs-only

## Summary

The OnlineDay family conflicts with the current queue contracts by design, not
because of one isolated implementation bug.

It represents a separate department/day counter worldview:

- `OnlineDay`
- `Setting(category="queue")`
- legacy counters `last_ticket`, `waiting`, `serving`, `done`

These conflicts remain production-relevant because mounted endpoints still use
that worldview.

## Numbering conflicts

### Current runtime

- Numbering is `department + date_str` scoped, not `DailyQueue` scoped.
- `issue_next_ticket()` increments `last_ticket` in settings storage.
- The live mounted path `POST /api/v1/queues/next-ticket` can issue a ticket
  without creating an SSOT `OnlineQueueEntry`.

### Conflict with current contract

This conflicts with `W2C_QUEUE_NUMBERING_CONTRACT.md`, which requires:

- queue-local numbering
- day-scoped within `DailyQueue`
- transactionally coupled queue-entry creation

### Production relevance

- Yes, still production-relevant
- Main affected path:
  - `POST /api/v1/queues/next-ticket`

## Duplicate conflicts

### Current runtime

- The live mounted allocator path has no patient-level duplicate gate.
- The disabled legacy self-join path uses `phone` / `telegram_id` keys in
  settings rather than canonical `identity_key + queue_id + queue_day`.

### Conflict with current contract

This conflicts with `W2C_DUPLICATE_POLICY_CONTRACT.md`, which requires:

- patient-first identity resolution
- one active entry per identity per queue/day unless explicitly overridden

### Production relevance

- Partially production-relevant
- The mounted `/queues/next-ticket` path bypasses patient-linked duplicate
  semantics entirely
- The phone/telegram duplicate memory remains in disabled legacy join code

## Fairness conflicts

### Current runtime

- OnlineDay world has no `queue_time`
- no priority ordering
- counters are `waiting`, `serving`, `done`

### Conflict with current contract

This conflicts with the SSOT fairness model:

- `priority DESC`
- `queue_time ASC`

### Production relevance

- Yes
- Mounted board/stats paths expose legacy queue state that is not derived from
  canonical queue-entry ordering

## Active-entry conflicts

### Current runtime

- OnlineDay family does not use canonical active statuses
- it uses legacy counters and a simplified day-open model

### Conflict with current contract

This conflicts with `W2C_ACTIVE_ENTRY_CONTRACT.md`, which defines active as:

- `waiting`
- `called`
- `in_service`
- `diagnostics`

### Production relevance

- Yes, conceptually
- Mounted legacy endpoints still reflect the old waiting/serving/done model

## Source and identity conflicts

### Current runtime

- The live mounted path does not record canonical `source`
- the disabled self-join path remembers identity through ad hoc settings keys

### Conflict with current contract

This conflicts with the SSOT queue families, where source and identity are part
of a concrete queue-entry row.

### Production relevance

- Medium
- Most visible in the disabled legacy self-join path and in the absence of any
  source semantics for `POST /queues/next-ticket`

## Runtime bridge conflicts

### Current runtime

- No runtime bridge was found between `OnlineDay` counters and
  `DailyQueue` / `OnlineQueueEntry`
- coexistence is side-by-side, not synchronized

### Conflict with migration strategy

`W2C_ALLOCATOR_MIGRATION_STRATEGY.md` already treats OnlineDay as a separate
legacy track that should be frozen or retired later, not merged into the main
boundary rollout.

### Production relevance

- Yes
- It is the main reason OnlineDay should not stay in the main queue track

## Conflict verdict

OnlineDay conflicts are still production-relevant, but they are legacy-island
conflicts, not blockers for the already migrated SSOT allocator families.
