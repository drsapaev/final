## Chosen Next Step

`D) human/ops review still needed`

## Why this is the safest next move

The characterization pass already proved real runtime drift.

This usage-confirmation pass then narrowed the remaining blocker:

- not a missing code trace
- not a missing test
- but unresolved operational exposure

We now know:

- the legacy routes are not confirmed current in-repo UI paths
- the operational workflow is still strongly implied by docs and code comments
- the routes remain mounted and admin-visible

That is exactly the situation where a narrow fix can still create avoidable operational surprise.

## Why a narrow fix is not chosen yet

A narrow fix would be technically possible now, but it would still change:

- state-source behavior
- response semantics
- or broadcast behavior

without confirming whether any operators or external clients still depend on the current legacy shape.

## What the human/ops review should confirm

1. Whether `POST /api/v1/appointments/open-day` is still used outside the repo.
2. Whether `POST /api/v1/appointments/close` is still used outside the repo.
3. Whether any operator workflow still depends on the current asymmetric behavior.
4. Whether the old routes can be treated as compatibility-only surfaces before a fix.
