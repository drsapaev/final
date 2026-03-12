# Wave 2C QR Contract Compliance Recheck

Date: 2026-03-09
Mode: docs-only readiness recheck

## Verdict

Contract compliance is preserved after QR seam extraction.

## Rechecked Invariants

### Consultation keeps original `queue_time`

Preserved.

- Characterization still documents that the original consultation row keeps the
  pre-existing QR `queue_time`.
- The extracted QR seam only materializes new additional-service rows.

### Additional services create independent entries

Preserved.

- The mounted runtime still creates one independent `OnlineQueueEntry` per
  additional service / target queue.
- The extracted seam did not collapse additional-service fan-out into the
  original consultation row.

### Numbering semantics unchanged

Preserved.

- The QR-local seam still computes the next number with raw SQL
  `MAX(number)+1`.
- No numbering redesign or counter migration happened in this slice.

### Source inheritance unchanged

Preserved.

- Additional-service rows still use `entry.source or "online"`.
- Characterization remains aligned with the observed `source="online"` QR path.

### Same-day QR semantics unchanged

Preserved.

- First-fill and edit-existing additional-service branches still behave as
  same-day QR edits.
- The public `/queue/join/start` and `/queue/join/complete` flows remain
  outside this seam and are unchanged.

### Response shape unchanged

Preserved.

- `full_update_online_entry()` still returns the same mounted response envelope.
- The extracted seam is internal and does not reshape the endpoint response.

## Compliance Notes Against Queue Contracts

### With `W2C_QUEUE_NUMBERING_CONTRACT.md`

Partially aligned for migration-prep only.

- Current QR runtime still does not use the target single-owner allocator.
- Extraction preserved runtime behavior without claiming final contract
  compliance for numbering ownership.

### With `W2C_DUPLICATE_POLICY_CONTRACT.md`

Known partial divergence remains.

- Additional-service create branch still does not run a canonical duplicate gate
  before creating new independent entries.
- This divergence is already characterized and remains unchanged.

### With `W2C_ACTIVE_ENTRY_CONTRACT.md`

Known partial divergence remains.

- `queue_session` reuse still excludes `diagnostics`.
- This was not changed by the QR extraction slice.

## Conclusion

The extraction preserved the already-characterized QR runtime. Remaining issues
are migration blockers only where the current boundary cannot reproduce that
runtime 1:1.
