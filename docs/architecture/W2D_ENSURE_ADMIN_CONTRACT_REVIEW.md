# W2D Ensure Admin Contract Review

## Summary

This slice hardened the explicit admin-bootstrap helper
`C:/final/backend/app/scripts/ensure_admin.py` without turning it into a broad
auth/bootstrap rewrite.

Goal:

- keep explicit bootstrap available
- keep create-if-missing available
- stop mutating an existing matched user by default

## Verified Problem

After startup hardening, app startup no longer mutates schema or admin state by
default.

However, `ensure_admin.py` still remained overly strong even as an explicit
operator command:

- a matched existing user could be promoted to `Admin`
- reactivated
- renamed
- have profile fields rewritten
- and optionally have password reset

all without a separate “yes, mutate existing user” opt-in.

That meant the explicit helper still had implicit mutation semantics once
invoked.

## What Changed

### New explicit mutation gate

`ensure_admin.py` now reads:

- `ADMIN_ALLOW_UPDATE`

Behavior:

- if no matching user exists:
  - create an admin user
- if a matching user already exists:
  - return a `skipped` result unless `ADMIN_ALLOW_UPDATE=1`
- if `ADMIN_ALLOW_UPDATE=1`:
  - existing-user normalization/promote/reactivate logic may run
- if `ADMIN_RESET_PASSWORD=1`:
  - password reset remains explicit and only applies during an allowed update

### Resulting operator contract

Create-only default:

- `python app/scripts/ensure_admin.py`

Explicit existing-user mutation:

- `ADMIN_ALLOW_UPDATE=1 python app/scripts/ensure_admin.py`

Explicit password reset on existing user:

- `ADMIN_ALLOW_UPDATE=1 ADMIN_RESET_PASSWORD=1 python app/scripts/ensure_admin.py`

## Supporting Updates

Operator-facing hints were aligned in:

- `C:/final/README.md`
- `C:/final/ops/README.md`
- `C:/final/backend/SETUP_PRODUCTION.md`
- `C:/final/backend/PRODUCTION_SETUP_SUMMARY.md`
- `C:/final/backend/.env.example`
- `C:/final/ops/.env.example`
- `C:/final/ops/docker-compose.yml`

## Why This Is Safer

- explicit bootstrap still exists
- local/dev and demo flows still work
- existing-user mutation is no longer the default helper behavior
- operator intent is now visible in env/command form

## Out Of Scope

- no redesign of `ensure_admin.py` into a formal CLI
- no password policy rewrite
- no user-management or RBAC refactor
- no deployment-system rewrite

## Current Verdict

The startup/bootstrap path is now more honestly operator-first:

- startup itself is explicit
- admin helper mutation is also explicit

The next low-risk follow-up is no longer behavior hardening, but command/runbook
normalization around the explicit operator flow.
