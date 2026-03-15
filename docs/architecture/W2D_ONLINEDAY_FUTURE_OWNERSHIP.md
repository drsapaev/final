# Wave 2D OnlineDay Future Ownership

Date: 2026-03-09
Mode: analysis-first, docs-only

Owner categories:

- `A)` replace with SSOT queue/domain path
- `B)` replace with read-model / reporting layer
- `C)` replace with operational admin adapter
- `D)` retire instead of replace
- `E)` human/business decision required

| Live surface | Future owner category | Candidate future owner | Why |
|---|---|---|---|
| `appointments.py::open_day()` | `E)` human/business decision required | If retained, later `C)` operational admin adapter over SSOT queue operations | Current legacy meaning is department/day intake control plus `start_number`; there is no direct SSOT equivalent yet. |
| `appointments.py::stats()` | `D)` retire instead of replace | Retire after consumer confirmation, or redirect to unified read model | It duplicates `queues.stats()` semantics and does not appear to own unique queue state. |
| `appointments.py::close_day()` | `E)` human/business decision required | If retained, later `C)` operational admin adapter | Current behavior is day-intake closure over legacy state; SSOT has no department/day close contract. |
| `queues.py::stats()` | `B)` replace with read-model / reporting layer | SSOT queue read model composed from `DailyQueue` / `OnlineQueueEntry` aggregates | This is a department/day read surface and should move to a dedicated read-model, not to allocator mutation code. |
| `queues.py::next_ticket()` | `E)` human/business decision required | If retained, later `C)` operational admin adapter | Legacy front-desk ticket issuing has no direct SSOT equivalent and may need product-level redesign or retirement. |
| `board.py::board_state()` | `B)` replace with read-model / reporting layer | Board/display read model over SSOT queue aggregates | Board is a consumer-facing projection problem, not an allocator problem. |
| `online_queue.py` service | `D)` retire instead of replace | Split responsibilities into read-model + admin adapter if needed | Service is just the runtime owner of the legacy island; it should disappear after surface replacement. |
| `online.py::OnlineDay` model | `D)` retire instead of replace | Remove after all mounted surfaces are replaced or retired | Model has no justified future role inside SSOT queue architecture. |

## Ownership verdict

The future state is intentionally asymmetric:

- read surfaces should move to read-model ownership
- write/admin legacy semantics require product/operational decisions first
- `online_queue.py` and `OnlineDay` are not replacement targets; they are
  retirement targets

This means OnlineDay removal is blocked less by code complexity and more by
missing owner decisions for legacy operator workflows.
