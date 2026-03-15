# W2D board legacy usage reduction readiness

## Verdict

`BLOCKED_BY_PRODUCT_SEMANTICS`

## Why

Legacy dependency is already narrow, but the remaining fields:

- `is_paused`
- `is_closed`

do not have a confirmed mounted backend owner.

The blocker is no longer data parity or adapter wiring. The blocker is semantic:

- what exactly these flags mean
- which domain should own them
- whether they are persistent settings or transient operational state

## What is already ready

- queue/display metadata migration for the confirmed fields
- additive board-display endpoint
- staged frontend adapter usage

## What is not ready

- field migration of `is_paused` / `is_closed`
- further reduction of legacy `/board/state` usage for those fields
