# W2D Next Execution Unit After Queues Stats Prep

## Decision

`B) legacy-vs-SSOT comparison harness`

## Why This Is The Safest Next Step

- `queues.stats` is a live mounted surface with a confirmed UI consumer.
- The live consumer only needs a small subset of fields, but the route still
  exposes the full legacy contract.
- We still do not have evidence-backed parity for:
  - department/day to SSOT queue mapping
  - `last_ticket` equivalence
  - compatibility handling for `is_open`
  - compatibility handling for `start_number`

A comparison harness gives us those answers without switching runtime behavior.

## Why Not `A) SSOT read-model skeleton only`

An isolated skeleton is useful, but by itself it does not prove parity against the
live legacy endpoint. The higher-value next step is the harness that shows whether
the candidate model is actually safe.

## Why Not `C) narrow queues.stats replacement slice`

That would be too early because:

- there is still no validated department/day aggregate mapping
- `start_number` and `is_open` still need compatibility handling
- `last_ticket` equivalence is not yet evidenced

## Why Not `D) human review needed before code step`

This slice already reduced the unknowns enough to support a very small code step:
read-only comparison and parity capture.

## Narrow Next-Step Shape

The next step should stay read-only and non-invasive:

- introduce a candidate SSOT `queues.stats` projection or harness
- compare it against legacy `queues.stats`
- capture field-level parity / mismatch evidence
- do not switch the mounted endpoint yet
