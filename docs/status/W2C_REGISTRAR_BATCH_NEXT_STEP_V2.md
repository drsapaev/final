# Wave 2C Registrar Batch Next Step V2

Date: 2026-03-08
Status: `narrow behavior-correction slice for diagnostics duplicate gate`

## Recommended Next Step

Implement a narrow registrar batch-only behavior-correction slice that updates
the duplicate gate to reuse an existing active row when the existing row is in
`diagnostics`.

## Why This Is The Next Safe Step

- the contract ambiguity is now clarified
- `diagnostics` mismatch is already characterization-tested
- the fix can stay inside the mounted batch-only flow
- it does not require allocator redesign
- it does not require QR, `OnlineDay`, or force-majeure migration

## What The Slice Should Preserve

- specialist-level batch claim
- current numbering algorithm
- current `queue_time` fairness behavior
- source passthrough behavior
- same-specialist multi-service grouping

## What The Slice Should Correct

- stop creating a second active row when an existing `diagnostics` row already
  owns the same patient/specialist/day claim

## Why Other Options Were Not Chosen

### `same-specialist multi-service policy correction`

Not needed. After contract clarification, current grouping matches the chosen
batch-only claim model.

### `seam extraction before migration`

Useful later, but it would preserve a known duplicate-gate drift if done first.

### `human decision required`

No longer necessary for this subfamily. The local contract is now clear enough
for a small correction slice.

## Follow-up After The Correction

If the correction slice passes, the next registrar batch step should be:

- service/seam extraction before boundary migration

not immediate broad registrar migration.
