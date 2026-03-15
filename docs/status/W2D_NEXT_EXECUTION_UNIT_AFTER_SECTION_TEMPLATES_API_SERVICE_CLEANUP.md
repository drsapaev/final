# Next Execution Unit After Section Templates API Service Cleanup

Historical status:

- this pointer was executed and is now a historical snapshot
- current SSOT lives in:
  - `docs/status/AI_FACTORY_OPENHANDS_MASTER_PLAN.md`
  - `docs/status/W2D_NEXT_EXECUTION_UNIT_AFTER_2FA_DEVICES_OPENAPI_PARITY_RESTORATION.md`

Original next step at the time:
- continue the protected EMR / clinical audit/proof lane with
  `backend/app/services/emr_export_api_service.py`

Required entry conditions:
- treat the first pass as audit/proof, not default deletion
- confirm mounted owner, published routes, and live runtime usage before any
  mutation
- keep `cashier_api_service.py` and the mixed `/api/v1/2fa/devices*` tail out
  of the EMR slice

Why:
- `section_templates` was the lightest remaining EMR-protected duplicate pair
  and is now resolved
- the remaining cleanup-capable protected inventory is still in the EMR /
  clinical bucket
- `emr_export` is the next cleanest entry point in that remaining bucket
