# W2D board_state contract decision

## Chosen strategy

Chosen strategy:

- introduce a new adapter-backed endpoint/contract and migrate UI separately

This is the safest bounded path for production.

## Why this option was chosen

- current `/board/state` is a real legacy OnlineDay route with a queue-counter
  contract
- the live UI expects a display-metadata contract instead
- changing `/board/state` in place would mutate both request meaning and
  response meaning at the same time
- a new endpoint keeps rollback simple and preserves unknown legacy consumers

## Rejected alternatives

### Rejected as final strategy: keep legacy route only

Reason:

- safe as a pause, but it does not resolve the actual UI/backend contract
  mismatch

### Rejected as default migration path: in-place replacement of `/board/state`

Reason:

- highest compatibility risk
- route meaning would change under existing consumers
- backward compatibility cost is too high for the expected gain

### Not chosen as the primary framing: permanent split without a new adapter contract

Reason:

- long-term split may still end up being the right steady state
- but the immediate next step should still be a concrete adapter-backed contract
  preparation, not indefinite coexistence without a defined replacement surface

## Can code work continue after this decision?

Yes.

The next code work can proceed safely, but it should target:

- preparation of a new adapter-backed endpoint contract

It should not target:

- in-place mutation of the mounted legacy `/board/state` route

## Final safety verdict

The safest strategy is:

- new endpoint first
- staged frontend migration second
- legacy route retirement or long-term compatibility decision later
