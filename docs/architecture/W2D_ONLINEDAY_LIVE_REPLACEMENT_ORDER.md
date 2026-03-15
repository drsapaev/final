# Wave 2D OnlineDay Live Replacement Order

Date: 2026-03-09
Mode: analysis-first, docs-only

## Safest replacement order

### Stage 1: Read-surface replacement prep

Targets:

- `board.py::board_state()`
- `queues.py::stats()`
- `appointments.py::stats()` (retire-vs-redirect decision)

Prerequisites:

- consumer map for board/stats surfaces
- SSOT aggregate candidate identified
- response-shape baseline captured

Migration risk:

- Medium

Validation needed:

- board/stats payload comparison
- same department/day baseline vs proposed read model
- duplicate-surface inventory (`appointments.stats()` vs `queues.stats()`)

Rollback concern:

- read-surface replacement can be rolled back at endpoint level if payload
  divergence is detected

### Stage 2: `next_ticket` replacement prep

Target:

- `queues.py::next_ticket()`

Prerequisites:

- business decision: retain front-desk ticket issuer vs retire
- numbering/queue-state characterization for legacy behavior
- future owner category chosen

Migration risk:

- High

Validation needed:

- `start_number` and `last_ticket` semantics
- waiting counter increment behavior
- board/stats parity after issuing ticket

Rollback concern:

- write-path rollback must preserve counters and operator workflow continuity

### Stage 3: Open/close day admin replacement prep

Targets:

- `appointments.py::open_day()`
- `appointments.py::close_day()`

Prerequisites:

- product decision whether manual day open/close remains a supported workflow
- operational owner identified
- websocket side effects mapped

Migration risk:

- High

Validation needed:

- day-open/day-close state transitions
- `start_number` effect on ticket issuance
- websocket/broadcast compatibility

Rollback concern:

- rollback must restore admin ability to reopen/close intake without losing day
  state

### Stage 4: Service/model retirement prep

Targets:

- `online_queue.py`
- `OnlineDay`

Prerequisites:

- Stages 1-3 complete
- no mounted surface still depends on OnlineDay runtime

Migration risk:

- High if attempted early, Low after full surface replacement

Validation needed:

- import audit
- route ownership audit
- final legacy state/data retention decision

Rollback concern:

- should remain trivial if done only after live surfaces are already retired or
  replaced

## Order verdict

Safest order is:

1. board/stats read surfaces
2. `next_ticket` write surface
3. open/close day admin surfaces
4. service/model retirement

This keeps read-model work ahead of operational writes and leaves the hardest
business-coupled legacy semantics for later phases.
