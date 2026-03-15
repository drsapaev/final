# Next Execution Unit After EMR Versioning Enhanced API Service Cleanup

Historical status:

- this pointer was executed and is now a historical snapshot
- current SSOT lives in:
  - `docs/status/AI_FACTORY_OPENHANDS_MASTER_PLAN.md`
  - `docs/status/W2D_NEXT_EXECUTION_UNIT_AFTER_2FA_DEVICES_OPENAPI_PARITY_RESTORATION.md`

Original next step at the time:
- continue the protected EMR / clinical audit/proof lane with
  `backend/app/services/emr_lab_integration_api_service.py`

Required entry conditions:
- treat the first pass as audit/proof, not default deletion
- confirm mounted owner, published routes, and live runtime usage before any
  mutation
- keep `cashier_api_service.py` and the mixed `/api/v1/2fa/devices*` tail out
  of the EMR slice

Why:
- `emr_versioning_enhanced` is now resolved as a proof-backed detached
  duplicate pair
- the remaining cleanup-capable protected inventory is still in the EMR /
  clinical bucket
- `emr_lab_integration` is the next clean entry point in that remaining bucket
