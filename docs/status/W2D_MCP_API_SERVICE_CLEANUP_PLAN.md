# MCP API Service Cleanup Plan

Scope:
- delete dead router-style residue `backend/app/services/mcp_api_service.py`

Evidence:
- `backend/app/api/v1/api.py` mounts the endpoint owner `mcp.py`
- `backend/openapi.json` contains the live `/api/v1/mcp/*` routes served by
  that owner
- no confirmed backend, test, docs, or frontend import of `mcp_api_service.py`
  remains
- the file was not the mounted owner and represented an older detached router
  implementation for the same MCP surface

Why this is safe:
- the file was not a mounted owner
- the live MCP endpoints remain in `mcp.py`
- removing the residue does not change the active MCP runtime

Out of scope:
- changing MCP behavior
- changing MCP authorization behavior
- removing the mounted `mcp.py` owner
