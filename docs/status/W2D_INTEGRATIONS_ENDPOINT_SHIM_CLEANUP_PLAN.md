# Integrations Endpoint Shim Cleanup Plan

Scope:
- delete dead endpoint shim `backend/app/api/v1/endpoints/integrations.py`

Evidence:
- `backend/app/api/v1/api.py` does not mount integrations routes
- `backend/openapi.json` contains no integrations endpoint paths
- no confirmed frontend, backend runtime, or test import of the endpoint shim
  remains
- the file itself is only a compatibility re-export of
  `app.services.integrations_api_service`

Why this is safe:
- the endpoint was not mounted, so deleting it cannot change runtime routing
- the actual service module remains in place for its current non-endpoint uses

Out of scope:
- cleanup of `integrations_api_service.py`
- interoperability/integration product design
- introducing or mounting integrations routes
