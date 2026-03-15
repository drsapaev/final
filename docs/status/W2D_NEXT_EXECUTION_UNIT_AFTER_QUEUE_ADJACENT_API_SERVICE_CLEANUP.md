# Next Execution Unit After Queue Adjacent API Service Cleanup

Historical status:

- this pointer was executed and is now a historical snapshot
- current SSOT lives in:
  - `docs/status/AI_FACTORY_OPENHANDS_MASTER_PLAN.md`
  - `docs/status/W2D_NEXT_EXECUTION_UNIT_AFTER_2FA_DEVICES_OPENAPI_PARITY_RESTORATION.md`

Original next step at the time:
- a protected EMR / clinical audit/proof pass starting with
  `backend/app/services/section_templates_api_service.py`

Required entry conditions:
- treat the first pass as audit/proof, not default deletion
- confirm mounted owner, live EMR/runtime usage, and contract sensitivity
  before any mutation
- do not reopen the queue-adjacent duplicate files; both detached services are
  already gone
- keep `cashier_api_service.py` and the `/api/v1/2fa/devices*` route-shadowing
  tail outside the EMR slice

Why:
- the protected auth-adjacent and queue-adjacent duplicate buckets are now
  exhausted
- the remaining cleanup-capable protected inventory now sits in the EMR /
  clinical bucket
- `section_templates` is the lightest next entry point in that remaining bucket
