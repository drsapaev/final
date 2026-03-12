# W2D Queues Stats Minimal SSOT Model

## Goal

Define the smallest SSOT-backed read model that could eventually replace:

- `GET /api/v1/queues/stats`

without immediately solving the broader `board.state` or OnlineDay admin/write
surfaces.

## Target Owner Candidate

Recommended first owner:

- `QueueDepartmentStatsReadModel`

Recommended placement:

- adjacent to SSOT queue read services / repositories
- read-only layer
- not part of `QueueDomainService.allocate_ticket()`

This is a read-model concern, not an allocator concern.

## Required SSOT Data Sources

Minimum candidate sources:

- `DailyQueue`
- `OnlineQueueEntry`
- doctor / specialist to department mapping
- queue profile metadata where needed to resolve department ownership

## Minimal First-Replacement Output

For the smallest safe first replacement, the SSOT-backed model should aim to
support this compatibility payload:

| Field | Initial SSOT replacement expectation |
| --- | --- |
| `department` | Echo normalized request department |
| `date_str` | Echo normalized request day |
| `last_ticket` | SSOT-derived highest visible / issued number equivalent for the mapped department-day |
| `waiting` | SSOT aggregate for waiting entries in the mapped department-day |
| `serving` | SSOT aggregate for currently serving entries in the mapped department-day |
| `done` | SSOT aggregate for completed entries in the mapped department-day |
| `is_open` | Compatibility field; likely requires temporary legacy fallback or explicit business decision |
| `start_number` | Compatibility field; likely requires temporary legacy fallback or explicit business decision |

## Department / Day Mapping Assumptions

The biggest modeling gap is not the counter math itself but the ownership map:

- legacy world is `department + date`
- SSOT world is primarily queue/specialist/day

So the first SSOT model requires a mapping layer that can answer:

- which SSOT queues belong to the requested legacy department
- for the requested day

That mapping is currently an assumption, not yet a finalized runtime artifact.

## Fields That Need Strict First-Slice Parity

For the confirmed live consumer, strict parity is most important for:

- `last_ticket`
- `waiting`
- `serving`
- `done`

## Fields That Likely Need Deferred Decision or Temporary Legacy Fallback

These fields are currently legacy-only and not confirmed as required by the live
consumer:

- `is_open`
- `start_number`

Recommended handling for the first replacement step:

- keep them in the response shape
- but allow them to stay legacy-backed until product/business sign-off or until
  a dedicated operational replacement exists

## What This Minimal Model Does Not Need Yet

It does not need to solve:

- board metadata (`brand`, `logo`, announcements, display flags)
- `next_ticket`
- `open_day` / `close_day`
- OnlineDay model retirement

## Practical Conclusion

The smallest viable SSOT replacement for `queues.stats` is a hybrid-compatible
read model:

- SSOT-backed for core counters
- compatibility-preserving for legacy-only fields

That makes a comparison harness the safest next code step before any live route
switch.
