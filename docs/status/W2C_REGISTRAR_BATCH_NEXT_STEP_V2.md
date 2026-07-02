# Wave 2C Registrar Batch Next Step V2

Date: 2026-05-05
Mode: docs-only replacement for stale PR #78

## Recommended Next Runtime Slice

If this area continues, the smallest useful runtime slice is not a broad allocator rewrite. It is a targeted duplicate-boundary proof for the mounted registrar batch endpoint.

## Proposed Slice

1. Add or update focused tests for the mounted batch endpoint.
2. Prove `specialist_id` is treated as `doctors.id`.
3. Prove same-doctor multi-service requests produce one queue row in the first service `queue_tag` bucket.
4. Prove duplicate behavior for the selected active statuses.
5. Update contract docs only after tests establish the runtime truth.

## Do Not Include

- frontend panel refactors
- queue numbering redesign
- cashier/payment behavior
- Telegram or realtime notification behavior
- migration changes

## Stop Condition

Stop the runtime slice if reviewers cannot agree whether the product wants doctor-level grouping or service-level queue entries. That is a behavior decision, not a cleanup detail.
