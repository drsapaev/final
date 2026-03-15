# Websocket Auth API Service Cleanup Plan

Scope:
- review detached `backend/app/services/websocket_auth_api_service.py`
- prove the mounted websocket-auth runtime before any deletion
- port only the narrow mounted-owner drift that is required to match the live
  `WSManager` interface

Evidence:
- the live owner is mounted from
  `backend/app/api/v1/endpoints/websocket_auth.py`
- runtime route introspection confirms the live websocket surface:
  - `/api/v1/ws-auth/ws/queue/auth`
  - `/api/v1/ws-auth/ws/queue/optional-auth`
- live backend helpers already import from the endpoint owner, not the
  detached service
- live frontend usage remains in `frontend/src/utils/websocketAuth.js`
- websocket routes are absent from `backend/openapi.json` by design, so this
  slice needs runtime-contract proof instead of OpenAPI path proof
- diff vs the mounted owner contains behavior-bearing drift around
  `ws_manager.connect(...)` and `ws_manager.broadcast(...)`

Why this is safe:
- dedicated websocket contract proof lands before deleting the detached file
- the only runtime edit is a narrow owner repair that aligns the mounted
  endpoint with the existing `WSManager` async/sync contract
- verification still includes OpenAPI regression, RBAC role-routing, and the
  full backend suite

Out of scope:
- changing queue business logic
- reworking notification/display websocket flows
- touching the separate `/api/v1/2fa/devices*` route-shadowing tail
- widening the slice into queue, payment, or EMR cleanup
