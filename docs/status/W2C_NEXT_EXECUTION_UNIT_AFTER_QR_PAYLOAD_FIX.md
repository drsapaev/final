# Wave 2C Next Execution Unit After QR Payload Fix

Date: 2026-03-09
Mode: post-compatibility-fix decision
Status: `QR boundary migration`

## Selected Next Step

QR boundary migration.

## Exact Recommended Slice

Move the mounted QR additional-service create seam in
`full_update_online_entry()` from QR-local direct materialization to:

- `QueueDomainService.allocate_ticket(allocation_mode="create_entry")`

while preserving:

- raw numbering behavior
- `queue_time` behavior
- source inheritance
- additional-service independent-entry behavior

## Why This Step Comes Next

The only known migration blocker was QR payload compatibility.

That blocker is now closed, and the family no longer needs another readiness or
contract-clarification pass before the caller migration.
