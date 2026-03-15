# W2D Legacy Re-entry Options

This document compares the realistic actionable next-track options after the
Postgres pilot guardrail was put in CI.

## Option 1: OnlineDay deprecation continuation

### Expected architectural value

High.

This is still the largest remaining engineering tail with live runtime impact.
Reducing even one more mounted OnlineDay surface keeps shrinking the legacy
island for real.

### Implementation risk

Medium if scoped to a read-only or retirement-prep slice.

### Dependency on blocked tails

Partial.

Write/admin surfaces are blocked, but not every OnlineDay surface is.

### Likely blast radius

Manageable if the slice targets one read-only or deprecation-prep surface only.

### Why it may be the best next slice

- highest remaining architectural leverage among actionable work
- now protected by the new Postgres guardrail
- can continue legacy reduction without touching blocked product/ops semantics

### Why it may not be chosen

If no bounded read-only candidate existed, this track would still be too tied to
blocked operational routes. Current evidence suggests at least two do exist:

- `appointments.stats()`
- `appointments/qrcode`

## Option 2: Support/test-only residue cleanup

### Expected architectural value

Low to medium.

### Implementation risk

Low.

### Dependency on blocked tails

Low.

### Likely blast radius

Small.

### Why it may be the best next slice

It is easy and safe.

### Why it is not the best next slice

It does not reduce a meaningful live legacy runtime surface. The remaining
OnlineDay island would barely shrink.

## Option 3: Docs / architecture consolidation

### Expected architectural value

Low to medium.

### Implementation risk

Low.

### Dependency on blocked tails

None.

### Likely blast radius

Very small.

### Why it may be the best next slice

It would make the accumulated W2D status easier to navigate.

### Why it is not the best next slice

It improves clarity, but not architecture. The project is now better served by
one more real legacy-reduction slice.

## Option 4: Pause-point formalization

### Expected architectural value

Low.

### Implementation risk

Low.

### Dependency on blocked tails

None.

### Likely blast radius

Very small.

### Why it may be the best next slice

It is safe and tidy.

### Why it is not the best next slice

It is largely redundant now. The Postgres alignment review, pilot marker docs,
and CI guardrail docs already act as a strong pause-point record.

## Preferred option

`OnlineDay deprecation continuation` is the strongest next track, provided the
first slice is kept narrow and read-only / retirement-prep oriented.

Within that track, `appointments.stats()` is the strongest candidate because:

- it is mounted
- it is read-only
- it appears to have no confirmed live frontend runtime consumer
- it can reduce the OnlineDay island without touching blocked `open_day`,
  `close_day`, or `next_ticket` semantics

After that slice, `appointments/qrcode` becomes the next strongest bounded
follow-up candidate because it is even smaller, still mounted, and does not own
OnlineDay writes at all.
