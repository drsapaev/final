# Wave 2C Queue Track Status After OnlineDay

Date: 2026-03-09
Mode: analysis-first, docs-only

## Main production queue allocator track

Verdict:

`effectively complete`

## Why

The main production queue-allocation families are now aligned to
`QueueDomainService.allocate_ticket()`:

- confirmation family
- mounted registrar batch-only family
- mounted wizard family
- mounted QR full-update create branch

## What remains outside the main track

- `OnlineDay` legacy island
- `force_majeure` exceptional-domain
- dead / duplicate cleanup

## Interpretation

Remaining queue work is no longer about the main SSOT allocator boundary.

It is now split into:

- legacy isolation / retirement
- exceptional-domain ownership
- cleanup of dead or duplicate surfaces

This status is now superseded in more detail by:

- `docs/status/W2C_QUEUE_TRACK_STATUS_AFTER_FORCE_MAJEURE.md`
