# Docs API Service Cleanup

## Why this file was removable

`backend/app/services/docs_api_service.py` was a duplicate service-side mirror of the mounted router in `backend/app/api/v1/endpoints/docs.py`.

The actual route registration in `backend/app/api/v1/api.py` includes:

- `docs.router` with prefix `/docs`

No live source imports of `docs_api_service.py` were found in `backend/app` or `backend/tests`.

## Why this was safe

- mounted runtime ownership already lived in the endpoint module
- the removed file did not own unique runtime behavior
- no service-boundary test was still tied to this file

## Result

The duplicate/unmounted mirror was removed without changing mounted documentation behavior.
