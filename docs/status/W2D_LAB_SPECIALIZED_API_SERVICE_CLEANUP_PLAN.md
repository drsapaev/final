# Lab Specialized API Service Cleanup Plan

Scope:
- delete dead router-style duplicate
  `backend/app/services/lab_specialized_api_service.py`

Evidence:
- `backend/app/api/v1/api.py` mounts the endpoint owner
  `lab_specialized.py`
- `backend/openapi.json` contains the live `/api/v1/lab/*` routes served by
  that owner, including `/api/v1/lab/tests` and `/api/v1/lab/results`
- no confirmed backend, test, docs, or frontend import of
  `lab_specialized_api_service.py` remains
- the service file duplicated mounted router logic instead of acting as a
  consumed service layer

Why this is safe:
- the file was not a mounted owner
- the live lab specialized endpoints remain in `lab_specialized.py`
- removing the duplicate does not change the active lab runtime

Out of scope:
- changing lab route behavior
- changing lab role gates
- removing the mounted `lab_specialized.py` owner
