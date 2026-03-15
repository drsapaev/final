# Wave 2C Force Majeure Readiness

Date: 2026-03-09
Mode: characterization / migration-prep
Decision: `BLOCKED_BY_POLICY_OVERRIDE_COMPLEXITY`

## Why This Is Blocked

- transfer owns its own next-number allocator
- transfer intentionally overrides fairness via `priority=2`
- transfer resets `queue_time`
- transfer bypasses canonical duplicate handling on tomorrow queue
- cancel flow is payment/refund coupled

## What This Means

This family is not ready for direct boundary migration or narrow seam extraction
yet.

The next safe step is contract clarification for the force-majeure transfer
domain:

- should duplicate prevention apply on tomorrow queue
- should `queue_time` be preserved or intentionally reset
- should transferred rows keep explicit priority override
- should transfer remain a separate domain outside ordinary queue allocation
