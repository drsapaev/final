# Telemetry API Service Cleanup Plan

Scope:
- delete dead router-style duplicate
  `backend/app/services/telemetry_api_service.py`

Evidence:
- `backend/app/api/v1/api.py` mounts the endpoint owner `telemetry.py`
- `backend/openapi.json` contains the live `/api/v1/telemetry*` routes served
  by that owner
- no confirmed backend, test, docs, or frontend import of
  `telemetry_api_service.py` remains
- the service file duplicated mounted router logic instead of acting as a
  consumed service layer

Why this is safe:
- the file was not a mounted owner
- the live telemetry endpoints remain in `telemetry.py`
- removing the duplicate does not change the active telemetry runtime

Out of scope:
- changing telemetry validation rules
- changing telemetry event allowlist behavior
- removing the mounted `telemetry.py` owner
