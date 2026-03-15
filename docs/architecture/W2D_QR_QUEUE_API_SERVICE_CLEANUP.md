# W2D qr_queue_api_service cleanup

## What changed

Removed:

- `backend/app/services/qr_queue_api_service.py`

## Why this was safe

The file was a duplicate service-side router mirror, not the mounted runtime
owner.

The live QR runtime already lives in:

- `backend/app/api/v1/endpoints/qr_queue.py`
- `backend/app/services/qr_queue_service.py`

`backend/app/api/v1/api.py` includes the endpoint router directly.

## What did not change

This slice did not change:

- `/queue` QR route registration
- QR token generation behavior
- join session behavior
- QR characterization or integration behavior

## Practical effect

One more duplicate QR router artifact is removed without affecting the active QR
API surface.
