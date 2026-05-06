# W2C Wizard Boundary Migration Status

Date: 2026-05-06

## Status

Current-main replacement for stale PR #90.

## Done

- Mounted same-day wizard create-branch materialization delegates to `QueueDomainService.allocate_ticket(allocation_mode="create_entry")`.
- Focused unit coverage proves default queue-domain delegation.
- Existing legacy allocator injection remains for characterization only.

## Deferred

- shadow/unmounted wizard route compatibility review
- dead-code cleanup after route ownership is proven
- broad allocator service removal
