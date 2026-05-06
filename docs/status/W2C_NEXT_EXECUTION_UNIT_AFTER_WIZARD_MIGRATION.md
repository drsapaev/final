# W2C Next Execution Unit After Wizard Migration

Date: 2026-05-06

## Completed prerequisite

Mounted same-day wizard create-branch handoffs now use `QueueDomainService.allocate_ticket(allocation_mode="create_entry")` by default.

## Next smallest safe unit

Review remaining registrar wizard shadow/unmounted paths and classify each as:

- already covered by the mounted service boundary
- compatibility-only and safe to document
- still requiring a narrow runtime migration

## Validation target

A future slice should include a targeted test or smoke proof only for the route/path it changes. Do not broaden into allocator cleanup unless the compatibility review proves the path is dead or duplicate.
