# Wave 2D OnlineDay Live Replacement Validation

Date: 2026-03-09
Mode: analysis-first, docs-only

## Validation buckets before any live replacement

### 1. Endpoint-level characterization

Required for:

- `appointments.open_day()`
- `appointments.stats()`
- `appointments.close_day()`
- `queues.stats()`
- `queues.next_ticket()`
- `board.state()`

Checks:

- request shape
- auth/role requirements
- response payload and field meanings
- mounted route names and query param aliases

### 2. Board/stats parity validation

Required for:

- `appointments.stats()`
- `queues.stats()`
- `board.state()`

Checks:

- same department/day request yields internally consistent counters
- any replacement read model matches user-visible payload fields
- duplicate endpoint behavior is characterized before retirement decision

### 3. `next_ticket` state/numbering validation

Required for:

- `queues.next_ticket()`
- `online_queue.issue_next_ticket()`

Checks:

- `start_number` handling
- `last_ticket` increment
- waiting counter increment
- interaction with `is_open`
- observable payload shape after issuing a ticket

### 4. Open/close day validation

Required for:

- `appointments.open_day()`
- `appointments.close_day()`

Checks:

- state transition behavior for `is_open`
- `start_number` write behavior
- stats payload after open/close
- websocket/broadcast side effects

### 5. Snapshot / characterization requirements

Before runtime replacement work:

- capture characterization tests or snapshots for each live surface
- confirm whether board/stats endpoints share identical counter truth
- preserve rollback-ready baselines for live operator flows

## Validation verdict

The first replacement-prep execution unit should target read surfaces because
their validation is simpler:

- no counter mutation
- no day-state mutation
- no operator write-path rollback problem

Write-surface replacement prep should begin only after read-surface baselines
and consumer ownership are explicit.
