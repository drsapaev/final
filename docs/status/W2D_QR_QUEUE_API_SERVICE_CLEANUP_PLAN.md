# W2D qr_queue_api_service cleanup plan

Date: 2026-03-11
Mode: bounded cleanup

## Scope

Remove only:

- `backend/app/services/qr_queue_api_service.py`

## Why this candidate is in scope

Current review confirms:

- mounted QR runtime already lives in `backend/app/api/v1/endpoints/qr_queue.py`
- `backend/app/api/v1/api.py` includes the endpoint router, not this service-side mirror
- no live source imports of `qr_queue_api_service.py` remain under `backend/app` or
  `backend/tests`

## What remains out of scope

- `backend/app/api/v1/endpoints/qr_queue.py`
- `backend/app/services/qr_queue_service.py`
- QR queue behavior, token flow, or allocator logic
- QR characterization or integration tests
