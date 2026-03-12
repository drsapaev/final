# W2D Next Execution Unit After Appointments QRCode Deprecation Prep

Date: 2026-03-11
Mode: status decision

## Recommended next step

`support/test-only residue review`

## Why this is the safest next step

The cleanest mounted OnlineDay compatibility tails have now been narrowed
further through bounded deprecation-prep:

- `appointments.stats`
- `appointments/qrcode`
- `board/state`

The remaining larger tails are blocked by:

- product semantics
- ops/manual usage risk

So the best next engineering move is to look for the next bounded
support-only/test-only residue cleanup slice rather than forcing a blocked
operational surface.

## Why broader action is not chosen yet

- `open_day` / `close_day` remain ops-sensitive
- `next_ticket` remains deprecate-later with unresolved external/manual usage
- board tail semantics remain blocked by `is_paused` / `is_closed`
