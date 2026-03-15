# W2D API Reference Status Codes Roles Verification Status

Status: completed

What changed:

- the `HTTP Status Codes` section in `docs/API_REFERENCE.md` now reflects
  common response patterns in this repo instead of a context-free generic table
- repo-specific notes for `204`, `202`, and the prevalence of `422` were added
- the `Roles & Permissions` section is now a role glossary instead of an
  overconfident access matrix
- RBAC caveats for superuser bypass, `Receptionist` normalization, and
  doctor-adjacent specialty roles were added

Validation:

- `pytest tests/test_openapi_contract.py -q` -> `14 passed`
- `python test_role_routing.py` -> `19 passed`
- status, role, and RBAC claims were checked against:
  - `backend/openapi.json`
  - `backend/app/core/security.py`
  - `backend/tests/integration/test_rbac_matrix.py`
  - `backend/test_role_routing.py`

Result:

- the touched footer sections no longer pretend to be a universal policy matrix
- the reviewed sections now better match current generated contracts and RBAC
  evidence while staying concise
