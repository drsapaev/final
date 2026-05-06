# W2C Wizard Boundary Migration Plan

Date: 2026-05-06

## Goal

Move the mounted registrar wizard create-branch seam from direct queue-service allocation to the queue domain boundary without changing the external queue-number payload.

## Steps

1. Preserve `MorningAssignmentCreateBranchHandoff` as the preparation/output seam.
2. Route default handoff materialization through `QueueDomainService.allocate_ticket(allocation_mode="create_entry")`.
3. Keep the legacy allocator injection only as a test seam.
4. Add a focused unit proof that default flow reaches the queue domain boundary.
5. Document remaining shadow/unmounted wizard work as deferred.

## Non-goals

- no RBAC changes
- no frontend contract changes
- no notification or websocket changes
- no broad allocator cleanup
