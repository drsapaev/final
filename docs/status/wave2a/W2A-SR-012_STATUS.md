# W2A-SR-012 Status

Status: `replacement-pr-opened`
Date: 2026-05-04
Replacement for: PR #58

## Applied Shape

- `list_visits` delegates to `VisitsApiService.list_visits(...)`.
- `get_visit` delegates to `VisitsApiService.get_visit(...)`.
- Write and queue-coupled handlers in `visits.py` are intentionally unchanged.

## Proof Added

- Router delegation tests for both read-only endpoints.
- Architecture guard for completed read-only handlers only.
- Narrow contract file documenting scope and stop conditions.

## Validation

- See replacement PR checks for current results.
