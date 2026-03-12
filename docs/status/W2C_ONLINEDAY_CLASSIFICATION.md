# Wave 2C OnlineDay Classification

Date: 2026-03-09
Mode: analysis-first, docs-only

## Classification verdict

`D) mixed legacy with one live path`

## Why this classification fits

- The family is **not dead**:
  - `appointments.open_day`
  - `appointments.stats`
  - `appointments.close`
  - `queues.stats`
  - `queues.next-ticket`
  - `board.state`
  are still mounted.
- It is **not fully active mainline queue runtime** either:
  - there is no bridge to `DailyQueue` / `OnlineQueueEntry`
  - the main queue-allocation families already live elsewhere
- There is **one live mounted allocator path**:
  - `POST /api/v1/queues/next-ticket`
- The rest of the mounted surface is:
  - admin/open-close compatibility
  - read-only legacy stats / board visibility

## Secondary interpretation

Track ownership-wise, the same evidence also supports treating OnlineDay as a
separate legacy island.

That ownership decision is documented separately in:

- `docs/status/W2C_ONLINEDAY_TRACK_DECISION.md`
