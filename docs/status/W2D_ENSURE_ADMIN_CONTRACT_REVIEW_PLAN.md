# W2D Ensure Admin Contract Review Plan

Status: completed
Branch: `codex/startup-operator-first-hardening`

## Summary

After startup hardening, `C:/final/backend/app/scripts/ensure_admin.py`
remains the main explicit operator mutation helper.

This slice reviews and narrows that helper without turning it into a broad
auth/bootstrap refactor.

## Current Verified Behavior

`ensure_admin.py` currently:

- creates an admin if no matching user exists
- updates an existing user matched by username
- updates an existing user matched by email
- can change:
  - `username`
  - `email`
  - `full_name`
  - `role`
  - `is_active`
  - `hashed_password` when `ADMIN_RESET_PASSWORD=1`

Current issue:

- even though startup is now explicit, the helper still mutates existing users
  by default once it is invoked

## Exact Minimal Change In This Slice

1. Keep create-if-missing behavior available by default.
2. Make mutation of an existing user explicit opt-in via a dedicated env flag.
3. Keep password reset as an explicit sub-action, not an implicit side effect.
4. Document the updated operator contract in the nearest startup docs.

## Out Of Scope

- no auth model redesign
- no role-system redesign
- no new bootstrap service/framework
- no CLI wrapper redesign
- no broad user-management workflow rewrite

## Validation Plan

- add narrow unit coverage for `ensure_admin.py`
- run those targeted tests
- run `cd C:\final\backend && pytest tests/test_openapi_contract.py -q`
