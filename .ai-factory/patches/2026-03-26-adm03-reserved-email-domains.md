# ADM-03 Reserved Email Domains Fix

## Problem

Admin user create/update rejected reserved test domains such as `user@test.local` even in local/staging flows.

## Root Cause

`backend/app/schemas/user_management.py` used `EmailStr` for admin user email fields.
`EmailStr` delegates to `email-validator`, which rejects reserved/special-use domains like `.test.local`.

## Solution

- Replaced `EmailStr` with a custom validator on `UserCreateRequest` and `UserUpdateRequest`.
- Kept syntax validation through `email-validator`.
- Added a non-production fallback that allows reserved test domains such as `.test.local` while still rejecting malformed emails.
- Logged acceptance of reserved domains with `[FIX:ADM-03]`.

## Prevention

- Added unit coverage for:
  - reserved test domain acceptance
  - update-path normalization
  - invalid localhost-style email rejection
- Added integration coverage for real admin user create via `/api/v1/users/users`.

## Tags

`admin`, `validation`, `email`, `reserved-domains`, `p2`
