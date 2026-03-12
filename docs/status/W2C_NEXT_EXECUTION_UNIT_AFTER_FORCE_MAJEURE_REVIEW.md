# Wave 2C Next Execution Unit After Force Majeure Review

Date: 2026-03-09
Mode: post-contract-review
Status: `move to OnlineDay legacy review`

## Decision

The next execution unit should be:

- `move to OnlineDay legacy review`

## Why

- force majeure is now classified as an exceptional-domain island
- it should be removed from the ordinary boundary-migration track
- the main remaining allocator family in the current track is the legacy
  `OnlineDay` surface

## Not Chosen

- `narrow force_majeure behavior-correction slice`
  - possible later inside the exceptional-domain track, but not the best next
    boundary-track step
- `narrow force_majeure seam extraction`
  - seams are not the blocker; policy ownership is
- `isolate as exceptional-domain and defer from boundary track`
  - this pass already establishes that decision
