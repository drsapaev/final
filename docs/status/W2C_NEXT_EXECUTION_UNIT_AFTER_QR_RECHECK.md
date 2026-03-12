# Wave 2C Next Execution Unit After QR Recheck

Date: 2026-03-09
Mode: docs-only readiness review
Status: `one more narrow QR fix`

## Selected Next Step

One more narrow QR fix.

## Exact Recommended Slice

Introduce a minimal QR-compatible create-entry adapter so the mounted
`full_update_online_entry()` create seam can route through
`QueueDomainService.allocate_ticket()` without dropping QR row fields.

The fix should stay narrow:

- no numbering redesign
- no duplicate-policy redesign
- no `queue_session` semantic change
- no public QR join flow refactor

## Why This Step Comes Next

It removes the last concrete boundary-compatibility blocker while preserving the
already characterized QR runtime.

After that, the family should be ready for an actual boundary migration slice.
