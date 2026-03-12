# W2D Next Execution Unit After online_queue_legacy_api_service Cleanup

Date: 2026-03-11
Mode: status decision

## Recommended next step

`duplicate/unmounted residue review`

## Why this is the safest next step

The evidence-based cleanup pattern is still working:

- identify one unmounted duplicate
- remove it
- validate OpenAPI and full backend suite

That continues to reduce residue without crossing into blocked operational or
product-semantics tails.

## Why broader action is not chosen yet

- `open_day` / `close_day` remain ops-sensitive
- `next_ticket` remains deprecate-later with unresolved external/manual usage
- board semantics remain blocked by `is_paused` / `is_closed`
