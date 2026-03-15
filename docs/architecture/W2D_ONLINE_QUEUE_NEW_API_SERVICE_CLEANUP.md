# W2D online_queue_new_api_service cleanup

## What changed

Removed:

- `backend/app/services/online_queue_new_api_service.py`

## Why this was safe

The file was a duplicate/unmounted compatibility module rather than a mounted
runtime owner.

The active runtime paths already live elsewhere:

- mounted endpoint module:
  `backend/app/api/v1/endpoints/online_queue_new.py`
- queue-domain and service owners:
  `queue_domain_service.py`, `queue_service.py`, `online_queue_new_service.py`

## What did not change

This slice did not change:

- route registration
- QR token generation
- queue join behavior
- queue opening behavior
- allocator logic

## Practical effect

One more duplicate queue artifact is removed without changing any live queue
surface.

## Test-gate alignment

One stale service-boundary test still referenced the removed duplicate file.
That gate was updated to stop asserting on a module that no longer belongs to
the runtime or cleanup target set.
