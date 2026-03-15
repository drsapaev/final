# W2D print_templates_api_service cleanup

## What changed

Removed:

- `backend/app/services/print_templates_api_service.py`

## Why this was safe

The file was a duplicate service-side router mirror, not the mounted runtime
owner.

The live print-template runtime already lives in:

- `backend/app/api/v1/endpoints/print_templates.py`

`backend/app/api/v1/api.py` includes that endpoint router directly.

## What did not change

This slice did not change:

- print template route registration
- template CRUD behavior
- template preview/upload behavior
- print config persistence behavior

## Practical effect

One more duplicate print-related router artifact is removed without affecting
the active print-template API surface.
