# Wave 2C Confirmation Next Execution Unit V2

Date: 2026-03-07
Mode: analysis-first, docs-only

## Recommended Next Step

`confirmation reuse-existing-entry change`

## Why This Is The Right Next Unit

The contract clarification is now sufficient to reject the current
duplicate-creating behavior as the target design.

The next execution unit should therefore be a narrow behavior-change slice that:

- checks for an existing active queue row for the same canonical queue claim
- reuses that row instead of allocating a second one
- fails explicitly when ownership is ambiguous
- leaves allocator-family migration for later

## Why Not Boundary Migration Yet

Direct migration to `QueueDomainService.allocate_ticket()` would move plumbing
without first resolving the actual domain drift.

That would preserve the wrong behavior behind a cleaner boundary.

## Why Not Defer Entirely

The conflict is now clarified enough to define a narrow follow-up slice.

The blocker is no longer "insufficient understanding". The blocker is "runtime
behavior needs a deliberate domain correction before migration".

## Suggested Scope For The Next Unit

- public confirmation flow in `visit_confirmation_service.py`
- registrar confirmation bridge only if its behavior is intentionally aligned in
  the same slice, otherwise defer it explicitly
- characterization updates proving:
  - existing active row is reused
  - second active row is no longer created
  - ambiguous duplicate ownership returns an explicit conflict path

## Status

`SAFE_NEXT_STEP_IDENTIFIED`
