# Websocket Auth API Service Cleanup Status

Status: completed

What changed:
- added dedicated websocket-auth endpoint contract tests
- repaired the mounted `websocket_auth.py` owner to await `connect(...)` and
  call synchronous `broadcast(...)` correctly
- deleted `backend/app/services/websocket_auth_api_service.py`

Validation:
- targeted websocket-auth/OpenAPI verification passes
- `python test_role_routing.py` passes
- full backend suite passes

Result:
- `websocket_auth` is no longer an active protected auth residue candidate
- mounted `/api/v1/ws-auth/*` behavior stays intact
- the next honest protected follow-up shifts to queue-adjacent plan-gated audit
