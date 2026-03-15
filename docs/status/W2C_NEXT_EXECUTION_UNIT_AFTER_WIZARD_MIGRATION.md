# Wave 2C Next Execution Unit After Wizard Migration

Date: 2026-03-09

## Decision

Recommended next execution unit: `broader registrar family follow-up`

## Why This Step

The mounted wizard-family and mounted registrar batch-only family are now both
migrated to the compatibility boundary for their create branches.

The next highest-signal allocator work is no longer another wizard slice, but a
broader registrar-family review/execution pass that can separate:

- remaining wizard/cart orchestration
- still-deferred registrar branches
- queue ownership that is not yet migrated through the boundary

## Not Chosen

- `qr_queue direct SQL characterization/migration-prep`
  Still higher risk and better handled after registrar-family narrowing.

- `force_majeure characterization`
  Remains isolated and high-risk, but is not the cleanest next step while
  registrar-family still has deferred branches.

- `OnlineDay legacy isolation review`
  Still deferred to the legacy track.

- `defer pending human decision`
  Not needed; the next registrar-family follow-up slice is already clear.
