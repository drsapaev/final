# W2D API Reference Departments Services Verification

## Summary

This was a bounded docs-vs-code verification pass for `docs/API_REFERENCE.md`.

The goal was not to fully re-document the whole operational catalog. The goal
was to correct high-confidence drift in the adjacent `Departments` and
`Services` sections while keeping the slice docs-only.

## Findings

### Departments section was still advertising CRUD that is not in the published contract

- the doc still advertised:
  - `GET /departments/`
  - `POST /departments/`
  - `PUT /departments/{id}`
- current published OpenAPI only exposes:
  - `GET /api/v1/departments`
  - `GET /api/v1/departments/active`
  - `GET /api/v1/departments/{department_id}`
- the mounted owner in `backend/app/api/v1/endpoints/departments.py` matches
  that read-only shape

### Departments access notes are more specific than the old section implied

- all currently published department routes are authenticated
- both list-style department routes expose the optional `active_only` query
  flag in `backend/openapi.json`
- the old section did not distinguish between the general list route and the
  convenience `active` route at all

### Services section was still framed around a removed narrow route

- the doc still advertised:
  - `GET /services/`
  - `GET /services/department/{dept_id}`
- the current published OpenAPI exposes a broader modern surface instead:
  - catalog CRUD under `/api/v1/services` and `/api/v1/services/{service_id}`
  - category management under `/api/v1/services/categories*`
  - helper routes under:
    - `/api/v1/services/code-mappings`
    - `/api/v1/services/queue-groups`
    - `/api/v1/services/resolve`
    - `/api/v1/services/admin/doctors`

### Services access notes are looser than the old docs implied

- the generated OpenAPI currently publishes the reviewed services routes
  without a `security` block
- the honest docs move was to call that out and avoid inventing stricter role
  claims that are not expressed in the current published contract

## What changed

- updated the `Departments` section in `docs/API_REFERENCE.md` to a curated
  read-only lookup map
- removed the stale `POST /departments/` and `PUT /departments/{id}` claims
- updated the `Services` section in `docs/API_REFERENCE.md` to the current
  catalog/category/helper route shape
- removed the stale `/services/department/{dept_id}` claim
- added a conservative note that the current published services surface has no
  OpenAPI security block

## Evidence used

- `backend/openapi.json`
- `backend/app/api/v1/endpoints/departments.py`
- `backend/app/api/v1/endpoints/services.py`

## Recommended next step

Continue the broader `API_REFERENCE.md` verification track with another bounded
slice rather than a full rewrite.

Good next candidates:

- `Doctors`
- `Appointments`
