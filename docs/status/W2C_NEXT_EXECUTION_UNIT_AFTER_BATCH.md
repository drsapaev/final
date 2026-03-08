# Wave 2C Next Execution Unit After Batch

Date: 2026-03-08
Status: `broader registrar wizard characterization`

## Recommended Next Step

Run a characterization/review-first pass for broader registrar wizard queue
branches outside the mounted batch-only family.

## Why This Is The Next Step

- mounted confirmation family is migrated
- mounted registrar batch-only family is now migrated
- the next closest deferred family is broader registrar wizard orchestration
- it is still likely safer than jumping directly into `qr_queue.py` direct SQL
  or `OnlineDay`

## Why Other Options Were Not Chosen

### `qr_queue direct SQL characterization/migration-prep`

Still needed, but it remains the highest-risk live allocator family.

### `force_majeure characterization`

Valid later, but it is more exceptional and less central than the remaining
registrar family surface.

### `legacy OnlineDay isolation review`

Still needed, but it is a separate legacy track rather than the next adjacent
queue-family migration.

### `defer pending human decision`

Not necessary yet. The next family is already identifiable.
