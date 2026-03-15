# MCP API Service Cleanup

`backend/app/services/mcp_api_service.py` was a detached router-style residue
for the mounted MCP endpoint owner.

Verified facts:
- `backend/app/api/v1/api.py` mounts `backend/app/api/v1/endpoints/mcp.py`
  with `prefix="/mcp"`
- `backend/openapi.json` exposes the live `/api/v1/mcp/*` routes owned by the
  mounted endpoint file
- no live source imports of `backend/app/services/mcp_api_service.py` were
  found in `backend/app`, `backend/tests`, `docs`, or `frontend`
- `backend/app/services/mcp_api_service.py` differed from the mounted owner
  only by import path and typing drift and no longer owned runtime route
  behavior

Cleanup performed:
- removed `backend/app/services/mcp_api_service.py`

Effect:
- no mounted runtime route was removed
- live MCP route ownership remains unchanged
- one more dead router-style service residue is gone
