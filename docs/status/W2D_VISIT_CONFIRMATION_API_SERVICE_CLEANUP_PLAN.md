# W2D visit_confirmation_api_service cleanup plan

Date: 2026-03-11
Mode: bounded cleanup

## In scope

- `backend/app/services/visit_confirmation_api_service.py`
- cleanup status/architecture docs

## Why this file is a candidate

The file duplicates the mounted confirmation router behavior that already lives
in:

- `backend/app/api/v1/endpoints/visit_confirmation.py`
- `backend/app/services/visit_confirmation_service.py`

Current repo evidence shows:

- no confirmed in-repo imports of `visit_confirmation_api_service`
- no direct backend test dependency
- no route registration through this file

## Why this is the narrowest safe cleanup

This is a support-only duplicate module cleanup, not a confirmation-domain
refactor.

The slice intentionally does not:

- change mounted confirmation endpoints
- change confirmation service behavior
- change queue allocation/confirmation semantics

## Validation plan

- OpenAPI contract check
- full backend suite to catch any hidden import/bootstrap dependency
