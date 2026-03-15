# W2D Backend Entrypoint Startup Semantics Plan Gate

## Summary

This is a plan-gated review for the remaining behavior-bearing startup tails in:

- `ops/backend.entrypoint.sh`

This is no longer a low-risk path/config cleanup slice.

The fallback-path drift has already been resolved. What remains now is startup
policy:

- schema bootstrap via `Base.metadata.create_all(...)`
- automatic admin bootstrap via `ENSURE_ADMIN`

Those behaviors should not be changed silently.

## Verified Findings

### The entrypoint still performs metadata-based schema bootstrap before app startup

`ops/backend.entrypoint.sh` currently runs:

- `Base.metadata.create_all(bind=engine)`

before starting Uvicorn.

That behavior is real and repo-backed.

At the same time, current production-facing docs and migration tooling still
frame schema changes around:

- `alembic upgrade head`

Evidence:

- `ops/backend.entrypoint.sh`
- `backend/alembic/env.py`
- `backend/SETUP_PRODUCTION.md`
- `backend/PRODUCTION_SETUP_SUMMARY.md`

### `create_all` is not the same thing as migration-first startup

The current entrypoint behavior may be acceptable as a convenience bootstrap
for local or loosely managed environments, but it is not equivalent to a
reviewed migration-first deployment policy.

Risks of treating it as equivalent:

- missing migration semantics can be obscured by “table exists now” behavior
- operators may believe compose startup fully replaces explicit Alembic steps
- docs can drift into implying a stronger deployment guarantee than the repo
  actually proves

### Automatic admin bootstrap is active by default

`ops/backend.entrypoint.sh` still defaults:

- `ENSURE_ADMIN=1`

and then runs:

- `python app/scripts/ensure_admin.py`

unless disabled.

This is not just “admin creation if missing”.

`backend/app/scripts/ensure_admin.py` can:

- create an admin if none exists
- update an existing user matched by username
- update an existing user matched by email
- normalize role to `Admin`
- reactivate an inactive user
- optionally reset the password if `ADMIN_RESET_PASSWORD` is set

### Current compose/docs story still needs explicit operator framing

The current compose path already carries local/dev-oriented defaults such as:

- `ENV=dev`
- `CORS_ALLOW_ALL=1`
- `ADMIN_PASSWORD=admin`

Combined with default `ENSURE_ADMIN=1`, this means the compose/entrypoint path
is still a convenience bootstrap surface unless operators review it explicitly.

## Decision Buckets

### Option A: Keep the current startup behavior, but frame it honestly

Meaning:

- keep `create_all`
- keep default admin bootstrap
- explicitly document that this path is convenience-first, not migration-first

When this is acceptable:

- local/dev or tightly controlled internal environments
- operator-owned deployments where this behavior is deliberate

### Option B: Keep admin bootstrap, but gate schema bootstrap harder

Meaning:

- stop automatic `create_all`
- require migrations first
- optionally leave admin bootstrap as a separate reviewed convenience

When this is acceptable:

- environments that want stronger migration discipline without fully removing
  bootstrap helpers

### Option C: Move the whole entrypoint to an explicit operator-first startup model

Meaning:

- no automatic `create_all`
- no automatic admin bootstrap unless explicitly enabled
- compose/docs switch to a more explicit reviewed deployment posture

When this is acceptable:

- environments aiming for clearer production semantics and fewer hidden
  side effects

## Current Gate Decision

No runtime decision was taken in this slice.

What this slice did instead:

- recorded the remaining tails as behavior-bearing startup semantics
- tightened neighboring docs so they do not hide those behaviors
- left the actual startup policy unchanged

## Recommended Next Step

Run a human-reviewed startup-semantics decision pass focused on:

1. whether `Base.metadata.create_all(...)` should remain in the entrypoint
2. whether `ENSURE_ADMIN` should default to `1`
3. whether compose-facing docs should continue to describe the current path as
   convenience bootstrap or be moved toward a stricter operator-first model
