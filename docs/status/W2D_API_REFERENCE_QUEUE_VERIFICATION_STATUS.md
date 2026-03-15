# W2D API Reference Queue Verification Status

Status: completed

What changed:

- the `Queue` section in `docs/API_REFERENCE.md` now reflects the current split
  between modern `/queue/*` surfaces and legacy `/queue/legacy/*`
- the section now documents the live session-based join flow and public
  position/status routes instead of the stale `/queue/join` and
  `/queue/{id}/call` narrative
- the `join/complete` response was intentionally documented conservatively
  because generated OpenAPI does not currently expose a stable typed response

Validation:

- `pytest tests/test_openapi_contract.py -q` -> `14 passed`
- route and schema claims were checked against:
  - `backend/openapi.json`
  - `backend/app/api/v1/endpoints/queue.py`
  - `backend/app/api/v1/endpoints/qr_queue.py`
  - `backend/app/api/v1/endpoints/queue_position.py`
  - `backend/app/api/v1/endpoints/queue_reorder.py`

Result:

- the touched queue docs no longer advertise the stale pre-split queue
  contract
- the section now distinguishes recommended queue routes from legacy
  compatibility routes more honestly
