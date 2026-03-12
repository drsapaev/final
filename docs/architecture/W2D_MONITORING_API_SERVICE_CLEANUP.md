# Monitoring API Service Cleanup

## Why this file was removable

`backend/app/services/monitoring_api_service.py` had no live source imports and no mounted runtime owner.

The endpoint counterpart `backend/app/api/v1/endpoints/monitoring.py` also is not currently mounted from `backend/app/api/v1/api.py`, which means the service-side mirror was doubly inactive:

- not imported by live code
- not part of the mounted API surface

## Why this was still kept narrow

This slice removes only the service-side duplicate file.

It does **not** clean up the endpoint-side `monitoring.py` artifact yet. That keeps the blast radius small and preserves a follow-up review step if we want to clean dead endpoint artifacts later.

## Result

The duplicate/unmounted service-side monitoring mirror was removed without changing mounted runtime behavior.
