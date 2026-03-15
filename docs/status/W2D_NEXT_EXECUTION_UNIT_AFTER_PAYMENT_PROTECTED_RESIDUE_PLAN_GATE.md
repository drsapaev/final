# Next Execution Unit After Payment Protected Residue Plan Gate

Historical status:

- this pointer was executed and is now superseded by the completed 2FA parity
  follow-up
- current SSOT lives in:
  - `docs/status/AI_FACTORY_OPENHANDS_MASTER_PLAN.md`
  - `docs/status/W2D_NEXT_EXECUTION_UNIT_AFTER_2FA_DEVICES_OPENAPI_PARITY_RESTORATION.md`

Original next step at the time:
- continue from the completed `/api/v1/2fa/devices*` ownership audit into a
  human-reviewed migration/parity plan for that surface

Required entry conditions:
- treat the next pass as a migration decision, not a default deletion
- confirm frontend expectations against both backend owner contracts before any
  runtime mutation
- do not reopen `admin_users`, `minimal_auth`, `simple_auth`,
  `password_reset`, `phone_verification`, `two_factor_devices`,
  `two_factor_sms_email`, `websocket_auth`, `queue_auto_close`, or
  `wait_time_analytics`; all ten have already been resolved with dedicated
  contract proof
- do not reopen the resolved `section_templates`, `emr_export`,
  `emr_versioning_enhanced`, `emr_lab_integration`, `emr_ai`, or
  `emr_ai_enhanced` pairs
- keep the separate `/api/v1/2fa/devices*` route-shadowing tail out of the
  cleanup lane
- keep `cashier_api_service.py` out of the auth-adjacent ownership slice

Why:
- `admin_providers` and `payment_settings` have already been resolved
- `admin_users`, `minimal_auth`, `simple_auth`, `password_reset`, and
  `phone_verification` have also now been resolved
- `two_factor_devices` has also now been resolved with runtime-contract proof
  and cleanup
- `two_factor_sms_email` has also now been resolved with endpoint proof,
  cleanup, and frontend parity repair
- `websocket_auth` has also now been resolved with websocket runtime proof,
  cleanup, and narrow mounted-owner parity fixes
- `queue_auto_close` and `wait_time_analytics` have also now been resolved
  with endpoint proof, cleanup, and narrow mounted-owner SSOT RBAC fixes
- `section_templates` has now also been resolved with dedicated endpoint proof
  and cleanup
- `emr_export` has now also been resolved with dedicated endpoint proof and
  cleanup
- `emr_versioning_enhanced` has now also been resolved with dedicated
  endpoint proof and cleanup
- `emr_lab_integration` has now also been resolved with dedicated endpoint
  proof and cleanup
- `emr_ai` has now also been resolved with dedicated endpoint proof and
  cleanup
- `emr_ai_enhanced` has now also been resolved with dedicated endpoint proof,
  cleanup, and a narrow mounted-owner CRUD import fix
- the `/api/v1/2fa/devices*` ownership audit is now complete; the next honest
  move is a deliberate migration/parity plan, not another detached-file
  deletion
- `cashier` is payment-critical and already flagged for separate human review
