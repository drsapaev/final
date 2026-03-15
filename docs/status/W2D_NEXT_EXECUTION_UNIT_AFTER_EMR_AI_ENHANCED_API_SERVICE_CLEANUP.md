# Next Execution Unit After EMR AI Enhanced API Service Cleanup

Historical status:

- this pointer was executed and is now superseded by the completed
  `docs/architecture/W2D_2FA_DEVICES_OPENAPI_PARITY_RESTORATION.md`
- current SSOT lives in:
  - `docs/status/AI_FACTORY_OPENHANDS_MASTER_PLAN.md`
  - `docs/status/W2D_NEXT_EXECUTION_UNIT_AFTER_2FA_DEVICES_OPENAPI_PARITY_RESTORATION.md`

Original next step at the time:
- open a protected contract/ownership plan-gate for the mixed
  `/api/v1/2fa/devices*` runtime tail

Required entry conditions:
- treat the first pass as audit/planning, not cleanup or deletion
- confirm router-order ownership between
  `backend/app/api/v1/endpoints/two_factor_auth.py` and
  `backend/app/api/v1/endpoints/two_factor_devices.py`
- preserve both published and runtime-resolved routes while the tail is being
  mapped
- keep `cashier_api_service.py` out of this auth-adjacent slice

Why:
- the cleanup-capable protected duplicate queue is now exhausted
- `/api/v1/2fa/devices*` remains the clearest bounded contract-sensitive tail
  that still needs explicit ownership proof
- `cashier` is still payment-critical and should remain a separate later
  review
