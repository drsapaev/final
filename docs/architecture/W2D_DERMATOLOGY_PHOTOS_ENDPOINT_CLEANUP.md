# Dermatology Photos Endpoint Cleanup

`backend/app/api/v1/endpoints/dermatology_photos.py` and
`backend/app/services/dermatology_photos_api_service.py` were detached legacy
entrypoint artifacts.

Verified facts:
- `backend/app/api/v1/api.py` did not include `dermatology_photos.router`
- `backend/openapi.json` did not expose the file's expected
  `/api/v1/dermatology/photos/*` routes
- no live source imports of
  `backend/app/api/v1/endpoints/dermatology_photos.py` or
  `backend/app/services/dermatology_photos_api_service.py` were found in
  `backend/app` or `backend/tests`
- `backend/app/services/dermatology_photos_api_service.py` was an extra
  router-style duplicate living under `services/`
- the mounted dermatology surface remains owned by
  `backend/app/api/v1/endpoints/derma.py`
- the underlying model and CRUD files for `dermatology_photos` remain in place
  and were not changed by this cleanup

Cleanup performed:
- removed `backend/app/api/v1/endpoints/dermatology_photos.py`
- removed `backend/app/services/dermatology_photos_api_service.py`

Effect:
- no mounted runtime route was removed
- live `/api/v1/derma/*` ownership remains unchanged
- dead dermatology photo entrypoint residue is reduced without touching models,
  CRUD, or uploads behavior
