# W2D API Reference Status Codes Roles Verification

## Summary

This was a bounded docs-vs-code verification pass for `docs/API_REFERENCE.md`.

The goal was not to turn the footer into a formal API policy manual. The goal
was to correct high-confidence drift in the `HTTP Status Codes` and
`Roles & Permissions` sections while keeping the slice docs-only.

## Findings

### HTTP status table was too generic and missed current repo-specific patterns

- the old table was a short generic list:
  - `200`
  - `201`
  - `400`
  - `401`
  - `403`
  - `404`
  - `422`
  - `500`
- current generated OpenAPI is much more skewed than that table suggested:
  - `200` is the dominant success code
  - `422` is the most common non-2xx generated response
  - `201`, `204`, and a small amount of `202` also exist
- some runtime/domain responses such as `403` and stateful `409` paths are
  better evidenced by the security layer and tests than by the generated
  OpenAPI alone

### Roles table was too narrow and too absolute

- the old section claimed:
  - `Admin | Full access`
  - `Doctor | Patients, Visits, EMR`
  - `Registrar | Patients, Appointments`
  - `Cashier | Payments only`
  - `Patient | Own appointments/results`
- those claims were too simplistic for the current codebase
- current live security and tests show a broader and more nuanced role story:
  - `Lab` is a live role in code
  - `Cashier` has some patient-adjacent access on selected routes
  - `is_superuser=True` bypasses role checks
  - `Receptionist` is normalized to `Registrar`
  - specialty roles such as `cardio`, `derma`, and `dentist` still exist in
    code as compatibility/domain-specific doctor-adjacent roles

### RBAC evidence is route-specific, not one global matrix

- the deterministic RBAC matrix and wrapper tests currently provide strongest
  evidence for:
  - `Admin`
  - `Registrar`
  - `Doctor`
  - `Cashier`
  - `Patient`
- the honest docs move was to turn the table into a role glossary with caveats,
  not to pretend the project has one tiny universal access matrix

## What changed

- updated the `HTTP Status Codes` section in `docs/API_REFERENCE.md` to a
  curated “common response patterns” block
- added repo-specific notes for `204`, `202`, the dominance of `422`, and the
  fact that some domain codes are route-specific
- updated the `Roles & Permissions` section to a role glossary instead of an
  absolute access matrix
- added RBAC caveats for superuser bypass, `Receptionist` normalization, and
  doctor-adjacent specialty roles

## Evidence used

- `backend/openapi.json`
- `backend/app/core/security.py`
- `backend/tests/integration/test_rbac_matrix.py`
- `backend/test_role_routing.py`

## Recommended next step

Continue the broader `API_REFERENCE.md` verification track with another bounded
slice rather than a full rewrite.

Good next candidates:

- `New Modules`
- `Links`
