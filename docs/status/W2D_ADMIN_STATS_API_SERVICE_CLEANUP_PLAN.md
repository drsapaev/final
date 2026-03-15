# Admin Stats API Service Cleanup Plan

Scope:
- delete dead service-side residue
  `backend/app/services/admin_stats_api_service.py`

Evidence:
- `backend/app/api/v1/api.py` mounts the endpoint owner `admin_stats.py`
- `backend/openapi.json` contains the live `/api/v1/admin/stats` route served
  by that owner
- no confirmed backend, test, docs, or frontend import of
  `admin_stats_api_service.py` remains
- the file was not the mounted owner and represented an unused alternate
  implementation for the same admin stats surface

Why this is safe:
- the file was not a mounted owner
- the live admin stats endpoint remains in `admin_stats.py`
- removing the residue does not change the active admin stats runtime

Out of scope:
- changing admin stats behavior
- changing revenue aggregation behavior
- removing the mounted `admin_stats.py` owner
