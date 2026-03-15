# W2D API Reference Status Codes Roles Verification Plan

Scope:

- verify the `HTTP Status Codes` and `Roles & Permissions` sections in
  `docs/API_REFERENCE.md` against current OpenAPI, security code, and RBAC
  tests
- keep the slice docs-only
- avoid turning the pass into a full authorization redesign or policy spec

Evidence targets:

- `backend/openapi.json`
- `backend/app/core/security.py`
- `backend/tests/integration/test_rbac_matrix.py`
- `backend/test_role_routing.py`

Expected outcome:

- generic status table downgraded to current common response patterns
- current RBAC role glossary reflected without pretending to be a full matrix
- superuser and role-normalization caveats documented
- next footer/reference candidates isolated cleanly
