# Next Execution Unit After Websocket Auth API Service Cleanup

Historical status:

- this pointer was executed and is now a historical snapshot
- current SSOT lives in:
  - `docs/status/AI_FACTORY_OPENHANDS_MASTER_PLAN.md`
  - `docs/status/W2D_NEXT_EXECUTION_UNIT_AFTER_2FA_DEVICES_OPENAPI_PARITY_RESTORATION.md`

Original next step at the time:
- a protected queue-adjacent audit/proof pass for
  `backend/app/services/queue_auto_close_api_service.py` and
  `backend/app/services/wait_time_analytics_api_service.py`

Required entry conditions:
- treat the first pass as audit/proof, not default deletion
- confirm mounted owners, live queue/runtime usage, and contract sensitivity
  before any mutation
- do not reopen `websocket_auth`; the detached duplicate is already gone
- do not widen the slice into cashier or EMR runtime

Why:
- the protected auth-adjacent duplicate queue is now exhausted
- queue-adjacent residue is the next protected bucket still marked as
  audit-only in the strategic inventory
- `cashier` remains payment-critical and the `/api/v1/2fa/devices*`
  route-shadowing tail remains a separate protected ownership issue
