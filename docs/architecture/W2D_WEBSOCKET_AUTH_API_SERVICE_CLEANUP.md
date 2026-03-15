# Websocket Auth API Service Cleanup

`backend/app/services/websocket_auth_api_service.py` was handled as a protected
auth-adjacent duplicate, not as a blind-delete candidate.

Verified facts:
- `backend/app/api/v1/api.py` mounts
  `backend/app/api/v1/endpoints/websocket_auth.py` under `/api/v1/ws-auth`
- the live websocket routes were confirmed by runtime route introspection:
  - `/api/v1/ws-auth/ws/queue/auth`
  - `/api/v1/ws-auth/ws/queue/optional-auth`
- websocket routes are not published in `backend/openapi.json`, so OpenAPI was
  treated only as a regression guard, not as the source of truth for this slice
- live backend imports already pointed at the mounted endpoint owner:
  - `backend/app/api/v1/endpoints/display_websocket.py`
  - `backend/app/api/v1/endpoints/notification_websocket.py`
  - `backend/tests/unit/test_websocket_auth_subject_normalization.py`
- live frontend usage remains in `frontend/src/utils/websocketAuth.js`
- no live imports of the detached service remained in `backend/app`,
  `backend/tests`, `docs`, or `frontend`
- diff vs the mounted owner exposed narrow runtime drift:
  - the mounted owner did not await `ws_manager.connect(...)`
  - the mounted owner incorrectly awaited synchronous
    `ws_manager.broadcast(...)`

Cleanup performed:
- added `backend/tests/integration/test_websocket_auth_endpoint_contract.py`
  to protect the mounted websocket-auth runtime contract
- repaired the mounted owner in
  `backend/app/api/v1/endpoints/websocket_auth.py` by awaiting
  `ws_manager.connect(...)` and calling synchronous `broadcast(...)` without
  `await`
- deleted detached `backend/app/services/websocket_auth_api_service.py`

Effect:
- no mounted websocket route was removed
- the detached duplicate is gone
- the live websocket-auth owner now matches the actual `WSManager` interface
- auth-adjacent residue moves forward without reopening the separate
  `/api/v1/2fa/devices*` route-shadowing tail
