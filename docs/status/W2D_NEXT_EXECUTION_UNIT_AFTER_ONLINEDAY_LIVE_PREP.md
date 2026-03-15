# Next Execution Unit After OnlineDay Live Replacement Prep

Date: 2026-03-09
Recommended next step: `A) replacement-prep for board/stats read surfaces`

## Why this is next

- read surfaces are the lowest-risk live legacy surface
- they are the closest candidates for replacement by SSOT-backed read models
- they do not require immediate resolution of legacy ticket-issuing semantics
- they do not require immediate business decision on manual day open/close

## Why not `next_ticket` first

- `next_ticket` is the last live legacy write allocator path
- it still depends on legacy counter semantics with no direct SSOT equivalent
- replacing it before read-surface prep would raise risk without reducing the
  broader visibility/consumer ambiguity

## Why not open/close day first

- those endpoints remain blocked by product/operational owner decisions
- the current system has no clear SSOT replacement for department/day
  intake-state control

## Execution shape

- preparation-first
- characterize consumers and payload expectations for:
  - `appointments.stats()`
  - `queues.stats()`
  - `board.state()`
- define whether `appointments.stats()` should be retired or redirected
