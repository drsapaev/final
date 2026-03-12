# W2D OnlineDay Board/Stats Target Read Model

## Target Owner Candidate

The replacement should not be another allocator path. It should be an SSOT-backed
read-model layer that reads from the modern queue system and exposes legacy-compatible
department/day counters where still needed.

Recommended target shape:

1. `QueueBoardStatsReadModel`
   - Owner candidate: new read-model service/repository adjacent to existing
     queue read services, not `QueueDomainService.allocate_ticket()`
   - Purpose: provide department/day counter projection for legacy board/stats surfaces
2. `BoardStateReadAdapter`
   - Owner candidate: adapter over the same stats projection plus board/display config
   - Purpose: replace legacy `board.state()` separately from pure counter reads

## Required SSOT Sources

- `DailyQueue`
- `OnlineQueueEntry`
- doctor / department ownership mapping
- display configuration sources where board-facing metadata is needed
  - likely `DisplayBoard` / display config tables
  - possibly `Setting(category="display_board")` compatibility values where still used

## Required Aggregations

For the first read-model slice, the future projection must be able to answer:

- department/day visibility
- total current last-issued or highest-visible number equivalent
- `waiting` count
- `serving` count
- `done` count
- queue-open / display-open surrogate only if the consumer truly requires it

## Legacy Concepts That Need Mapping

These concepts exist in the OnlineDay world and do not map 1:1 to SSOT today:

- `department + date_str` legacy ownership
- `start_number`
- `last_ticket`
- `is_open`
- single department/day counter world instead of specialist/day queue ownership

## Practical Replacement Direction

- `queues.stats()` should be replaced first by `QueueBoardStatsReadModel`
- `appointments.stats()` should either redirect to the same read-model or be retired
- `board.state()` should be replaced later by an adapter that combines:
  - SSOT queue counters
  - board/display configuration
  - any remaining open/closed presentation flags
