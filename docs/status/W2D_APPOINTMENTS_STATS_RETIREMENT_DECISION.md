# W2D appointments.stats retirement decision

## Verdict

`READY_FOR_RETIREMENT_PREP`

## Why

Current evidence shows:

- the route is still mounted and public
- it is read-only
- it duplicates the same legacy `load_stats(...)` contract as `queues.stats()`
- no confirmed in-repo live runtime consumer was found

That is strong enough to justify retirement/deprecation preparation, but not
strong enough to justify immediate removal.

## Chosen direction

- do not modernize `appointments.stats()` into a new SSOT read-model first
- do not remove it abruptly
- treat it as a duplicate legacy compatibility surface that should move toward
  retirement unless real consumers are proven

## Rejected directions

### Keep unchanged indefinitely

Rejected because it preserves duplicate legacy surface without clear value.

### Replace first, retire later

Rejected because it would spend engineering effort on a surface with no
confirmed active consumer.

### Immediate retirement

Rejected because mounted public exposure still deserves a narrow deprecation-prep
step first.
