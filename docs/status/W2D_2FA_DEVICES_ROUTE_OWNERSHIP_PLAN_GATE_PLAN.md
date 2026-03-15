# W2D 2FA Devices Route Ownership Plan Gate Plan

Scope:

- audit the mixed `/api/v1/2fa/devices*` ownership tail after protected
  duplicate cleanup was exhausted
- capture router-order runtime ownership, published contract shape, and
  frontend expectations without mutating live 2FA behavior
- turn the tail into an explicit plan-gate instead of a hidden follow-up

Evidence targets:

- mount order in `backend/app/api/v1/api.py`
- published routes in `backend/openapi.json`
- current runtime contract proof in
  `backend/tests/integration/test_two_factor_devices_endpoint_contract.py`
- frontend expectations in:
  - `frontend/src/components/TwoFactorSettings.jsx`
  - `frontend/src/components/security/TwoFactorManager.jsx`

Expected outcome:

- no silent auth/2FA cleanup or router reordering
- explicit proof that runtime first-match and published OpenAPI diverge for the
  shadowed `GET/DELETE /api/v1/2fa/devices*` operations
- next execution unit moved from generic ownership audit to a dedicated
  human-reviewed migration/parity plan
