# W2D Legacy Re-entry Status

This document refreshes the remaining post-W2C legacy/deprecation tails after
the Postgres pilot was converted into a CI guardrail.

## Tail status matrix

| Tail | Current status | Blocked | Blocker type | Architectural value if progressed now | Risk level |
| --- | --- | --- | --- | --- | --- |
| OnlineDay deprecation continuation | Partially prepared, but not resumed after Postgres alignment work | No, for selected read-only sub-slices | Technical / sequencing only | High | Medium |
| `appointments.stats()` legacy read surface | Still mounted inside the OnlineDay island; no confirmed live frontend consumer found | No | None confirmed; only consumer/retirement verification needed | High | Low to medium |
| `appointments/qrcode` compatibility route | Still mounted, but only returns a tiny QR payload stub and does not own OnlineDay writes | No | None confirmed; only consumer/retirement verification needed | Medium to high | Low |
| `queues.stats()` remaining compatibility fields (`is_open`, `start_number`) | Stable with partial SSOT-backed replacement already in place | No, but low urgency | Technical / compatibility only | Medium | Low |
| Legacy board tail (`GET /api/v1/board/state`) | Compatibility fallback remains; board page is mostly off it | Partly | Product semantics for `is_paused` / `is_closed` | Medium | Medium |
| Board flags `is_paused` / `is_closed` | Narrowest remaining board blocker | Yes | Product / business semantics | Medium | Medium |
| `open_day` / `close_day` | Characterized and reframed, but behavior changes remain blocked | Yes | Ops / external usage risk | High | High |
| `next_ticket` | Contract direction already set to deprecate-later | Yes, for code change | Ops / external usage risk | Medium to high | High |
| Support/test-only residue cleanup | Most obvious removals already done; a small retained residue remains | No | None for very narrow follow-ups | Low to medium | Low |
| Docs / architecture consolidation | Always possible | No | None | Low to medium | Low |
| Pause-point/status formalization | Mostly already documented through alignment review and CI guardrail docs | No | None | Low | Low |

## Key takeaway

The big change since the last legacy-roadmap review is not inside the legacy
surfaces themselves. It is that the queue-sensitive Postgres regression signal
is now automated in CI.

That lowers the risk of returning to OnlineDay deprecation work, but it does
not unblock the tails that are still waiting on:

- product semantics (`is_paused`, `is_closed`)
- operational/manual usage confirmation (`open_day`, `close_day`, `next_ticket`)

So the best re-entry target is now a bounded legacy surface that is:

- still live
- not blocked by product/ops uncertainty
- small enough to reduce the OnlineDay island without reopening architecture
  risk
