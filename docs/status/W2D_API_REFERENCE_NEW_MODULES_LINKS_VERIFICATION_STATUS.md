# W2D API Reference New Modules Links Verification Status

Status: completed

What changed:

- the `New Modules` footer in `docs/API_REFERENCE.md` was reframed from a stale
  versioned block into a curated pointer map for current cardio, dental,
  messaging, and monitoring families
- non-published routes such as `/cardio/ecg/upload`,
  `/cardio/ecg/{id}/interpret`, `/dental/odontogram*`, and `/messages/audio`
  were removed from the curated reference
- the `Links` footer now distinguishes canonical generated docs
  (`/docs`, `/redoc`, `/openapi.json`) from custom `/api/v1/docs/*` helpers
- the placeholder websocket host was replaced with current mounted-family
  guidance

Validation:

- `pytest tests/test_openapi_contract.py -q` -> `14 passed`
- claims were checked against:
  - `backend/openapi.json`
  - `backend/app/main.py`
  - `backend/app/api/v1/api.py`
  - `backend/app/api/v1/endpoints/cardio.py`
  - `backend/app/api/v1/endpoints/dental.py`
  - `backend/app/api/v1/endpoints/messages.py`
  - `backend/app/api/v1/endpoints/system_management.py`
  - `backend/app/api/v1/endpoints/docs.py`
  - websocket owners under `backend/app/ws/*`

Result:

- the footer no longer advertises non-published specialty routes or a fake
  websocket host
- the remaining low-risk follow-up now sits in the mounted custom docs pages,
  not in `API_REFERENCE.md` footer cleanup
