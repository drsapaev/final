# Wave 2D OnlineDay Replacement Requirements

Date: 2026-03-09
Mode: analysis-first, docs-only

## Live mounted legacy surfaces

| Surface | Current legacy owner | Future owner candidate | Retire or replace? | Migration complexity | User-visible impact |
|---|---|---|---|---|---|
| `appointments.open_day()` | `appointments.py` + `online_queue.get_or_create_day()` / settings counters | dedicated queue-operations admin service or explicit product retirement | Must be replaced or explicitly retired | High | Registrar/admin day-opening workflow changes |
| `appointments.close_day()` | `appointments.py` + `online_queue.get_or_create_day(open_flag=False)` | dedicated queue-operations admin service or explicit product retirement | Must be replaced or explicitly retired | High | Registrar/admin day-closing workflow changes |
| `appointments.stats()` | `appointments.py` + `online_queue.load_stats()` | shared queue read-model endpoint over SSOT queue data, or explicit retirement as duplicate stats surface | Can be retired if duplicate; otherwise must be replaced | Medium | Admin stats payload and tooling behavior |
| `queues.stats()` | `queues.py` + `online_queue.load_stats()` | SSOT queue stats/read-model endpoint | Must be replaced unless client is retired | Medium | Queue counters visible to operator dashboards/integrations |
| `queues.next_ticket()` | `queues.py` + `online_queue.issue_next_ticket()` | dedicated front-desk ticket-issuing service over non-OnlineDay ownership, or explicit retirement if obsolete | Must be replaced or explicitly retired | High | Ticket issuing workflow, numbering, and waiting counts |
| `board.state()` | `board.py` + `online_queue.load_stats()` | SSOT board/display read model | Must be replaced if board remains supported | High | Public/operator board visibility |

## Notes per surface

### `appointments.open_day()` / `appointments.close_day()`

- These are not ordinary queue-entry allocators.
- They own legacy day-open/day-close administration.
- Cleanup cannot proceed until product/business decides whether manual
  department-day control still exists after OnlineDay retirement.

### `appointments.stats()` and `queues.stats()`

- These look partially duplicative.
- Cleanup prep should treat them separately first, then decide whether one can
  be retired earlier instead of replacing both.

### `queues.next_ticket()`

- This is the hardest live legacy surface because it still issues numbers.
- It cannot be deleted just because the SSOT queue allocator track is complete;
  it needs an explicit replacement or product retirement decision.

### `board.state()`

- If any board UI remains supported, this read model must survive somewhere.
- That means `board_state()` is a replacement-prep item, not an early cleanup
  candidate.

## Replacement-requirements verdict

The first safe cleanup work is not replacement itself. It is preparation for
replacement/retirement, starting with:

- endpoint characterization
- consumer discovery
- owner decision for day-open/day-close
- owner decision for `next_ticket`
