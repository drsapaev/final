# RBAC Helper Accepts Legacy Role Lists

**Date:** 2026-03-26 10:03
**Files:** backend/app/core/security.py, backend/app/api/v1/endpoints/specialized_panels.py, backend/tests/unit/test_require_roles_normalization.py, backend/tests/integration/test_specialized_panels_api_endpoints.py
**Severity:** high

## Problem

`GET /api/v1/specialized/dentistry/patients` and `GET /api/v1/specialized/dentistry/visits` were returning `500` with
`'list' object has no attribute 'lower'`.

The failure was occurring in the shared RBAC dependency path when a route passed `require_roles([...])`
instead of varargs.

## Root Cause

`app.core.security.require_roles()` accepted `*roles` but assumed every item was already a string.
When a route used the legacy list form, the tuple of roles contained a single list item and the helper
executed `r.lower()` on that list.

## Solution

- Hardened `require_roles()` to flatten legacy list/tuple/set role collections before lowercasing.
- Added `[FIX:require_roles]` debug logging for normalized inputs.
- Canonicalized the specialized panel route dependencies to `require_roles("Admin", "Doctor")`.
- Added regression coverage for both the normalization helper and the live specialized panel endpoints.

## Prevention

- Shared dependency factories should tolerate the legacy call styles already present in the codebase.
- When a helper is designed for varargs, normalize at the boundary instead of assuming every argument is a scalar.
- Add endpoint-level regression coverage when a route depends on a shared auth helper.

## Tags

`#rbac` `#fastapi` `#security` `#dependencies` `#regression`
