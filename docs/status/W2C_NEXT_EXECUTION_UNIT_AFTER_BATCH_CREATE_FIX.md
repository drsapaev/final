# Wave 2C Next Execution Unit After Batch Create Fix


Date: 2026-05-06
Current-main replacement for stale PR #93 after parent #92 was superseded by merged PR #271.
## Decision

`registrar allocator track effectively complete -> move to qr_queue direct SQL family`

## Why

After this slice:

- confirmation family is boundary-covered
- mounted registrar batch-only family is boundary-covered
- mounted wizard family is boundary-covered
- mounted `/registrar/batch` create-action no longer breaks on a stale import and
  now uses the supported queue boundary path

That means no production-relevant mounted registrar allocator path remains as an
active migration blocker.

## Not Recommended Next

- `one more narrow registrar follow-up`
  not justified by current production runtime evidence
- `human review needed`
  not required for registrar allocator ownership at this point
- `defer mounted batch create-action as separate legacy island`
  no longer justified because the path is now live and boundary-covered

## Recommended Track Shift

The next allocator family with the highest remaining architectural risk is:

- `qr_queue` direct SQL characterization / migration-prep
