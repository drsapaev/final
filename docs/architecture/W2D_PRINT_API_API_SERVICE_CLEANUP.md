# W2D print_api_api_service cleanup

## What changed

Removed:

- `backend/app/services/print_api_api_service.py`

## Why this was safe

The file was a duplicate router-style mirror under `services/`, not the mounted
runtime owner.

The live runtime already lives in:

- `backend/app/api/v1/endpoints/print_api.py`
- `backend/app/api/v1/endpoints/print.py`

`backend/app/api/v1/api.py` includes those endpoint routers directly.

## What did not change

This slice did not change:

- print route registration
- ticket/receipt/prescription/certificate printing behavior
- printer status behavior
- any print-service implementation

## Practical effect

One more duplicate service-side router artifact is removed without affecting the
active print API surface.
