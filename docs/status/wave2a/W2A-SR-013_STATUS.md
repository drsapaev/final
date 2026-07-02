# W2A-SR-013 Status

Status: `replacement-pr-opened`
Date: 2026-05-04
Replacement for: PR #59

## Applied Shape

- `create_visit` delegates to `VisitsApiService.create_visit(...)`.
- `add_service` delegates to `VisitsApiService.add_service(...)`.
- `VisitsApiService.create_visit` preserves the previous CRUD-path `source` fallback.
- Queue-coupled handlers in `visits.py` are intentionally unchanged.

## Proof Added

- Router delegation tests for both safe write endpoints.
- Architecture guard for completed safe write handlers only.
- Narrow contract file documenting scope and stop conditions.

## Validation

- See replacement PR checks for current results.
