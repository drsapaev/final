# W2D Operator Runbook Command Normalization

## Summary

This slice normalized the explicit operator command story after:

- startup hardening
- `ensure_admin` contract hardening

The goal was not to change behavior again, but to make the same explicit flow
read the same way across the repo.

## Verified Drift Before This Slice

The explicit operator flow was already correct in principle, but commands were
still spread across multiple docs with slightly different assumptions:

- some examples assumed repo-root execution
- some examples assumed `cd ops`
- some examples showed direct backend commands
- some examples described admin bootstrap without one canonical command map

That created low-risk but real operator ambiguity.

## What Changed

### Canonical command map added

A single canonical command map now exists in:

- `C:/final/docs/OPERATOR_STARTUP_COMMANDS.md`

It defines:

- direct backend migration/start commands
- direct admin-bootstrap commands
- compose-based migration/start commands
- explicit existing-user mutation commands using `ADMIN_ALLOW_UPDATE=1`

### Neighboring docs aligned to the same map

The following docs now point to the same command story:

- `C:/final/README.md`
- `C:/final/ops/README.md`
- `C:/final/backend/SETUP_PRODUCTION.md`
- `C:/final/backend/PRODUCTION_SETUP_SUMMARY.md`

## Why This Is Useful

- the operator path is now both explicit and easier to follow
- startup behavior and runbook wording now reinforce each other
- low-risk ambiguity was reduced without reopening startup semantics

## Current Verdict

The bounded operator-first startup lane is now sufficiently complete:

- startup mutation is removed
- explicit helper mutation is gated
- runbook commands are normalized

Further work here is optional, not urgent.
