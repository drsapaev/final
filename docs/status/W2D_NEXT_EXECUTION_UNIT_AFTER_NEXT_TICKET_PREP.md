# W2D Next Execution Unit After next_ticket Prep

## Chosen next step

`B) next_ticket contract clarification pass`

## Why this is the safest next step

The code evidence is already sufficient to describe current runtime behavior.

The remaining risk is not implementation uncertainty, but target-meaning uncertainty:

- Is `next_ticket` still a needed operational action?
- If yes, should it remain a department/day counter issuer?
- If no, should it be retired instead of replaced?

Those questions should be resolved before characterization-heavy replacement work or code prep.

## Why broader replacement is not chosen yet

Broader replacement is not justified yet because:

- no clean SSOT target exists
- no confirmed direct in-repo consumer exists
- current route still indirectly affects board/stats state

That combination makes contract clarification the smallest safe deterministic next slice.
