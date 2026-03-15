# Dermatology Photos Endpoint Cleanup Plan

Scope:
- delete dead endpoint artifact
  `backend/app/api/v1/endpoints/dermatology_photos.py`
- delete detached router duplicate
  `backend/app/services/dermatology_photos_api_service.py`

Evidence:
- `backend/app/api/v1/api.py` does not mount `dermatology_photos.router`
- `backend/openapi.json` does not contain `/api/v1/dermatology/photos/*`
- no confirmed backend, test, frontend, or docs import/reference of the
  endpoint module remains beyond generated analysis artifacts
- no confirmed live import of `dermatology_photos_api_service.py` remains

Why this is safe:
- the endpoint file was not mounted, so deleting it cannot change runtime
  routing
- the duplicate router file under `services/` had no confirmed live imports
- the mounted `derma.py` router remains intact

Out of scope:
- removing `app/models/dermatology_photos.py`
- removing `app/crud/dermatology_photos.py`
- changing the mounted dermatology feature set
