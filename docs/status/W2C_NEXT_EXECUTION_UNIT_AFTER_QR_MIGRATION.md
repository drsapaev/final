# Wave 2C Next Execution Unit After QR Migration

Date: 2026-03-09
Mode: post-QR boundary migration
Status: `force_majeure characterization`

## Decision

The next execution unit should be:

- `force_majeure characterization`

## Why This Is The Next Step

- registrar allocator track is effectively complete
- mounted QR full-update family is now migrated to the compatibility boundary
- the next remaining production allocator family with distinct numbering and
  lifecycle semantics is `force_majeure`

## Not Chosen

- `OnlineDay` legacy isolation review
  - still valid later, but `force_majeure` is the nearer non-legacy allocator
    family
- broader QR follow-up
  - not the best next allocator-migration unit because current QR runtime
    blocker for boundary adoption is already closed
- `defer pending human decision`
  - not needed because the next family is clear
